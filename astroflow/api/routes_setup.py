"""Setup check: which components are missing on this computer and how to install them (astroflow.doctor)."""
import copy
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import doctor, settings
from ..i18n import tr
from .models import PathIn, SetupReport

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("", response_model=SetupReport)
def report():
    return doctor.run()


@router.post("/data-root", response_model=SetupReport)
def create_data_root(body: PathIn):
    """Create the data folder (with In Processing and Processed) and make it the data root."""
    path = Path(body.path.strip()).expanduser()
    if not path.is_absolute():
        raise HTTPException(400, tr("需要完整路径：{path}", path=body.path))
    try:
        for sub in ("In Processing", "Processed"):
            (path / sub).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(400, tr("没能创建 {path}：{error}", path=path, error=e.strerror or e)) from None
    s = copy.deepcopy(settings.get())
    s.astro_root = str(path)
    settings.save(s)
    return doctor.run()
