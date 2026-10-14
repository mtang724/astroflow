"""Pictures for sharing (astroflow.share): suggested caption and crops, quick previews while the user edits, export."""
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .. import settings, share
from ..i18n import tr
from ..services import targets
from .models import ShareInfo, ShareOut, ShareSpec
from .paths import target_dir

router = APIRouter(prefix="/api/share", tags=["share"])
PREVIEW_SIDE = 1100


def _target_dir(path):
    d = target_dir(path)
    if share.source(d) is None:
        raise HTTPException(400, tr("这个目标还没有成品图"))
    return d


def _spec(body):
    return {"aspect": body.aspect, "crop": body.crop, "caption": body.caption, "signature": body.signature}


@router.get("/info", response_model=ShareInfo)
def info(path: str):
    d = target_dir(path)
    src = share.source(d)
    if src is None:
        return ShareInfo(source=None)
    w, h = share.source_image(d).size
    summary = targets.summary(d)
    return ShareInfo(source=src.as_posix(), width=w, height=h,
                     caption=share.suggest(d, targets.acquisition(d), summary["nights"]),
                     signature=settings.get().preferences.get("share_signature", ""),
                     crops={a: share.default_crop(d, a) for a in share.ASPECTS})


@router.post("/preview")
def preview(body: ShareSpec):
    img = share.render(_target_dir(body.path), _spec(body), max_side=PREVIEW_SIDE)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/export", response_model=ShareOut)
def export(body: ShareSpec):
    out = share.export(_target_dir(body.path), _spec(body))
    s = settings.get()
    if s.preferences.get("share_signature", "") != body.signature:      # offered again next time
        s.preferences = {**s.preferences, "share_signature": body.signature}
        settings.save(s)
    from PIL import Image
    with Image.open(out) as im:
        w, h = im.size
    return ShareOut(file=out.as_posix(), width=w, height=h)
