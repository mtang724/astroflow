"""The user's saved styles: a target's parameter edits kept under a name and given to other targets that use the same
recipe (services.presets)."""

from fastapi import APIRouter, HTTPException

from ..services import presets, targets
from .models import Ok, Preset, PresetIn
from .paths import target_dir

router = APIRouter(prefix="/api", tags=["presets"])


def _recipe(path):
    d = target_dir(path)
    recipe = targets.summary(d)["recipe"]
    if not recipe:
        raise HTTPException(400, "choose a recipe for this target first")
    return d, recipe


@router.get("/presets", response_model=list[Preset])
def list_presets(recipe: str | None = None):
    return presets.list_presets(recipe)


@router.post("/presets", response_model=Preset)
def save_preset(body: PresetIn):
    d, recipe = _recipe(body.path)
    try:
        return presets.save(body.name, d, recipe)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/presets/apply", response_model=Ok)
def apply_preset(body: PresetIn):
    d, recipe = _recipe(body.path)
    try:
        presets.apply(body.name, d, recipe)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return Ok()


@router.delete("/presets", response_model=Ok)
def delete_preset(name: str):
    presets.delete(name)
    return Ok()
