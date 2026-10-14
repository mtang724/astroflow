"""Per-frame quality of a target's light frames: how many stars, how large (FWHM) and how round they are, and how bright
the sky is, with a thumbnail of each frame, so frames spoiled by clouds, dew, wind, bad focus or dawn can be seen and
left out before stacking.

    framecheck.analyze(target)              measure the lights (new or changed frames only; cached in frames.json)
    framecheck.report(target)               the measurements, with suspicious frames flagged and why
    framecheck.exclude(target, names)       move frames to <target>/Excluded/Light (WBPP never sees them)
    framecheck.restore(target, names)       move them back

Frames are compared with the target's own frames (median and spread of the set), so the flags work for any camera,
exposure and sky. Measurements are made on binned luminance (astroflow.frameio): stars are local maxima well above the
background noise, their size and elongation come from adaptive second moments of the brightest unsaturated ones (within
~10 % of Gaussian fits on ZWO, Nikon and Fujifilm X-Trans frames). Names are paths relative to Light/ (multi-night
targets have a folder per night there).
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import frameio, jobctx, jsonfile, wbpp
from .i18n import tr

STORE = "frames.json"
THUMBS = Path("Thumbnails") / "frames"
EXCLUDED = Path("Excluded") / "Light"
THUMB_SIDE = 480
DETECT_SIGMA = 5.0
FWHM_SNR = 30.0                  # stars this far above the noise (and unsaturated) give the size and shape
WINDOW = 8                       # half size of the box around a star (binned px)
MIN_FRAMES = 5                   # fewer frames: nothing to compare with
FLAG_STARS = 0.5                 # fewer stars than this fraction of the median: clouds, fog, dew
FLAG_FWHM = 0.25                 # stars this much larger than the median: focus, seeing, wind
FLAG_ECC = 0.6                   # elongation (eccentricity) above this and clearly above the others: tracking, wind
FLAG_BACKGROUND = 0.10           # sky this much brighter than the median: moon, clouds, dawn


# ----------------------------------------------------------------------------------------------- measuring

def measure(path):
    """Stars, FWHM (native pixels), eccentricity, background and noise of one frame, and a stretched thumbnail
    (uint8 array)."""
    img, b = frameio.read_luminance(path)
    bgmap = _background_map(img)
    resid = img - bgmap
    noise = _mad_sigma(resid)
    smooth = ndimage.gaussian_filter(resid, 1.0)
    peaks = (smooth > DETECT_SIGMA * _mad_sigma(smooth)) & (smooth == ndimage.maximum_filter(smooth, size=5))
    r = WINDOW
    peaks[:r + 1], peaks[-r - 1:], peaks[:, :r + 1], peaks[:, -r - 1:] = False, False, False, False
    ys, xs = np.nonzero(peaks)
    bright = (resid[ys, xs] > FWHM_SNR * noise) & (img[ys, xs] < 0.9)      # unsaturated, well above the noise
    if bright.sum() > 400:                                                    # plenty: the brightest 400 will do
        keep = np.argsort(-resid[ys, xs] * bright)[:400]
        bright = np.zeros_like(bright)
        bright[keep] = True
    sigma, ecc = _adaptive_moments(resid, ys[bright], xs[bright])
    ok = np.isfinite(sigma)
    return {"stars": int(ys.size),
            "fwhm_px": round(float(np.median(sigma[ok])) * 2.3548 * b, 3) if ok.sum() >= 5 else None,
            "ecc": round(float(np.median(ecc[ok])), 3) if ok.sum() >= 5 else None,
            "background": round(float(np.median(bgmap)), 6), "noise": round(noise, 6)}, _thumbnail(img)


def _mad_sigma(a):
    s = a[::5, ::5]
    return 1.4826 * float(np.median(np.abs(s - np.median(s)))) or 1e-6


def _background_map(img, tile=64):
    """Sky level everywhere: medians of tiles (each smoothed with its neighbours, so stars and small nebulae do not
    count), interpolated back to full size."""
    ny, nx = img.shape[0] // tile, img.shape[1] // tile
    if ny < 2 or nx < 2:
        return np.full_like(img, np.median(img))
    tiles = np.median(img[:ny * tile, :nx * tile].reshape(ny, tile, nx, tile), axis=(1, 3))
    tiles = ndimage.median_filter(tiles, size=3, mode="nearest")
    zoom = (img.shape[0] / ny, img.shape[1] / nx)
    return ndimage.zoom(tiles, zoom, order=1, mode="nearest", grid_mode=True)[:img.shape[0], :img.shape[1]].astype(
        np.float32)


def _adaptive_moments(resid, ys, xs, iterations=6):
    """Gaussian sigma (binned px) and eccentricity of each star from Gaussian-weighted second moments, the weight
    adapted to the star and its effect removed (adaptive moments: neighbours and noise far from the star barely count).
    The weight is kept at least 1 px wide: narrower, the pixel grid takes over for undersampled stars."""
    off = np.arange(-WINDOW, WINDOW + 1)
    patch = resid[ys[:, None, None] + off[None, :, None], xs[:, None, None] + off[None, None, :]].astype(np.float64)
    dy, dx = off[None, :, None].astype(float), off[None, None, :].astype(float)
    n = len(ys)
    w2, cy, cx = np.full(n, 2.0), np.zeros(n), np.zeros(n)
    txx = tyy = txy = np.full(n, np.nan)
    good = np.zeros(n, bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        for _ in range(iterations):
            for centring in (True, False):
                ry, rx = dy - cy[:, None, None], dx - cx[:, None, None]
                wp = np.exp(-(ry ** 2 + rx ** 2) / (2 * w2[:, None, None])) * patch
                m0 = wp.sum(axis=(1, 2))
                m0 = np.where(m0 > 0, m0, np.nan)
                if centring:
                    cy = np.nan_to_num(np.clip(cy + (wp * ry).sum(axis=(1, 2)) / m0, -2, 2))
                    cx = np.nan_to_num(np.clip(cx + (wp * rx).sum(axis=(1, 2)) / m0, -2, 2))
            mxx, myy = (wp * rx ** 2).sum(axis=(1, 2)) / m0, (wp * ry ** 2).sum(axis=(1, 2)) / m0
            mxy = (wp * ry * rx).sum(axis=(1, 2)) / m0
            det = mxx * myy - mxy ** 2                            # star covariance: (M^-1 - I/w2)^-1
            ia, ib, ic = myy / det - 1 / w2, mxx / det - 1 / w2, -mxy / det
            d2 = ia * ib - ic ** 2
            txx, tyy, txy = ib / d2, ia / d2, -ic / d2
            true2 = (txx + tyy) / 2
            good = np.isfinite(true2) & (true2 > 0) & (d2 > 0) & (det > 0)
            w2 = np.where(good, np.clip(true2, 1.0, 16.0), w2)
        half, diff = (txx + tyy) / 2, np.sqrt(((txx - tyy) / 2) ** 2 + txy ** 2)
        ecc = np.sqrt(np.clip(1 - (half - diff) / (half + diff), 0, 1))
    return np.where(good, np.sqrt(np.abs(half)), np.nan), np.where(good, ecc, np.nan)


def _thumbnail(img):
    """Grey preview, long side THUMB_SIDE, stretched so the sky sits at a quarter of full brightness."""
    step = max(1, int(np.ceil(max(img.shape) / THUMB_SIDE)))
    h, w = img.shape[0] // step * step, img.shape[1] // step * step
    small = img[:h, :w].reshape(h // step, step, w // step, step).mean(axis=(1, 3))
    med = float(np.median(small))
    mad = float(np.median(np.abs(small - med))) or 1e-6
    lo, hi = med - 2.8 * mad, float(np.percentile(small, 99.95))
    x = np.clip((small - lo) / max(hi - lo, 1e-6), 0, 1)
    m = _midtones_for((med - lo) / max(hi - lo, 1e-6), 0.25)
    x = (m - 1) * x / ((2 * m - 1) * x - m)                 # midtones transfer function (PixInsight's STF)
    return (np.clip(x, 0, 1) * 255).astype(np.uint8)


def _midtones_for(x, target):
    """Midtones balance that maps x to target."""
    x = min(max(x, 1e-6), 1 - 1e-6)
    return (target - 1) * x / ((2 * target - 1) * x - target)


# ----------------------------------------------------------------------------------------------- the target's set

def _store(d):
    p = Path(d) / STORE
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"frames": {}}


def _frames(d):
    """{name: (path, excluded)} of every light frame, kept or excluded."""
    d = Path(d)
    out = {}
    for base, excluded in ((d / "Light", False), (d / EXCLUDED, True)):
        for p in frameio.frame_files(base):
            out[p.relative_to(base).as_posix()] = (p, excluded)
    return out


def _thumb_path(d, name):
    return Path(d) / THUMBS / (name.replace("/", "__").rsplit(".", 1)[0] + ".jpg")


def analyze(d, workers=None, force=False):
    """Measure every light frame that has no up-to-date measurement (force: every frame). Returns report(d).
    Measurements are saved as they come: Cancel keeps what was measured and stops after the frames in progress."""
    from PIL import Image
    d = Path(d)
    store = _store(d)
    known = store["frames"]
    frames = _frames(d)
    todo = []
    for name, (p, _) in frames.items():
        try:
            st = p.stat()
        except OSError:                                      # moved away meanwhile
            continue
        rec = known.get(name)
        if force or not rec or rec.get("size") != st.st_size or rec.get("mtime") != int(st.st_mtime):
            todo.append((name, p))
    (d / THUMBS).mkdir(parents=True, exist_ok=True)

    def one(name, p):
        try:
            st = p.stat()
            m, thumb = measure(p)
            Image.fromarray(thumb).save(_thumb_path(d, name), quality=82)
            return name, {**m, "size": st.st_size, "mtime": int(st.st_mtime), **_when(p)}
        except (OSError, ValueError) as e:                   # unreadable, or moved away while being measured
            return name, {"error": str(e)}

    pool = ThreadPoolExecutor(max_workers=workers or min(4, os.cpu_count() or 1))
    try:
        futures = [pool.submit(one, name, p) for name, p in todo]
        for i, done in enumerate(as_completed(futures)):
            name, rec = done.result()
            known[name] = rec
            jobctx.emit("frames.progress", index=i, total=len(todo), name=name)
            if i % 20 == 19:
                jsonfile.write(d / STORE, store)
            jobctx.check_cancelled()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)        # on Cancel only the frames in progress finish
        for name in list(known):
            if name not in frames:
                del known[name]
        jsonfile.write(d / STORE, store)
    return report(d)


def _when(p):
    """Exposure and local capture time (what the user saw on the clock that night)."""
    from .organize import local_time
    try:
        h = frameio.header(p)
        when = local_time(p, h).isoformat(timespec="seconds")
    except (OSError, ValueError):
        return {}
    return {"exptime": float(h.get("EXPTIME") or 0) or None, "time": when}


def pixel_scale(d):
    """Arcseconds per native pixel from the lights' header (XPIXSZ and FOCALLEN), None when either is missing."""
    files = frameio.frame_files(Path(d) / "Light")
    if not files:
        return None
    try:
        h = frameio.header(files[0])
    except (OSError, ValueError):
        return None
    px, focal = h.get("XPIXSZ"), h.get("FOCALLEN")
    return round(206.265 * float(px) / float(focal), 4) if px and focal else None


