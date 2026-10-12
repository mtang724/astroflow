"""Images for the renderer: previews, finals, reference thumbnails. Only files under the data root, the knowledge
base, the PixInsight runs folder or folders the user opened are served; `max` returns a cached JPEG no larger than
that (16-bit TIFF finals are converted, browsers cannot show them)."""
import hashlib
from pathlib import Path

import platformdirs
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config, settings

router = APIRouter(prefix="/api", tags=["files"])

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
BROWSER_EXTS = {".jpg", ".jpeg", ".png"}


def _allowed_roots():
    roots = [config.ASTRO_ROOT, config.KNOWLEDGE, config.RUNS] + [Path(p) for p in settings.get().extra_targets]
    return [r.resolve() for r in roots if r.exists()]


def _check(path):
    p = Path(path).resolve()
    if p.suffix.lower() not in IMAGE_EXTS:
        raise HTTPException(400, "not an image")
    if not any(p == r or r in p.parents for r in _allowed_roots()):
        raise HTTPException(403, "outside the folders astroflow works in")
    if not p.is_file():
        raise HTTPException(404, "no such file")
    return p


def _cache_dir():
    d = Path(platformdirs.user_cache_dir(settings.APP, appauthor=False)) / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _thumbnail(p, max_side):
    st = p.stat()
    key = hashlib.sha1(f"{p}|{st.st_mtime_ns}|{st.st_size}|{max_side}".encode()).hexdigest()
    out = _cache_dir() / f"{key}.jpg"
    if out.exists():
        return out
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    if p.suffix.lower() in (".tif", ".tiff"):
        import numpy as np
        import tifffile
        a = tifffile.imread(p)
        if a.ndim == 3 and a.shape[0] in (3, 4) and a.shape[-1] not in (3, 4):
            a = np.moveaxis(a, 0, -1)
        if a.dtype != np.uint8:
            a = (a.astype(np.float32) / (65535.0 if a.dtype == np.uint16 else max(float(a.max()), 1e-9)) * 255)
            a = a.clip(0, 255).astype(np.uint8)
        im = Image.fromarray(a[..., :3] if a.ndim == 3 else a)
    else:
        im = Image.open(p)
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    im.save(out, "JPEG", quality=90)
    return out


@router.get("/files")
def get_file(path: str, max: int | None = None):
    p = _check(path)
    if max or p.suffix.lower() not in BROWSER_EXTS:
        return FileResponse(_thumbnail(p, max or 4096), media_type="image/jpeg")
    return FileResponse(p)
