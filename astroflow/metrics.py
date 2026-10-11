"""Numeric diagnostics of an image, used by the agent to judge each stage and to compare against references.

Works on the downsampled 16-bit TIFFs the PJSR runner writes (`metrics` outputs) and on ordinary
8-bit JPG/PNG files (reference images, final exports). Values are in [0, 1].
"""
import colorsys
from pathlib import Path

import numpy as np


def load(path):
    path = Path(path)
    if path.suffix.lower() in (".tif", ".tiff"):
        import tifffile
        a = tifffile.imread(str(path))
    else:
        from PIL import Image
        a = np.asarray(Image.open(path).convert("RGB"))
    a = np.asarray(a)
    if a.ndim == 3 and a.shape[0] in (1, 3) and a.shape[-1] not in (1, 3):
        a = np.moveaxis(a, 0, -1)          # planar -> interleaved
    if a.ndim == 2:
        a = a[..., None]
    scale = 65535.0 if a.dtype == np.uint16 else (255.0 if a.dtype == np.uint8 else 1.0)
    return a.astype(np.float32) / scale


def _lum(a):
    if a.shape[-1] == 1:
        return a[..., 0]
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def _tiles(img2d, nx=16, ny=10):
    h, w = img2d.shape
    ys = np.linspace(0, h, ny + 1, dtype=int)
    xs = np.linspace(0, w, nx + 1, dtype=int)
    return np.array([[np.median(img2d[ys[j]:ys[j + 1], xs[i]:xs[i + 1]]) for i in range(nx)] for j in range(ny)])


def _hf_noise(img2d):
    """Robust sigma of the high-frequency residual (pixel minus its 3x3 neighbourhood mean)."""
    k = (img2d[:-2, :-2] + img2d[:-2, 1:-1] + img2d[:-2, 2:] + img2d[1:-1, :-2] + img2d[1:-1, 2:] +
         img2d[2:, :-2] + img2d[2:, 1:-1] + img2d[2:, 2:]) / 8.0
    r = img2d[1:-1, 1:-1] - k
    return float(1.4826 * np.median(np.abs(r - np.median(r))) / np.sqrt(1 + 1 / 8))