def report(d):
    """{frames: [{name, excluded, thumb, stars, fwhm, ecc, background, flags, ...}], summary, scale, restack}."""
    d = Path(d)
    known = _store(d)["frames"]
    frames = _frames(d)
    scale = pixel_scale(d)
    rows = []
    for name, (p, excluded) in sorted(frames.items(), key=lambda kv: (known.get(kv[0], {}).get("time") or "", kv[0])):
        rec = known.get(name, {})
        fwhm = rec.get("fwhm_px")
        rows.append({"name": name, "path": p.as_posix(), "excluded": excluded, "measured": "stars" in rec,
                     "error": rec.get("error"), "thumb": _thumb_path(d, name).as_posix(),
                     "time": rec.get("time"), "exptime": rec.get("exptime"), "stars": rec.get("stars"),
                     "fwhm": round(fwhm * scale, 2) if fwhm and scale else fwhm, "ecc": rec.get("ecc"),
                     "background": rec.get("background"), "flags": []})
    kept = [r for r in rows if r["measured"] and not r["excluded"]]
    stats = _flag(rows, kept)
    return {"frames": rows, "fwhm_unit": "arcsec" if scale else "px", "scale": scale, "restack": restack_needed(d),
            "summary": {"total": len(rows), "measured": sum(r["measured"] for r in rows),
                        "excluded": sum(r["excluded"] for r in rows),
                        "suspicious": sum(bool(r["flags"]) and not r["excluded"] for r in rows), **stats}}


