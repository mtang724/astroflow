"""Pictures for sharing: the finished image cropped to a platform's shape (3:4 for Xiaohongshu, 16:9 for Bilibili ...),
optionally signed and captioned with what was shot and how.

    share.source(target)                    the finished image a share picture starts from
    share.suggest(target)                   default caption lines (object, equipment and integration, date)
    share.render(target, spec, max_side)    the picture as a PIL image (previews pass a small max_side)
    share.export(target, spec)              Post/share/<target>_<shape>_<time>.jpg, returns the path

spec = {"aspect": "3:4", "crop": [x0, y0, x1, y1] (fractions of the image; None: default_crop),
        "signature": "© Ming", "caption": ["M8 礁湖星云", "72 mm · ASI2600MC · 11 × 300 s"]}

Pure Python (Pillow), no PixInsight: an export takes a second or two. Text uses a CJK font of the system.
"""
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import objects, settings
from .i18n import language, tr

ASPECTS = {"3:4": (1620, 2160), "4:5": (1728, 2160), "1:1": (2160, 2160), "16:9": (2560, 1440),
           "original": None}
ORIGINAL_MAX = 4096
FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/Deng.ttf", "C:/Windows/Fonts/simhei.ttf",
         "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
         "/System/Library/Fonts/STHeiti Medium.ttc", "/Library/Fonts/Arial Unicode.ttf",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"]
BOLD_FONTS = ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/Dengb.ttf"]

CHINESE_NAMES = {
    "M1": "蟹状星云", "M8": "礁湖星云", "M13": "武仙座球状星团", "M16": "鹰状星云", "M17": "欧米茄星云",
    "M20": "三叶星云", "M27": "哑铃星云", "M31": "仙女座星系", "M33": "三角座星系", "M42": "猎户座大星云",
    "M44": "蜂巢星团", "M45": "昴星团", "M51": "涡状星系", "M57": "环状星云", "M63": "向日葵星系",
    "M64": "黑眼睛星系", "M74": "幻影星系", "M76": "小哑铃星云", "M81": "波德星系", "M82": "雪茄星系",
    "M83": "南风车星系", "M97": "夜枭星云", "M101": "风车星系", "M104": "草帽星系",
    "NGC246": "骷髅星云", "NGC253": "玉夫座星系", "NGC2237": "玫瑰星云", "NGC4565": "针状星系",
    "NGC6334": "猫爪星云", "NGC6357": "龙虾星云", "NGC6543": "猫眼星云", "NGC6960": "西面纱星云",
    "NGC6992": "东面纱星云", "NGC7000": "北美洲星云", "NGC7023": "鸢尾花星云", "NGC7293": "螺旋星云",
    "IC434": "马头星云", "IC1396": "象鼻星云", "IC1805": "心脏星云", "IC1848": "灵魂星云",
}


def source(target_dir):
    """The newest full-frame final (PNG, else JPG, else TIFF), None before the recipe has finished."""
    post = Path(target_dir) / "Post"
    name = Path(target_dir).name
    for ext in (".png", ".jpg", ".tif"):
        finals = sorted(p for p in post.glob(f"{name}_*{ext}") if "_crop" not in p.stem)
        if finals:
            return finals[-1]
    return None


def suggest(target_dir, acquisition=None, nights=()):
    """Default caption lines: the object, the equipment and integration, the date(s). Never the site."""
    name = Path(target_dir).name
    cat = objects.lookup(name) or {}
    local = (CHINESE_NAMES.get(objects.norm(name)) if language() == "zh" else None) or cat.get("common_name")
    lines = [f"{name} {local}" if local else name]
    a = acquisition or {}
    gear = [_optics(a), a.get("camera")]
    exposures = a.get("exposures_s") or {}
    if exposures:
        parts = [f"{n} × {float(e):g} s" for e, n in sorted(exposures.items(), key=lambda kv: -float(kv[0]))]
        gear.append(" + ".join(parts) + (tr("（{time}）", time=_hours(a["total_h"])) if a.get("total_h") else ""))
    lines.append(" · ".join(str(g) for g in gear if g))
    dates = [_date(n) for n in nights if _date(n)]
    if dates:
        lines.append(dates[0] if len(dates) == 1 else tr("{first} 至 {last}（{n} 晚）", first=dates[0], last=dates[-1],
                                                         n=len(dates)))
    return [ln for ln in lines if ln]


def _hours(h):
    return tr("{n} 分钟", n=round(h * 60)) if h < 1 else tr("{n} 小时", n=f"{h:.1f}".rstrip("0").rstrip("."))


def _optics(a):
    """'72 mm ED refractor' when the frames' focal length is the one in Settings, else the focal length itself."""
    focal = a.get("focal_mm")
    eq = settings.get().equipment
    if focal and eq.get("telescope") and eq.get("focal_mm") and abs(float(focal) - float(eq["focal_mm"])) < 15:
        return eq["telescope"]
    return f"{float(focal):g} mm" if focal else None