def analyze(path, linear=None):
    a = load(path)
    lum = _lum(a)
    out = {"file": str(path), "shape": list(a.shape)}
    ch = ["R", "G", "B"][:a.shape[-1]]
    out["median"] = {c: round(float(np.median(a[..., i])), 5) for i, c in enumerate(ch)}
    out["p99_9"] = {c: round(float(np.percentile(a[..., i], 99.9)), 4) for i, c in enumerate(ch)}
    out["clip_low_pct"] = round(float((a.min(axis=-1) <= 1 / 65535).mean() * 100), 3)
    out["clip_high_pct"] = round(float((a.max(axis=-1) >= 0.999).mean() * 100), 3)

    t = _tiles(lum)
    bg_level = float(np.percentile(t, 10))
    out["background_level"] = round(bg_level, 5)
    span = float(np.percentile(t, 90) - np.percentile(t, 10))
    out["tile_spread_p90_p10"] = round(span, 5)

    # background = darkest 25% of pixels by local brightness, away from stars
    thr = np.percentile(lum, 25)
    bg = lum <= thr
    noise = _hf_noise(lum)
    out["noise_hf"] = round(noise, 6)
    out["bg_snr_proxy"] = round(bg_level / noise, 2) if noise > 0 else None
    if a.shape[-1] == 3:
        bg_rgb = [float(np.median(a[..., i][bg])) for i in range(3)]
        g = bg_rgb[1] if bg_rgb[1] > 0 else 1e-6
        out["background_rgb"] = [round(v, 5) for v in bg_rgb]
        out["background_cast"] = {"R/G": round(bg_rgb[0] / g, 3), "B/G": round(bg_rgb[2] / g, 3)}

        # signal = brighter than background by a margin; describe its colour
        sig = lum > np.percentile(lum, 80)
        sub = a[sig]
        if len(sub) > 50000:
            sub = sub[np.random.default_rng(0).choice(len(sub), 50000, replace=False)]
        hsv = np.array([colorsys.rgb_to_hsv(*px) for px in sub])
        sat = hsv[:, 1]
        out["signal_saturation_mean"] = round(float(sat.mean()), 3)
        out["signal_saturation_p90"] = round(float(np.percentile(sat, 90)), 3)
        w = sat * hsv[:, 2]
        hist, _ = np.histogram(hsv[:, 0], bins=12, range=(0, 1), weights=w)
        hist = hist / hist.sum() if hist.sum() > 0 else hist
        names = ["red", "orange", "yellow", "chartreuse", "green", "spring", "cyan", "azure", "blue", "violet",
                 "magenta", "rose"]
        out["signal_hue_mix"] = {n: round(float(v), 3) for n, v in zip(names, hist, strict=True) if v >= 0.03}
        bg_sat = np.array([colorsys.rgb_to_hsv(*px)[1] for px in a[bg][::max(1, bg.sum() // 20000)]])
        out["background_saturation_mean"] = round(float(bg_sat.mean()), 3)
    out["contrast_p99_p10"] = round(float(np.percentile(lum, 99) - np.percentile(lum, 10)), 4)
    out["lum_median"] = round(float(np.median(lum)), 4)
    if linear is not None:
        out["linear"] = linear
    return out


def compare(ours, refs):
    """Differences between our (nonlinear) metrics and the median of reference metrics."""
    keys = ["background_level", "lum_median", "contrast_p99_p10", "signal_saturation_mean", "background_saturation_mean"]
    out = {}
    for k in keys:
        vals = [r[k] for r in refs if r.get(k) is not None]
        if vals and ours.get(k) is not None:
            ref = float(np.median(vals))
            out[k] = {"ours": ours[k], "refs_median": round(ref, 4), "delta": round(ours[k] - ref, 4)}
    hues = {}
    for r in refs:
        for h, v in (r.get("signal_hue_mix") or {}).items():
            hues.setdefault(h, []).append(v)
    out["ref_hue_mix"] = {h: round(float(np.mean(v)), 3) for h, v in hues.items() if np.mean(v) >= 0.05}
    out["our_hue_mix"] = ours.get("signal_hue_mix")
    return out


def summarize(fps):
    """Median fingerprint of a group of reference images (plus their average hue mix)."""
    if not fps:
        return {}
    keys = ["background_level", "lum_median", "contrast_p99_p10", "signal_saturation_mean",
            "background_saturation_mean", "noise_hf"]
    out = {k: round(float(np.median([f[k] for f in fps if f.get(k) is not None])), 4)
           for k in keys if any(f.get(k) is not None for f in fps)}
    hues = {}
    for f in fps:
        for h, v in (f.get("signal_hue_mix") or {}).items():
            hues[h] = hues.get(h, 0) + v / len(fps)
    out["hue_mix"] = {h: round(v, 3) for h, v in sorted(hues.items(), key=lambda kv: -kv[1])[:5]}
    out["n"] = len(fps)
    return out


# ----------------------------------------------------------------------------- perceptual colour of the subject

def _lab(a):
    """sRGB-encoded float RGB (0..1) -> CIE L*, a*, b* (D65)."""
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], dtype=np.float32)
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return 116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])


def subject_chroma(path, region=None, max_side=1200):
    """How colourful the subject is: Lab chroma C* (perceived saturation), robust to stars, white cores and framing.

    Stars are removed with a median filter. Pixels considered: brighter than the 70th luminance percentile (or, with
    region=(cx, cy, r) as fractions of width/height/width, inside that circle and above its median) and below the
    99.5th (cores). `chroma` is the 90th percentile of C* there - the most colourful part of the nebula/galaxy - so a
    background-dominated selection (wide framing, star field) does not pull it down; `chroma_med` is the median."""
    from PIL import Image, ImageFilter
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_side, max_side))
    im = im.filter(ImageFilter.MedianFilter(5 if max(im.size) >= 1000 else 3))
    a = np.asarray(im).astype(np.float32) / 255.0
    L, A, B = _lab(a)
    C = np.hypot(A, B)
    if region:
        h, w = L.shape
        yy, xx = np.mgrid[0:h, 0:w]
        inside = (xx - region[0] * w) ** 2 + (yy - region[1] * h) ** 2 <= (region[2] * w) ** 2
        Lin = L[inside]
        sel = inside & (L >= np.percentile(Lin, 50)) & (L <= np.percentile(Lin, 99.5))
    else:
        sel = (L >= np.percentile(L, 70)) & (L <= np.percentile(L, 99.5))
    if sel.sum() < 50:
        return {"chroma": None, "chroma_med": None}
    return {"chroma": round(float(np.percentile(C[sel], 90)), 1), "chroma_med": round(float(np.median(C[sel])), 1),
            "lightness_med": round(float(np.median(L[sel])), 1)}
