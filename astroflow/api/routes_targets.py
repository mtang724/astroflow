"""Targets, recipe parameters, the night's filter, their nights and disk space, and the organise plan."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config, jsonfile, multinight, objects, organize, pipeline, settings, storage
from ..services import recipes, targets
from .models import (NightsOut, OrganizeIn, OrganizePlan, ParamIn, PathIn, RecipeIn, SessionIn, Stage, StorageUsage,
                     TargetDetail, TargetSummary)

router = APIRouter(prefix="/api", tags=["targets"])


def _target_dir(path):
    d = Path(path)
    if not d.is_dir():
        raise HTTPException(404, f"no such folder: {path}")
    return d


@router.get("/targets", response_model=list[TargetSummary])
def list_targets():
    return targets.list_targets(extra=settings.get().extra_targets)


@router.get("/targets/detail", response_model=TargetDetail)
def target_detail(path: str):
    return targets.detail(_target_dir(path))


@router.post("/targets/open", response_model=TargetSummary)
def open_target(body: PathIn):
    d = _target_dir(body.path).resolve()
    s = settings.get()
    if config.IN_PROCESSING.resolve() not in d.parents and d.as_posix() not in s.extra_targets:
        s.extra_targets = s.extra_targets + [d.as_posix()]
        settings.save(s)
    return targets.summary(d)


@router.post("/targets/close", response_model=list[TargetSummary])
def close_target(body: PathIn):
    s = settings.get()
    s.extra_targets = [p for p in s.extra_targets if Path(p).resolve() != Path(body.path).resolve()]
    settings.save(s)
    return targets.list_targets(extra=s.extra_targets)


@router.get("/targets/nights", response_model=NightsOut)
def target_nights(path: str):
    """The target's nights in In Processing and its multi-night target (astroflow.multinight)."""
    d = _target_dir(path)
    combined = multinight.combined_dir(d.name)
    own = multinight.info(combined) or {}
    return NightsOut(name=d.name, nights=multinight.candidates(d.name),
                     combined=combined.as_posix() if own else None,
                     included=[n["night"] for n in own.get("nights", [])],
                     missing=[n["night"] for n in own.get("nights", []) if n.get("missing")])


@router.get("/storage", response_model=list[StorageUsage])
def disk_usage():
    """Disk space of every target, most removable first."""
    rows = []
    for t in targets.list_targets(extra=settings.get().extra_targets):
        rows.append({"path": t["path"], "name": t["name"], "night": t["night"], "nights": t["nights"],
                     **storage.usage(t["path"])})
    return sorted(rows, key=lambda r: -r["removable"])


@router.post("/targets/session", response_model=TargetSummary)
def set_session(body: SessionIn):
    """The night's filter (FITS headers do not record it): <night>/session.json, read by recipe choice and references."""
    d = _target_dir(body.path)
    p = objects.session_path(d)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.update({"filter": body.filter, "filter_class": body.filter_class})
    jsonfile.write(p, data)
    return targets.summary(d)


@router.post("/targets/recipe", response_model=TargetSummary)
def choose_recipe(body: RecipeIn):
    """Process the target with this recipe (its type is not in the built-in catalogue, or the automatic choice is not
    wanted). Records of stages run with another recipe are dropped; their files stay."""
    d = _target_dir(body.path)
    if body.recipe not in pipeline.RECIPES:
        raise HTTPException(400, f"no recipe {body.recipe}")
    pipeline.Work(d, body.recipe).use_recipe(body.recipe)
    return targets.summary(d)


@router.get("/recipes", response_model=list[str])
def list_recipes():
    return list(pipeline.RECIPES)


@router.get("/recipes/{name}", response_model=list[Stage])
def recipe(name: str):
    if name not in pipeline.RECIPES:
        raise HTTPException(404, f"no recipe {name}")
    return recipes.spec(name)


def _recipe_of(d):
    r = targets.summary(d)["recipe"]
    if r not in pipeline.RECIPES:
        raise HTTPException(400, f"{d.name}: no recipe for type {targets.summary(d)['type']!r}; choose one")
    return r


@router.get("/params", response_model=list[Stage])
def params(path: str):
    d = _target_dir(path)
    return recipes.effective(_recipe_of(d), d)


@router.put("/params", response_model=list[Stage])
def set_param(body: ParamIn):
    d = _target_dir(body.path)
    recipes.set_field(d, body.stage, body.step_id, body.key, body.value)
    return recipes.effective(_recipe_of(d), d)


@router.delete("/params", response_model=list[Stage])
def reset_params(path: str, stage: str | None = None):
    d = _target_dir(path)
    recipes.reset(d, stage)
    return recipes.effective(_recipe_of(d), d)


@router.post("/organize/plan", response_model=OrganizePlan)
def organize_plan(body: OrganizeIn):
    for s in body.sources or []:
        _target_dir(s)
    plan, notes = organize.build_plan(sources=body.sources)
    return OrganizePlan(rows=organize.summary(plan), imported=organize.imported_counts(plan), notes=notes)
