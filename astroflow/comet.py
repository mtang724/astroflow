"""Comet stacking for few, mixed-exposure, cloud-affected frames.

    python -m astroflow.comet --target "F:/AstroPhotograph/C2025-R3"        # after WBPP; then the PixInsight finish:
    python -m astroflow.pipeline "F:/AstroPhotograph/C2025-R3" --recipe comet --master ".../Post/comet_stack.fits"
    python -m astroflow.comet "<dir with star-registered RGB FITS>" --out "<Post dir>" [--ref <substr>] [--no-sxt]

Input: frames already calibrated, debayered and registered on the stars: WBPP's Output/registered (converted to
float FITS in <target>/Post/frames by --target), or any folder of such FITS. With only a handful of frames,
per-pixel statistical rejection is unreliable, so every frame gets:
  1. its own smooth background model (twilight / cloud glow), fitted with the comet's coma + tail protected;
  2. a photometric scale from aperture photometry of stars against the reference frame (exposure and transparency);
  3. a weight map: noise weight measured at a 4-px scale (so binned / upsampled frames are not over-weighted)
     x local transparency (star fluxes), set to zero where the frame disagrees with the others on large scales
     (cloud bands, glow; compared in comet-aligned coordinates around the comet), where it holds a satellite /
     aircraft trail (straight lines found with a Radon transform of the residual) and where it has no data;
  4. its stars removed with StarXTerminator (on a reversible stretch, un-stretched afterwards), so the comet-aligned
     stack has no trailed stars; what SXT removes besides stars (the bright inner coma, a small background
     offset from smoothing noise) is put back.
A flexible background (cloud glow bands a polynomial cannot follow) is then fitted on each starless frame with the
comet masked. Then: a star layer (star-aligned stack of each frame minus its starless version), a comet-aligned
starless stack (nucleus motion fitted linearly in time) with a last comet-protected background model, and a linear
composite = comet + stars. Outputs (in --out):
  comet_stack.fits, stars_linear.fits   the two layers (comet-aligned starless / star-aligned stars only), linear,
                                        star-based colour balance -> the `comet` recipe of astroflow.pipeline
  comet_linear.fits                     their sum (a single linear image, e.g. for processing by hand)
  weights.jpg, diag.json                per-frame weight maps (black = rejected) and numbers
  work/                                 SXT round trips, background model and comet mask previews
"""
import argparse
import glob
import json
import math
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

from . import jobctx

DS = 8   # analysis downsampling factor


# ----------------------------------------------------------------------------------------------- helpers

def load(frames_dir):
    frames = []
    for f in sorted(glob.glob(str(Path(frames_dir) / "*.fits"))):
        h = fits.getheader(f)
        d = fits.getdata(f).astype(np.float32)
        if d.ndim == 2:
            d = d[None]
        t = datetime.fromisoformat(str(h["DATE-OBS"])[:23])
        valid = ndi.binary_erosion((d != 0).any(0), iterations=4, border_value=0)   # registration borders
        frames.append({"name": Path(f).stem, "data": d, "valid": valid, "time": t, "exptime": float(h.get("EXPTIME", 0))})
    frames.sort(key=lambda fr: fr["time"])
    return frames


