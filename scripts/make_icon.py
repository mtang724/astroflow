"""Draw the app icon (a comet on a night-sky tile): desktop/build/icon.png (electron-builder makes .ico/.icns from it)
and the renderer favicon. Re-run after changing the design: python scripts/make_icon.py"""
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent / "desktop"
S = 1024


def tile():
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    top, bottom = (14, 22, 48), (30, 44, 92)
    for y in range(S):
        t = y / (S - 1)
        grad.paste(tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)) + (255,), (0, y, S, y + 1))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=255)
    bg.paste(grad, (0, 0), mask)
    return bg, mask


def comet(img):
    head = (660, 360)
    angle = math.radians(225)                    # tail towards the upper left (away from the Sun)
    tail = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(tail)
    for i in range(60):                          # widening, fading tail
        f = i / 59
        r = 520 * f
        x, y = head[0] + r * math.cos(angle), head[1] + r * math.sin(angle)
        w = 18 + 120 * f
        a = int(170 * (1 - f) ** 1.6)
        d.ellipse((x - w, y - w, x + w, y + w), fill=(110, 170, 255, a))
    tail = tail.filter(ImageFilter.GaussianBlur(28))
    img.alpha_composite(tail)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((head[0] - 120, head[1] - 120, head[0] + 120, head[1] + 120), fill=(90, 230, 210, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(core).ellipse((head[0] - 46, head[1] - 46, head[0] + 46, head[1] + 46), fill=(235, 255, 250, 255))
    img.alpha_composite(core.filter(ImageFilter.GaussianBlur(6)))


def stars(img):
    d = ImageDraw.Draw(img)
    for x, y, r in ((230, 230, 7), (800, 720, 6), (320, 760, 5), (860, 250, 4), (540, 820, 4), (180, 520, 3)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=(230, 236, 255, 230))


def main():
    img, mask = tile()
    stars(img)
    comet(img)
    img.putalpha(ImageChops.darker(img.getchannel("A"), mask))   # nothing outside the rounded tile
    (ROOT / "build").mkdir(exist_ok=True)
    img.save(ROOT / "build" / "icon.png")
    public = ROOT / "src" / "renderer" / "public"
    public.mkdir(parents=True, exist_ok=True)
    img.resize((256, 256), Image.LANCZOS).save(public / "favicon.png")
    print("wrote", ROOT / "build" / "icon.png", public / "favicon.png")


if __name__ == "__main__":
    main()
