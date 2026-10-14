"""Folders the API acts on. Actions that move, delete or write files only take a target inside the data root or a
folder the user opened in the app (resolved, so '..' cannot lead out of them)."""
from pathlib import Path

from fastapi import HTTPException

from .. import config, settings


def target_dir(path):
    """The target folder `path`: 404 when it does not exist, 403 outside the folders astroflow works in."""
    d = Path(path)
    if not d.is_dir():
        raise HTTPException(404, f"no such folder: {path}")
    real = d.resolve()
    roots = [Path(r).resolve() for r in [config.ASTRO_ROOT, *settings.get().extra_targets]]
    if not any(real == r or r in real.parents for r in roots):
        raise HTTPException(403, "outside the data root and the folders opened in astroflow")
    return d