def downsample(img, k=DS, func=np.median):
    h, w = img.shape[-2] // k * k, img.shape[-1] // k * k
    x = img[..., :h, :w].reshape(img.shape[:-2] + (h // k, k, w // k, k))
    return func(x, axis=(-3, -1))


def upsample(img_ds, shape):
    z = ndi.zoom(img_ds, (shape[0] / img_ds.shape[0], shape[1] / img_ds.shape[1]), order=1)
    return z[:shape[0], :shape[1]]


def mad_std(x):
    x = x[np.isfinite(x)]
    return 1.4826 * float(np.median(np.abs(x - np.median(x)))) + 1e-12


def mtf(m, x):
    return (m - 1) * x / ((2 * m - 1) * x - m)


def shift_img(img, dx, dy, order=1, cval=None):
    if cval is None:
        return ndi.shift(img, (dy, dx), order=order, mode="nearest")
    return ndi.shift(img, (dy, dx), order=order, mode="constant", cval=cval)


def disc(shape, center, radius):
    H, W = shape
    yy, xx = np.ogrid[0:H, 0:W]
    return (xx - center[0]) ** 2 + (yy - center[1]) ** 2 < radius ** 2


# ----------------------------------------------------------------------------------------------- comet geometry

def find_nucleus(lum, guess=None, box=700):
    H, W = lum.shape
    gy, gx = guess or (H // 2, W // 2)
    y0, y1 = max(0, gy - box), min(H, gy + box)
    x0, x1 = max(0, gx - box), min(W, gx + box)
    sub = lum[y0:y1, x0:x1] - np.median(lum[y0:y1, x0:x1])
    sm = ndi.gaussian_filter(sub, 6)
    iy, ix = np.unravel_index(np.argmax(sm), sm.shape)
    cy, cx = iy + y0, ix + x0
    win = lum[cy - 12:cy + 13, cx - 12:cx + 13]
    win = np.clip(win - np.median(win), 0, None)
    yy, xx = np.mgrid[-12:13, -12:13]
    s = win.sum() or 1.0
    return float(cx + (win * xx).sum() / s), float(cy + (win * yy).sum() / s)


def fit_motion(frames):
    """Linear nucleus motion in time (mid-exposure)."""
    t0 = frames[0]["time"]
    ts = np.array([(fr["time"] - t0).total_seconds() + fr["exptime"] / 2 for fr in frames])
    xs = np.array([fr["nucleus"][0] for fr in frames])
    ys = np.array([fr["nucleus"][1] for fr in frames])
    px, py = np.polyfit(ts, xs, 1), np.polyfit(ts, ys, 1)
    for fr, t in zip(frames, ts, strict=True):
        fr["nucleus_fit"] = (float(np.polyval(px, t)), float(np.polyval(py, t)))
    return {"vx_px_per_min": float(px[0] * 60), "vy_px_per_min": float(py[0] * 60),
            "residual_px": float(np.hypot(xs - np.polyval(px, ts), ys - np.polyval(py, ts)).max())}


def tail_angle(lum_flat, nucleus, r0=150, r1=1500):
    """Direction (radians, image coords) with the most excess flux along rays from the nucleus."""
    cx, cy = nucleus
    best, best_a = -1e9, 0.0
    rr = np.arange(r0, r1, 4)
    for deg in range(0, 360, 2):
        a = math.radians(deg)
        xs = (cx + rr * math.cos(a)).astype(int)
        ys = (cy + rr * math.sin(a)).astype(int)
        ok = (xs >= 0) & (ys >= 0) & (xs < lum_flat.shape[1]) & (ys < lum_flat.shape[0])
        if ok.sum() < 20:
            continue
        v = np.median(lum_flat[ys[ok], xs[ok]])
        if v > best:
            best, best_a = v, a
    return best_a


def comet_region(shape, nucleus, angle, coma_r=320, half_angle_deg=14, width0=140):
    """Boolean mask (full resolution) of coma + tail wedge."""
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xx - nucleus[0], yy - nucleus[1]
    r = np.hypot(dx, dy)
    along = dx * math.cos(angle) + dy * math.sin(angle)
    across = np.abs(-dx * math.sin(angle) + dy * math.cos(angle))
    wedge = (along > 0) & (across < width0 + along * math.tan(math.radians(half_angle_deg)))
    return (r < coma_r) | wedge


def comet_mask(lum, nucleus, angle, k=16, thresh=2.5, grow=6):
    """Data-driven coma + tail region on a (starless, comet-aligned) stack: smoothed excess over a coarse
    background, the part connected to the nucleus, grown generously; plus the inner coma and a narrow wedge
    along the tail axis (faint, fragmented outer tail)."""
    shape = lum.shape
    b = downsample(lum, k)
    wedge = downsample(comet_region(shape, nucleus, angle).astype(np.float32), k, np.max) > 0
    sm = ndi.gaussian_filter(b - background_model(b, wedge, degree=2), 1.5)
    hot = sm > thresh * mad_std(sm[~wedge])
    lab, _ = ndi.label(hot)
    ny, nx = int(nucleus[1] // k), int(nucleus[0] // k)
    ids = np.unique(lab[max(0, ny - 2):ny + 3, max(0, nx - 2):nx + 3])
    wide = downsample(comet_region(shape, nucleus, angle, coma_r=500).astype(np.float32), k, np.max) > 0
    keep = ndi.binary_dilation(np.isin(lab, ids[ids > 0]) & wide, iterations=grow)   # no leaking along clouds
    m = upsample(keep.astype(np.float32), shape) > 0.5
    return m | comet_region(shape, nucleus, angle, coma_r=400, half_angle_deg=3, width0=150)


# ----------------------------------------------------------------------------------------------- background

def poly_terms(degree):
    return [(i, d - i) for d in range(degree + 1) for i in range(d, -1, -1)]


def background_model(chan_ds, exclude_ds, degree=4, iters=8):
    """Robust 2-D polynomial fitted to the non-excluded downsampled pixels; positive outliers (stars, glow) and
    negative ones (cloud silhouettes) are rejected iteratively. Returns the model on the downsampled grid."""
    h, w = chan_ds.shape
    v, u = np.mgrid[0:h, 0:w].astype(np.float64)
    u, v = 2 * u / (w - 1) - 1, 2 * v / (h - 1) - 1
    terms = poly_terms(degree)
    A_all = np.stack([u ** i * v ** j for i, j in terms], -1).reshape(-1, len(terms))
    y_all = chan_ds.reshape(-1).astype(np.float64)
    base = ~exclude_ds.reshape(-1) & np.isfinite(y_all)
    ok = base
    coef = None
    for _ in range(iters):
        coef, *_ = np.linalg.lstsq(A_all[ok], y_all[ok], rcond=None)
        res = y_all - A_all @ coef
        s = mad_std(res[ok])
        new_ok = base & (res < 2.5 * s) & (res > -3.0 * s)
        if new_ok.sum() < len(terms) * 20 or (new_ok == ok).all():
            break
        ok = new_ok
    return (A_all @ coef).reshape(h, w).astype(np.float32)


def smooth_background(chan, exclude, k=16, sigma=10.0):
    """Flexible background (normalised convolution of a block-median image, excluded blocks interpolated) for
    cloud remnants a polynomial cannot follow. sigma in blocks; where support is thin it falls back to 3x sigma."""
    b = downsample(chan, k).astype(np.float64)
    m = (downsample(exclude.astype(np.float32), k, np.max) == 0).astype(np.float64)
    fine, coarse = [(ndi.gaussian_filter(b * m, s) / np.maximum(ndi.gaussian_filter(m, s), 1e-9),
                     ndi.gaussian_filter(m, s)) for s in (sigma, 3 * sigma)]
    a = np.clip(fine[1] / 0.25, 0, 1)                 # support of the fine model
    model = a * fine[0] + (1 - a) * coarse[0]
    return upsample(model.astype(np.float32), chan.shape)


# ----------------------------------------------------------------------------------------------- photometry

def detect_stars(lum, exclude, n=400):
    sm = ndi.gaussian_filter(lum, 1.5)
    noise = mad_std(lum[::7, ::7])
    peaks = (sm == ndi.maximum_filter(sm, size=15)) & (sm > 15 * noise) & ~exclude
    peaks[:40] = peaks[-40:] = False
    peaks[:, :40] = peaks[:, -40:] = False
    ys, xs = np.nonzero(peaks)
    order = np.argsort(-sm[ys, xs])
    ys, xs = ys[order], xs[order]
    keep = lum[ys, xs] < 0.85                         # unsaturated
    return xs[keep][:n], ys[keep][:n]


def aperture_flux(img, xs, ys, r=6, r_in=10, r_out=16):
    out = np.zeros(len(xs), np.float64)
    yy, xx = np.mgrid[-r_out:r_out + 1, -r_out:r_out + 1]
    rad = np.hypot(xx, yy)
    ap, ann = rad <= r, (rad >= r_in) & (rad <= r_out)
    for k, (x, y) in enumerate(zip(xs, ys, strict=True)):
        cut = img[y - r_out:y + r_out + 1, x - r_out:x + r_out + 1]
        if cut.shape != ap.shape:
            out[k] = np.nan
            continue
        out[k] = cut[ap].sum() - np.median(cut[ann]) * ap.sum()
    return out


def transparency_map(xs, ys, ratio, shape_ds, scale=DS, smooth=30, prior_stars=3.0):
    """Interpolate per-star flux ratios onto the downsampled grid (normalised convolution). Where only a few stars
    support the estimate it is pulled towards 1 (clear), so sparse/noisy frames do not get spurious holes."""
    acc = np.zeros(shape_ds, np.float64)
    wgt = np.zeros(shape_ds, np.float64)
    for x, y, q in zip(xs // scale, ys // scale, ratio, strict=True):
        if np.isfinite(q) and 0 <= y < shape_ds[0] and 0 <= x < shape_ds[1]:
            acc[y, x] += q
            wgt[y, x] += 1
    kernel_mass = 2 * math.pi * smooth ** 2          # gaussian_filter normalises; rescale to "number of stars"
    acc, wgt = ndi.gaussian_filter(acc, smooth) * kernel_mass, ndi.gaussian_filter(wgt, smooth) * kernel_mass
    return ((acc + prior_stars) / (wgt + prior_stars)).astype(np.float32)


def noise_at_scale(lum, mask, k=4):
    """Noise of k x k block means (high-passed): what matters for extended signal. Frames that were binned and
    upsampled by registration have correlated pixels, so their per-pixel noise flatters them."""
    b = downsample(lum, k, np.mean)
    m = downsample(mask.astype(np.float32), k, np.min) > 0
    return mad_std((b - ndi.median_filter(b, 5))[m])


# ----------------------------------------------------------------------------------------------- clouds and trails

def disagreement(stack, shifts, protect, k):
    """Per-frame residual against the median of the other frames: star-aligned outside the comet region,
    comet-aligned inside it (so the comet's own motion is not a difference). stack: (N,H,W) star-aligned."""
    n = len(stack)
    comet = np.stack([shift_img(s, dx / k, dy / k) for s, (dx, dy) in zip(stack, shifts, strict=True)])
    out = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        rs = stack[i] - np.median(stack[others], axis=0)
        rc = comet[i] - np.median(comet[others], axis=0)
        rc = shift_img(rc, -shifts[i][0] / k, -shifts[i][1] / k)
        out.append(np.where(protect, rc, rs).astype(np.float32))
    return out


def detect_trails(res, ok_full, ds=4, step_deg=0.25, thresh=8.0, max_lines=8):
    """Straight bright lines (satellites, aircraft) in a residual image (frame minus the median of the others):
    Radon transform of the high-passed, clipped residual at 1/ds resolution, peaks refined to 0.02 deg. Each
    accepted line's pixels are taken out of the transform before the next search (otherwise a bright trail
    returns a fan of near-duplicates). Returns [(theta, rho, snr, halfwidth)] in full-resolution pixels; the
    line is x cos(theta) + y sin(theta) = rho."""
    r = downsample(res, ds, np.mean)
    ok = downsample(ok_full.astype(np.float32), ds, np.min) > 0
    hp = r - ndi.median_filter(r, 9)                 # thin lines survive, clouds and glow do not
    z = np.clip(hp / mad_std(hp[ok]), -4, 4)
    ys, xs = np.nonzero(ok)
    zv = z[ys, xs].astype(np.float32)
    xs = xs.astype(np.float32) + 0.5
    ys = ys.astype(np.float32) + 0.5
    rmax = int(np.hypot(*z.shape)) + 2
    nb = 2 * rmax + 1
    removed = np.zeros(len(xs), bool)

    def sums(thetas, sel=None):
        x, y, w = (xs, ys, zv) if sel is None else (xs[sel], ys[sel], zv[sel])
        S = np.zeros((len(thetas), nb))
        N = np.zeros((len(thetas), nb))
        for k, t in enumerate(thetas):
            b = np.rint(x * math.cos(t) + y * math.sin(t)).astype(np.int32) + rmax
            S[k] = np.bincount(b, weights=w, minlength=nb)
            N[k] = np.bincount(b, minlength=nb)
        return S, N

    thetas = np.deg2rad(np.arange(0, 180, step_deg))
    S, N = sums(thetas)
    usable = N >= 150
    norm = mad_std((S / np.sqrt(np.maximum(N, 1)))[usable])
    lines = []
    for _ in range(max_lines):
        stat = np.where(usable, S / np.sqrt(np.maximum(N, 1)), 0) / norm
        k, b = np.unravel_index(np.argmax(stat), stat.shape)
        if stat[k, b] < thresh:
            break
        fine = thetas[k] + np.deg2rad(np.arange(-0.3, 0.301, 0.02))
        Sf, Nf = sums(fine, ~removed)
        lo, hi = max(0, b - 6), min(nb, b + 7)
        sub = (Sf / np.sqrt(np.maximum(Nf, 1)))[:, lo:hi]
        kk, bb = np.unravel_index(np.argmax(sub), sub.shape)
        t, rho = float(fine[kk]), float(bb + lo - rmax)
        hw = _trail_halfwidth(res, ok_full, t, rho * ds)
        lines.append((t, rho * ds, float(stat[k, b]), hw))
        sel = (np.abs(xs * math.cos(t) + ys * math.sin(t) - rho) < hw / ds + 1.0) & ~removed
        S -= sums(thetas, sel)[0]
        removed |= sel
    return lines


def _trail_halfwidth(res, ok_full, t, rho, reach=40):
    """Half-width (px) of a detected line from its mean perpendicular profile where the trail is present."""
    H, W = res.shape
    c, s = math.cos(t), math.sin(t)
    p0 = np.array([rho * c, rho * s])                # foot of the perpendicular from the origin
    d = np.array([-s, c])                            # direction along the line
    L = np.arange(-math.hypot(H, W), math.hypot(H, W), 4.0)
    pts = p0[None] + L[:, None] * d[None]
    inside = (pts[:, 0] > reach) & (pts[:, 0] < W - reach) & (pts[:, 1] > reach) & (pts[:, 1] < H - reach)
    pts = pts[inside]
    if len(pts) < 50:
        return 12.0
    offs = np.arange(-reach, reach + 1)
    X = pts[:, 0][:, None] + offs[None] * c
    Y = pts[:, 1][:, None] + offs[None] * s
    prof = ndi.map_coordinates(res, [Y.ravel(), X.ravel()], order=1).reshape(X.shape)
    okp = ndi.map_coordinates(ok_full.astype(np.float32), [Y.ravel(), X.ravel()], order=0).reshape(X.shape) > 0
    prof = np.where(okp, prof, np.nan)
    with np.errstate(all="ignore"):
        centre = ndi.uniform_filter1d(np.nan_to_num(np.nanmean(prof[:, reach - 2:reach + 3], 1)), 25)
        p = np.nanmean(prof[centre > np.percentile(centre, 60)], 0)
    p = p - np.nanmedian(np.concatenate([p[:8], p[-8:]]))
    peak = np.nanmax(p[reach - 4:reach + 5])
    above = np.nonzero(p > 0.08 * peak)[0] if peak > 0 else []
    run = [a for a in above if abs(a - reach) <= 25]
    if not run:
        return 12.0
    return float(min(max(max(abs(a - reach) for a in run) + 4, 7), 30))


def line_mask(shape, t, rho, halfwidth):
    H, W = shape
    yy, xx = np.ogrid[0:H, 0:W]
    return np.abs(xx * math.cos(t) + yy * math.sin(t) - rho) < halfwidth


# ----------------------------------------------------------------------------------------------- stacking

def weighted_stack(datas, weights, fallback_weights=None, k=4.0, sigmas=None):
    """Weighted mean of (3,H,W) frames with per-frame (H,W) weights. Values further than k sigma from the per-pixel
    median of the frames that cover the pixel are dropped (trails, hot pixels, star remnants) when >= 3 frames
    cover it (k=None: no rejection; sigmas: per-frame noise, default measured on the frames). Pixels no frame
    covers take the fallback weights (e.g. without cloud masks), then a plain mean."""
    D = np.stack(datas)                      # (N,3,H,W)
    Wt = np.stack(weights)[:, None]          # (N,1,H,W)
    bad = np.zeros(Wt.shape, bool)
    if k is not None:
        lum = D.mean(1, keepdims=True)
        if sigmas is None:
            sigmas = [mad_std(x[::5, ::5]) for x in lum[:, 0]]
        sig = np.array(sigmas, np.float32)[:, None, None, None]
        cover = (Wt > 0).sum(0)
        with warnings.catch_warnings():                      # pixels no frame covers: all-NaN, handled below
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(np.where(Wt > 0, lum, np.nan), axis=0)
        bad = (np.abs(lum - med) > k * sig) & (cover >= 3)
        del lum, med
        Wt = np.where(bad, 0, Wt)
    s = Wt.sum(0)
    stack = (D * Wt).sum(0) / np.maximum(s, 1e-30)
    holes = s <= 0
    if fallback_weights is not None and holes.any():
        Wf = np.stack(fallback_weights)[:, None]
        sf = Wf.sum(0)
        stack = np.where(holes & (sf > 0), (D * Wf).sum(0) / np.maximum(sf, 1e-30), stack)
        holes = holes & (sf <= 0)
    stack = np.where(holes, D.mean(0), stack)
    return stack.astype(np.float32), {"rejected": int(bad.sum()), "holes": int(holes.sum())}


def save_fits(path, img, header=None):
    fits.writeto(path, np.ascontiguousarray(img.astype(np.float32)), header=header, overwrite=True)


def _save_gray(path, img):
    from PIL import Image
    lo, hi = np.percentile(img, [0.5, 99.5])
    Image.fromarray((255 * np.clip((img - lo) / max(hi - lo, 1e-12), 0, 1)).astype(np.uint8)).save(path, quality=90)


# ----------------------------------------------------------------------------------------------- star removal

def remove_stars(images, work, nuclei, label="comet-sxt", reuse=False):
    """StarXTerminator on a reversible stretch of each linear (3,H,W) image; returns the un-stretched starless
    images, repaired so that only the stars are removed (see repair_starless).
    reuse=True takes earlier SXT outputs from the work dir when they were made from the same stretch."""
    from . import pi
    work = Path(work)
    (work / "sxt_in").mkdir(parents=True, exist_ok=True)
    (work / "sxt_out").mkdir(parents=True, exist_ok=True)
    meta_path = work / "sxt_params.json"
    old = json.loads(meta_path.read_text()) if reuse and meta_path.exists() else None
    params, ins, outs = [], [], []
    for i, img in enumerate(images):
        noise = mad_std(img.mean(0)[::5, ::5])
        lo, hi = -6 * noise, float(img.max()) * 1.001
        m = float(mtf(0.12, (0 - lo) / (hi - lo)))
        params.append((lo, hi, m))
        ins.append((work / "sxt_in" / f"f{i}.fits").as_posix())
        outs.append((work / "sxt_out" / f"f{i}.fits").as_posix())
    fresh = old is not None and len(old) == len(params) and all(Path(o).exists() for o in outs + ins) and \
        all(np.allclose(a, b, rtol=1e-3) for a, b in zip(old, params, strict=True))
    if fresh:
        params = [tuple(x) for x in old]
    else:
        for img, (lo, hi, m), p_in in zip(images, params, ins, strict=True):
            save_fits(p_in, mtf(m, np.clip((img - lo) / (hi - lo), 0, 1)))
        job = {"input": ins[0], "aux": {f"f{i}": ins[i] for i in range(1, len(ins))}, "linear": False,
               "steps": [{"op": "sxt", "target": "main" if i == 0 else f"f{i}", "unscreen": False, "largeOverlap": True}
                         for i in range(len(ins))],
               "save": [{"window": "main" if i == 0 else f"f{i}", "path": outs[i], "bits": 32} for i in range(len(ins))]}
        pi.run_job(job, timeout=3 * 3600, label=label, idle_limit=1200)
        meta_path.write_text(json.dumps(params))
    result = []
    for img, (lo, hi, m), p_in, p_out, nuc in zip(images, params, ins, outs, nuclei, strict=True):
        y = fits.getdata(p_out).astype(np.float32)
        y_in = fits.getdata(p_in)
        if np.median(np.abs(y[:, ::-1][:, ::16, ::16] - y_in[:, ::16, ::16])) < \
                np.median(np.abs(y[:, ::16, ::16] - y_in[:, ::16, ::16])):
            y = y[:, ::-1]                               # FITS row-order convention differs: flip back
        x = (lo + mtf(1 - m, np.clip(y, 0, 1)) * (hi - lo)).astype(np.float32)
        repair_starless(x, img, nuc)
        result.append(x)
    return result


def repair_starless(starless, original, nucleus, block=32, radius=300, star_size=35, core=30):
    """Keep only the stars out of SXT's result, in place. What SXT removed (original - starless) is stars plus two
    smooth things that are not stars: (1) a small offset everywhere - it smooths noise on the stretched image, which
    after un-stretching lowers the background, most in the noisiest channel and less on brighter sky; (2) the bright
    inner coma, which it takes for a star (out to ~100 px here). Both are put back: a coarse block-median field of the
    removed light over the whole frame, and around the nucleus a 35 px median filter (keeps the extended coma, drops
    compact stars) with the innermost core taken straight from the original."""
    removed = original - starless
    smooth = np.stack([upsample(downsample(ch, block), ch.shape) for ch in removed])
    if nucleus is not None:
        H, W = starless.shape[1:]
        cx, cy = int(round(nucleus[0])), int(round(nucleus[1]))
        pad = radius + star_size
        y0, y1, x0, x1 = max(0, cy - pad), min(H, cy + pad), max(0, cx - pad), min(W, cx + pad)
        rem = removed[:, y0:y1, x0:x1]
        fine = np.stack([ndi.median_filter(ch, size=star_size) for ch in rem])
        yy, xx = np.ogrid[y0:y1, x0:x1]
        r = np.hypot(xx - nucleus[0], yy - nucleus[1])
        a = np.clip((radius - r) / 50, 0, 1).astype(np.float32)          # fine model inside, coarse field outside
        b = np.clip((2 * core - r) / core, 0, 1).astype(np.float32)      # core: original pixels
        smooth[:, y0:y1, x0:x1] = (1 - a) * smooth[:, y0:y1, x0:x1] + a * ((1 - b) * fine + b * rem)
    starless += smooth


# ----------------------------------------------------------------------------------------------- main

def convert_registered(target_dir, frames_dir):
    """WBPP's registered XISF frames -> float FITS for this module (one PixInsight job). Returns the FITS paths."""
    from . import pi
    src = sorted((Path(target_dir) / "Output" / "registered").rglob("*.xisf"))
    if not src:
        raise FileNotFoundError(f"no registered frames under {target_dir}/Output/registered (run WBPP first)")
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    outs = [(frames_dir / f"{p.stem}.fits").as_posix() for p in src]
    job = {"input": src[0].as_posix(), "aux": {f"f{i}": p.as_posix() for i, p in enumerate(src[1:], 1)},
           "linear": True, "steps": [],
           "save": [{"window": "main" if i == 0 else f"f{i}", "path": o, "bits": 32} for i, o in enumerate(outs)]}
    pi.run_job(job, timeout=3600, label="comet-convert")
    return outs


def run(frames_dir, out_dir, ref_name=None, sxt=True, work=None, reuse_sxt=False):
    out = Path(out_dir)
    work = Path(work) if work else out / "work"
    for d in (out, work):
        d.mkdir(parents=True, exist_ok=True)
    frames = load(frames_dir)
    diag = {"frames": [{"name": fr["name"], "exptime": fr["exptime"], "time": fr["time"].isoformat()} for fr in frames]}

    step = _progress(["locate", "background", "photometry", "stars", "clouds", "weights", "stack", "flatten", "write"])
    step()
    ref, angle = locate_comet(frames, ref_name, diag)
    step()
    subtract_polynomial_backgrounds(frames, angle)
    step()
    calibrate_photometry(frames, ref, diag)
    step()
    images = [fr["data"] for fr in frames]
    starless = remove_stars(images, work, [fr["nucleus"] for fr in frames], reuse=reuse_sxt) if sxt         else [im.copy() for im in images]
    for fr, sl in zip(frames, starless, strict=True):
        fr["starless"] = sl
    step()
    subtract_cloud_glow(frames, ref, angle, work)
    step()
    weights, fallback, noise1 = frame_weights(frames, diag)
    _save_weight_preview(out / "weights.jpg", weights, [f["name"] for f in diag["frames"]])
    step()
    comet_stack, stars = stack_layers(frames, weights, fallback, noise1, diag)
    step()
    flatten_comet_background(comet_stack, frames, ref, angle, work, diag)
    step()
    write_outputs(out, comet_stack, stars, ref, diag)
    return diag


def _progress(names):
    """Each call announces the next step (and is a point where a cancel request takes effect)."""
    it = iter(enumerate(names))

    def step():
        i, name = next(it)
        jobctx.check_cancelled()
        jobctx.emit("comet.step", step=name, index=i, total=len(names))
    return step


def locate_comet(frames, ref_name, diag):
    """Nucleus per frame and its linear motion; the photometric reference (darkest sky per unit exposure, i.e. least
    twilight / cloud glow, unless named); the tail direction; each frame's shift onto the reference's comet."""
    shape = frames[0]["data"].shape[1:]
    flat = {}
    for fr in frames:
        lum = fr["data"].mean(0)
        flat[fr["name"]] = lum - upsample(ndi.median_filter(downsample(lum), 41), shape)
        fr["nucleus"] = find_nucleus(flat[fr["name"]])
    diag["motion"] = fit_motion(frames)
    ref = next((fr for fr in frames if ref_name and ref_name in fr["name"]), None) or \
        min(frames, key=lambda fr: np.median(flat[fr["name"]]) + np.median(fr["data"].mean(0)) / max(fr["exptime"], 1e-3))
    angle = tail_angle(flat[ref["name"]], ref["nucleus"])
    diag["reference"], diag["tail_angle_deg"] = ref["name"], round(math.degrees(angle), 1)
    for fr in frames:
        fr["shift"] = (ref["nucleus_fit"][0] - fr["nucleus_fit"][0], ref["nucleus_fit"][1] - fr["nucleus_fit"][1])
    return ref, angle


def subtract_polynomial_backgrounds(frames, angle):
    """Smooth twilight gradient per frame and channel, fitted with the coma + tail wedge and no-data borders excluded."""
    shape = frames[0]["data"].shape[1:]
    for fr in frames:
        fr["protect"] = comet_region(shape, fr["nucleus"], angle)
        excl_ds = (downsample(fr["protect"].astype(np.float32), func=np.max) > 0) | \
                  (downsample((~fr["valid"]).astype(np.float32), func=np.max) > 0)
        d = fr["data"]
        for c in range(d.shape[0]):
            d[c] -= upsample(background_model(downsample(d[c]), excl_ds), shape)
        d[:, ~fr["valid"]] = 0


def calibrate_photometry(frames, ref, diag):
    """Scale every frame to the reference with star aperture photometry (the clear-sky scale is an upper percentile
    of the star ratios, since clouds only remove light), map local transparency, and balance colour so the average
    star is white (applied now so SXT sees natural colour)."""
    ref_lum = ref["data"].mean(0)
    xs, ys = detect_stars(ref_lum, ref["protect"] | ~ref["valid"])
    f_ref = aperture_flux(ref_lum, xs, ys)
    for fr in frames:
        lum = fr["data"].mean(0)
        ratio = aperture_flux(lum, xs, ys) / f_ref
        good = np.isfinite(ratio) & (f_ref > 0) & fr["valid"][ys, xs]
        fr["scale"] = float(np.nanpercentile(ratio[good], 75)) if good.sum() > 10 else fr["exptime"] / ref["exptime"]
        fr["data"] /= fr["scale"]
        fr["transp_ds"] = np.clip(transparency_map(xs[good], ys[good], ratio[good] / fr["scale"], downsample(lum).shape), 0, 1.2)
    fl = np.stack([aperture_flux(ref["data"][c], xs, ys) for c in range(3)])
    okc = np.all(np.isfinite(fl) & (fl > 0), axis=0)
    kc = np.array([np.median(fl[1, okc] / fl[c, okc]) for c in range(3)]) if okc.sum() > 10 else np.ones(3)
    for fr in frames:
        fr["data"] *= kc[:, None, None].astype(np.float32)
    diag["white_balance"] = [round(float(k), 4) for k in kc]


def subtract_cloud_glow(frames, ref, angle, work):
    """Flexible per-frame background for the cloud glow bands a polynomial cannot follow. Fitted on the starless
    frame (star halos would bias it); the comet is protected by a data-driven mask from a comet-aligned median, kept
    tight so the interpolated gaps stay small. Subtracted from both the frame and its starless version."""
    med = np.median(np.stack([shift_img(fr["starless"].mean(0), *fr["shift"]) for fr in frames]), axis=0)
    region = comet_mask(med, ref["nucleus_fit"], angle)
    del med
    _save_gray(work / "frame_comet_mask.jpg", downsample(region.astype(np.float32), 8, np.mean))
    for fr in frames:
        dx, dy = fr["shift"]
        fr["comet_zone"] = shift_img(region.astype(np.float32), -dx, -dy, cval=0.0) > 0.5
        excl = fr["comet_zone"] | ~fr["valid"]
        for c in range(3):
            mdl = smooth_background(fr["starless"][c], excl, sigma=4.0)
            fr["starless"][c] -= mdl
            fr["data"][c] -= mdl
        fr["data"][:, ~fr["valid"]] = 0
        fr["starless"][:, ~fr["valid"]] = 0


def frame_weights(frames, diag):
    """Per-frame weight maps: 1/noise^2 (4-px scale, measured on the original frame - SXT smooths noisy frames) x
    local transparency, zero where the frame disagrees with the others (clouds; on the comet only dimming counts,
    since a frame whose tail is brighter than the others' is the clear one), on satellite / aircraft trails and
    outside its data. Returns (weights, fallback weights without cloud masks, per-pixel noise)."""
    shape = frames[0]["data"].shape[1:]
    shifts = [fr["shift"] for fr in frames]
    prot_union = np.logical_or.reduce([fr["protect"] for fr in frames])
    common = ndi.binary_erosion(np.logical_and.reduce([fr["valid"] for fr in frames]), iterations=8, border_value=0)
    common_ds = downsample(common.astype(np.float32), func=np.min) > 0
    res_ds = disagreement(np.stack([downsample(fr["starless"].mean(0)) for fr in frames]), shifts,
                          downsample(prot_union.astype(np.float32), func=np.max) > 0, DS)
    lums = [fr["data"].mean(0) for fr in frames]
    res_full = disagreement(np.stack(lums), shifts, prot_union, 1)
    weights, fallback, noise1 = [], [], []
    for i, fr in enumerate(frames):
        lum, valid = lums[i], fr["valid"]
        nuc_zone = disc(shape, fr["nucleus"], 150)
        noise4 = noise_at_scale(lum, valid & ~fr["protect"])
        noise1.append(mad_std(lum[valid][::37]))
        base = 1.0 / noise4 ** 2
        r = ndi.gaussian_filter(res_ds[i], 3)
        nz_ds = downsample(nuc_zone.astype(np.float32), func=np.max) > 0
        cz_ds = downsample(fr["comet_zone"].astype(np.float32), func=np.max) > 0
        thr = 5 * mad_std(r[~nz_ds & ~cz_ds & common_ds])
        cloud = np.where(cz_ds, r < -thr, np.abs(r) > thr) & ~nz_ds & common_ds
        ring = (downsample(disc(shape, fr["nucleus"], 300).astype(np.float32), func=np.max) > 0) & ~nz_ds
        if cloud[ring].mean() > 0.5:                                # the nucleus itself is judged by its surroundings
            cloud |= nz_ds
        cloud = ndi.binary_dilation(cloud, iterations=3)
        t = fr["transp_ds"]
        w_ds = np.where(cloud, 0.0, np.clip((t - 0.55) / 0.35, 0, 1) ** 2).astype(np.float32)
        w_ds = ndi.gaussian_filter(w_ds, 2)                                          # feather seams
        trails = detect_trails(res_full[i], common & ~nuc_zone)
        tmask = np.zeros(shape, bool)
        for t_, rho, _snr, hw in trails:
            tmask |= line_mask(shape, t_, rho, hw)
        ok = valid & ~tmask
        weights.append((upsample(w_ds, shape) * base * ok).astype(np.float32))
        fallback.append((ok * base).astype(np.float32))
        diag["frames"][i].update({
            "nucleus": [round(v, 1) for v in fr["nucleus"]], "comet_shift_px": [round(v, 2) for v in fr["shift"]],
            "scale_vs_ref": round(fr["scale"], 3), "noise_4px": noise4, "relative_weight": base,
            "cloud_fraction": round(float(cloud.mean()), 4), "low_transparency_fraction": round(float((t < 0.7).mean()), 4),
            "trails": [{"angle_deg": round(math.degrees(a), 2), "rho": round(p, 1), "snr": round(s, 1), "halfwidth": hw}
                       for a, p, s, hw in trails]})
    tot = sum(f["relative_weight"] for f in diag["frames"])
    for f in diag["frames"]:
        f["relative_weight"] = round(f["relative_weight"] / tot, 3)
    return weights, fallback, noise1


def stack_layers(frames, weights, fallback, noise1, diag):
    """Comet layer: starless frames shifted onto the reference's nucleus, weighted stack with 4-sigma rejection.
    Star layer: star-aligned stack of the signed per-frame differences (frame - starless; only gross outliers
    rejected, since star peaks vary with the seeing), kept only where a star is detected - clipping each frame's
    difference at zero would leave a positive, colour-biased haze. Frees the frames' image data."""
    shape = frames[0]["data"].shape[1:]
    diffs = [fr.pop("data") - fr["starless"] for fr in frames]
    comet_datas = [np.stack([shift_img(ch, *fr["shift"]) for ch in fr.pop("starless")]) for fr in frames]
    comet_w = [shift_img(w, *fr["shift"], cval=0.0) for fr, w in zip(frames, weights, strict=True)]
    comet_fb = [shift_img(w, *fr["shift"], cval=0.0) for fr, w in zip(frames, fallback, strict=True)]
    comet_stack, info_c = weighted_stack(comet_datas, comet_w, comet_fb)
    del comet_datas, comet_w, comet_fb
    S, info_s = weighted_stack(diffs, weights, fallback, k=10.0, sigmas=noise1)
    del diffs
    S -= np.median(S[:, ::5, ::5], axis=(1, 2))[:, None, None]
    found = ndi.gaussian_filter(S.mean(0), 1.0) > 2.5 * mad_std(comet_stack.mean(0)[::5, ::5])
    stars = np.clip(S, 0, None) * ndi.gaussian_filter(ndi.binary_dilation(found, iterations=3).astype(np.float32), 1.5)
    del S
    for fr in frames:
        stars[:, disc(shape, fr["nucleus"], 50)] = 0                 # the nucleus belongs to the comet layer
    diag["stack"] = {"stars": info_s, "comet": info_c, "star_pixels": int(found.sum())}
    return comet_stack, stars


def flatten_comet_background(comet_stack, frames, ref, angle, work, diag):
    """A last comet-protected flexible background on the comet layer (what is left of the clouds). In place."""
    region = comet_mask(comet_stack.mean(0), ref["nucleus_fit"], angle)
    valid_all = np.logical_and.reduce([shift_img(fr["valid"].astype(np.float32), *fr["shift"], cval=0.0) > 0.5
                                       for fr in frames])
    models = []
    for c in range(3):
        mdl = smooth_background(comet_stack[c], region | ~valid_all)
        comet_stack[c] -= mdl
        models.append(downsample(mdl, 8, np.mean))
    _save_gray(work / "comet_bg_model.jpg", np.mean(models, 0))
    _save_gray(work / "comet_mask.jpg", downsample(region.astype(np.float32), 8, np.mean))
    diag["comet_mask_fraction"] = round(float(region.mean()), 4)
    diag["comet_bg_model_rms"] = float(np.std(np.mean(models, 0)))


def write_outputs(out, comet_stack, stars, ref, diag):
    """Normalise (brightest stars just below 1), add a small pedestal to the comet layer, write the FITS files."""
    comp = comet_stack + stars
    norm = 0.95 / max(float(np.percentile(comp.max(0), 99.9999)), 1e-9)
    ped = max(0.0005, 5 * mad_std(comp.mean(0)[::5, ::5]) * norm)
    hdr = fits.Header()
    hdr["DATE-OBS"] = ref["time"].isoformat()
    hdr["COMMENT"] = "astroflow.comet: comet-aligned starless stack + star-aligned stars, linear"
    save_fits(out / "comet_linear.fits", np.clip(comp * norm + ped, 0, 1), hdr)
    save_fits(out / "comet_stack.fits", np.clip(comet_stack * norm + ped, 0, 1), hdr)
    save_fits(out / "stars_linear.fits", np.clip(stars * norm, 0, 1), hdr)
    diag["normalisation"] = {"norm": norm, "pedestal": ped, "nucleus_xy": [round(v, 1) for v in ref["nucleus_fit"]],
                             "background_noise": mad_std(comet_stack.mean(0)[::5, ::5]) * norm}
    (out / "diag.json").write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")


def _save_weight_preview(path, weights, names):
    from PIL import Image, ImageDraw
    tiles = []
    top = max(float(w.max()) for w in weights)
    for w, n in zip(weights, names, strict=True):
        ds = downsample(w, 8, np.mean)
        ds = (255 * np.sqrt(ds / max(top, 1e-30))).astype(np.uint8)    # sqrt: weak frames still visible
        im = Image.fromarray(ds).convert("RGB")
        ImageDraw.Draw(im).text((8, 8), n[-40:], fill=(255, 64, 64))
        tiles.append(im)
    W, H = tiles[0].size
    sheet = Image.new("RGB", (W * len(tiles), H))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * W, 0))
    sheet.save(path, quality=90)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frames_dir", nargs="?", help="star-registered RGB FITS (default with --target: <target>/Post/frames)")
    ap.add_argument("--target", help="target folder after WBPP; registered frames are converted if needed")
    ap.add_argument("--out", help="output folder (default with --target: <target>/Post)")
    ap.add_argument("--ref", help="substring of the frame to use as photometric reference (default: darkest sky)")
    ap.add_argument("--no-sxt", action="store_true", help="skip StarXTerminator (comet stack keeps trailed stars)")
    ap.add_argument("--work", help="scratch dir for SXT round trips (default <out>/work)")
    ap.add_argument("--reuse-sxt", action="store_true", help="reuse SXT outputs in the work dir when still valid")
    a = ap.parse_args()
    if a.target:
        a.out = a.out or str(Path(a.target) / "Post")
        a.frames_dir = a.frames_dir or str(Path(a.out) / "frames")
        if not glob.glob(str(Path(a.frames_dir) / "*.fits")):
            convert_registered(a.target, a.frames_dir)
    if not (a.frames_dir and a.out):
        ap.error("give frames_dir and --out, or --target")
    print(json.dumps(run(a.frames_dir, a.out, a.ref, sxt=not a.no_sxt, work=a.work, reuse_sxt=a.reuse_sxt),
                     ensure_ascii=False, indent=1))
