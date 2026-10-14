"""Checking single frames before stacking: the measurements of a target's light frames, leaving frames out and taking
them back. Measuring is a job (POST /api/actions/frames)."""
from fastapi import APIRouter, HTTPException

from .. import framecheck
from .models import FrameReport, FramesIn
from .paths import target_dir

router = APIRouter(prefix="/api", tags=["frames"])


def _target_dir(path):
    d = target_dir(path)
    if not (d / "Light").is_dir() and not (d / framecheck.EXCLUDED).is_dir():
        raise HTTPException(404, f"no light frames in {path}")
    return d


@router.get("/frames", response_model=FrameReport)
def frames(path: str):
    return framecheck.report(_target_dir(path))


@router.post("/frames/exclude", response_model=FrameReport)
def exclude(body: FramesIn):
    d = _target_dir(body.path)
    framecheck.exclude(d, body.names)
    return framecheck.report(d)


@router.post("/frames/restore", response_model=FrameReport)
def restore(body: FramesIn):
    d = _target_dir(body.path)
    framecheck.restore(d, body.names)
    return framecheck.report(d)