def restack_needed(d):
    """Frames were excluded or restored after the master was made: it no longer matches the kept frames."""
    master = wbpp.masters(d)
    changed = _store(d).get("changed")
    return bool(master and changed and datetime.fromtimestamp(master[0].stat().st_mtime).isoformat() < changed)


def _flag(rows, kept):
    """Mark frames that stand out from the kept, measured ones; returns the medians."""
    def med(key):
        v = [r[key] for r in kept if r[key] is not None]
        if not v:
            return None, None
        m = float(np.median(v))
        return m, 1.4826 * float(np.median(np.abs(np.array(v) - m)))

    (stars, _), (fwhm, fwhm_sd), (ecc, ecc_sd), (bg, bg_sd) = med("stars"), med("fwhm"), med("ecc"), med("background")
    if len(kept) >= MIN_FRAMES:
        for r in rows:
            if not r["measured"]:
                continue
            if stars and r["stars"] is not None and r["stars"] < FLAG_STARS * stars:
                r["flags"].append(tr("星点只有其他帧的 {share}（云、雾或结露）", share=f"{r['stars'] / stars:.0%}"))
            if fwhm and r["fwhm"] and r["fwhm"] > fwhm + max(3 * fwhm_sd, FLAG_FWHM * fwhm):
                r["flags"].append(tr("星点比其他帧大 {more}（跑焦、视宁度差或有风）", more=f"{r['fwhm'] / fwhm - 1:.0%}"))
            if ecc is not None and r["ecc"] is not None and r["ecc"] > max(FLAG_ECC, ecc + max(3 * ecc_sd, 0.1)):
                r["flags"].append(tr("星点被拉长（跟踪不准或有风）"))
            if bg and r["background"] is not None and r["background"] > bg + max(3 * bg_sd, FLAG_BACKGROUND * bg):
                r["flags"].append(tr("背景比其他帧亮 {more}（月光、云或天亮）", more=f"{r['background'] / bg - 1:.0%}"))
    for r in rows:
        if r["error"]:
            r["flags"].append(tr("读不了这一帧：{error}", error=r["error"]))
    return {"stars": stars, "fwhm": fwhm, "ecc": ecc, "background": bg}


# ----------------------------------------------------------------------------------------------- excluding

def exclude(d, names):
    """Move these frames (names from report()) out of Light/ into Excluded/Light/. Returns how many moved."""
    return _move(Path(d), names, Path(d) / "Light", Path(d) / EXCLUDED)


def restore(d, names):
    """Move excluded frames back into Light/."""
    return _move(Path(d), names, Path(d) / EXCLUDED, Path(d) / "Light")


def _move(d, names, src_root, dst_root):
    moved = 0
    for name in names:
        src = (src_root / name).resolve()
        if not src.is_relative_to(src_root.resolve()) or not src.is_file():
            continue                                         # not one of this target's frames
        dst = dst_root / name
        if dst.exists():
            continue                                         # never overwrite a frame already there
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src, dst)                                  # within the target: one step, nothing copied
        moved += 1
        parent = src.parent
        while parent != src_root.resolve() and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    if moved:
        store = _store(d)
        store["changed"] = datetime.now().isoformat(timespec="seconds")
        jsonfile.write(d / STORE, store)
    return moved