def _date(night):
    try:
        return datetime.strptime(night, "%Y%b%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


# ----------------------------------------------------------------------------------------------- rendering

@lru_cache(maxsize=4)
def _load(path, mtime, max_side):
    """The source image as 8-bit RGB, at most max_side (0: full size); cached for repeated previews."""
    Image.MAX_IMAGE_PIXELS = None
    p = Path(path)
    if p.suffix.lower() in (".tif", ".tiff"):
        import numpy as np
        import tifffile
        a = tifffile.imread(p)
        if a.ndim == 3 and a.shape[0] in (3, 4) and a.shape[-1] not in (3, 4):
            a = np.moveaxis(a, 0, -1)
        if a.dtype != np.uint8:
            a = (a.astype(np.float32) / (65535.0 if a.dtype == np.uint16 else max(float(a.max()), 1e-9)) * 255)
        im = Image.fromarray(a.clip(0, 255).astype(np.uint8)[..., :3] if a.ndim == 3 else a.astype(np.uint8))
    else:
        im = Image.open(p)
    im = im.convert("RGB")
    if max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    return im


def source_image(target_dir, max_side=0):
    src = source(target_dir)
    if src is None:
        raise FileNotFoundError("no finished image yet: run the recipe first")
    return _load(str(src), src.stat().st_mtime_ns, max_side)


def default_crop(target_dir, aspect):
    """The crop a share picture starts from (fractions): around the object where the recipe located it, else around
    the brightest, most colourful part of the picture (the nebula or galaxy, not the empty sky)."""
    full = source_image(target_dir)
    w, h = full.size
    state = Path(target_dir) / "Post" / "state.json"
    obj = (json.loads(state.read_text(encoding="utf-8")).get("object") or {}) if state.exists() else {}
    if obj.get("inImage") and obj.get("cx") is not None:
        centre = (obj["cx"], obj["cy"])
    else:
        small = source_image(target_dir, 256)
        cx, cy = _interest_centre(small, aspect)
        centre = (cx * w / small.size[0], cy * h / small.size[1])
    box = crop_box((w, h), aspect, None, centre=centre)
    return [round(box[0] / w, 4), round(box[1] / h, 4), round(box[2] / w, 4), round(box[3] / h, 4)]


def _interest_centre(small, aspect):
    """Centre (pixels of `small`) of the crop of this shape holding the most signal: brightness above the sky plus
    colour, smoothed so the stars spread evenly and only extended light stands out."""
    from scipy import ndimage
    a = np.asarray(small, dtype=np.float32) / 255
    lum = a.mean(axis=2)
    signal = np.clip(lum - np.median(lum), 0, None) + (a.max(axis=2) - a.min(axis=2))
    signal = ndimage.gaussian_filter(signal, max(2.0, min(signal.shape) / 25))
    sh, sw = signal.shape
    x0, y0, x1, y1 = crop_box((sw, sh), aspect)
    bw, bh = x1 - x0, y1 - y0
    integral = np.pad(signal.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    ys, xs = np.arange(sh - bh + 1)[:, None], np.arange(sw - bw + 1)[None, :]
    totals = integral[ys + bh, xs + bw] - integral[ys, xs + bw] - integral[ys + bh, xs] + integral[ys, xs]
    y, x = np.unravel_index(int(np.argmax(totals)), totals.shape)
    return x + bw / 2, y + bh / 2


def crop_box(size, aspect, crop=None, centre=None):
    """Pixel box (x0, y0, x1, y1) in an image of `size`: `crop` (fractions) made to the aspect's shape around its
    centre, or the largest box of that shape around `centre` (default: the middle), kept inside the image."""
    w, h = size
    ratio = _ratio(aspect, size)
    if crop:
        x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in crop)
        cx, cy, bw, bh = (x0 + x1) / 2 * w, (y0 + y1) / 2 * h, max((x1 - x0) * w, 8), max((y1 - y0) * h, 8)
    else:
        (cx, cy), bw, bh = centre or (w / 2, h / 2), w, h
    if bw / bh > ratio:
        bw = bh * ratio
    else:
        bh = bw / ratio
    bw, bh = min(bw, w, h * ratio), min(bh, h, w / ratio)
    x0 = min(max(cx - bw / 2, 0), w - bw)
    y0 = min(max(cy - bh / 2, 0), h - bh)
    return round(x0), round(y0), round(x0 + bw), round(y0 + bh)


def _ratio(aspect, size):
    if ASPECTS.get(aspect):
        ow, oh = ASPECTS[aspect]
        return ow / oh
    return size[0] / size[1]


def output_size(box, aspect):
    """The picture's size: the platform's size, never larger than the cropped pixels (no upscaling)."""
    bw, bh = box[2] - box[0], box[3] - box[1]
    target = ASPECTS.get(aspect)
    if not target:
        scale = min(1.0, ORIGINAL_MAX / max(bw, bh))
    else:
        scale = min(1.0, target[0] / bw, target[1] / bh)
    return max(1, round(bw * scale)), max(1, round(bh * scale))


def render(target_dir, spec, max_side=0):
    """The share picture (PIL RGB). max_side > 0 renders a small preview quickly (same layout, scaled)."""
    full = source_image(target_dir)
    aspect = spec.get("aspect") or "original"
    crop = spec.get("crop") or default_crop(target_dir, aspect)
    box = crop_box(full.size, aspect, crop)
    out_w, out_h = output_size(box, aspect)
    if max_side and max(out_w, out_h) > max_side:
        s = max_side / max(out_w, out_h)
        out_w, out_h = max(1, round(out_w * s)), max(1, round(out_h * s))
        base = source_image(target_dir, 2048)                              # previews: from a cached smaller copy
        f = base.size[0] / full.size[0]
        img = base.crop(tuple(round(v * f) for v in box)).resize((out_w, out_h), Image.LANCZOS)
    else:
        img = full.crop(box).resize((out_w, out_h), Image.LANCZOS)
    return _annotate(img, [ln for ln in spec.get("caption") or [] if ln.strip()], (spec.get("signature") or "").strip())


def _font(size, bold=False):
    for path in (BOLD_FONTS if bold else []) + FONTS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def _annotate(img, caption, signature):
    """Caption lines at the bottom left over a soft shade, the signature at the bottom right."""
    if not caption and not signature:
        return img
    w, h = img.size
    unit = min(w, h)
    margin = round(unit * 0.045)
    sign_font = _font(round(unit * 0.030))
    room = w - 2 * margin - (_text_size(sign_font, signature)[0] + margin if signature else 0)
    lines = _fit(caption[:1], round(unit * 0.046), room, bold=True) + _fit(caption[1:], round(unit * 0.026), room)
    title_font = lines[0][1] if lines else None
    heights = [_text_size(f, t)[1] for t, f in lines]
    gap = round(unit * 0.012)
    block = sum(heights) + gap * max(len(lines) - 1, 0)
    shade_h = min(h, block + 2 * margin + round(unit * 0.08)) if lines else round(unit * 0.16)
    shade = Image.new("L", (1, shade_h))
    shade.putdata([round(150 * (i / max(shade_h - 1, 1)) ** 1.6) for i in range(shade_h)])
    img = img.copy()
    img.paste(Image.new("RGB", (w, shade_h), (0, 0, 0)), (0, h - shade_h), shade.resize((w, shade_h)))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y = h - margin - block
    for (text, font), th in zip(lines, heights, strict=True):
        draw.text((margin, y), text, font=font, fill=(255, 255, 255, 242 if font is title_font else 215))
        y += th + gap
    if signature:
        sw, sh = _text_size(sign_font, signature)
        draw.text((w - margin - sw, h - margin - sh), signature, font=sign_font, fill=(255, 255, 255, 200))
    glow = layer.filter(ImageFilter.GaussianBlur(max(1, unit // 400)))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(glow.getchannel("A").point(lambda a: a * 0.6))
    out = img.convert("RGBA")
    out.alpha_composite(shadow)
    out.alpha_composite(layer)
    return out.convert("RGB")


def _fit(lines, size, room, bold=False):
    """(text, font) per line, each fitting `room` pixels: a long line gets a smaller font (down to 80 %), then is
    broken at its ' · ' separators."""
    out = []
    for line in lines:
        font = _font(size, bold)
        if _text_size(font, line)[0] > room:
            font = _font(max(round(size * max(0.8, room / _text_size(font, line)[0])), 8), bold)
        if _text_size(font, line)[0] <= room or " · " not in line:
            out.append((line, font))
            continue
        current = ""
        for part in line.split(" · "):
            joined = f"{current} · {part}" if current else part
            if current and _text_size(font, joined)[0] > room:
                out.append((current, font))
                current = part
            else:
                current = joined
        out.append((current, font))
    return out


def _text_size(font, text):
    x0, _, x1, y1 = font.getbbox(text)
    return x1 - x0, y1


def export(target_dir, spec):
    """Write the full-size picture to Post/share/ and return its path."""
    img = render(target_dir, spec)
    d = Path(target_dir)
    out_dir = d / "Post" / "share"
    out_dir.mkdir(parents=True, exist_ok=True)
    shape = (spec.get("aspect") or "original").replace(":", "x")
    out = out_dir / f"{d.name}_{shape}_{datetime.now():%Y%m%d-%H%M%S}.jpg"
    img.save(out, "JPEG", quality=94, subsampling=0, optimize=True)
    return out
