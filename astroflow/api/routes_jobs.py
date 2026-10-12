"""The job queue and the actions that create jobs (organise, stack, process, comet stack, crop, references)."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .. import organize, pipeline, wbpp
from ..services import actions
from .models import CometIn, CropIn, Job, JobDetail, Ok, OrganizeIn, PathIn, ProcessIn, ReferencesIn

router = APIRouter(prefix="/api", tags=["jobs"])


def _jobs(request):
    return request.app.state.services.jobs


def _dir(path):
    d = Path(path)
    if not d.is_dir():
        raise HTTPException(404, f"no such folder: {path}")
    return d


def _jsonable(x):
    try:
        return json.loads(json.dumps(x, default=str))
    except (TypeError, ValueError):
        return str(x)


@router.get("/jobs", response_model=list[Job])
def list_jobs(request: Request):
    return [j.public() for j in _jobs(request).jobs()]


@router.get("/jobs/{job_id}", response_model=JobDetail)
def job_detail(job_id: str, request: Request):
    job = _jobs(request).get(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    return {**job.public(), "log": list(job.log), "result": _jsonable(job.result)}


@router.post("/jobs/{job_id}/cancel", response_model=Ok)
def cancel_job(job_id: str, request: Request):
    return Ok(ok=_jobs(request).cancel(job_id))


@router.post("/actions/process", response_model=Job)
def process(body: ProcessIn, request: Request):
    d = _dir(body.path)

    def run():                       # the user's saved parameter edits apply (pipeline.saved_overrides)
        recs = pipeline.run(d, body.recipe, body.start, body.stage)
        return [{"stage": r["stage"], "seconds": r["seconds"], "previews": r.get("previews", [])} for r in recs]

    what = f"stage {body.stage}" if body.stage else f"from {body.start}" if body.start else "pipeline"
    return _jobs(request).submit("process", f"{d.name}: {what}", run, target=d.as_posix()).public()


@router.post("/actions/stack", response_model=Job)
def stack(body: PathIn, request: Request):
    d = _dir(body.path)
    return _jobs(request).submit("stack", f"{d.name}: WBPP", lambda: wbpp.run(d), target=d.as_posix()).public()


@router.post("/actions/comet", response_model=Job)
def comet_stack(body: CometIn, request: Request):
    d = _dir(body.path)
    return _jobs(request).submit("comet", f"{d.name}: comet stack",
                                 lambda: actions.comet_stack(d, reuse_sxt=body.reuse_sxt),
                                 target=d.as_posix()).public()


@router.post("/actions/organize", response_model=Job)
def organize_apply(body: OrganizeIn, request: Request):
    for s in body.sources or []:
        _dir(s)

    def run():
        plan, _ = organize.build_plan(sources=body.sources)
        organize.apply_plan(plan, move_lights=not body.copy_lights)
        return organize.summary(plan)

    return _jobs(request).submit("organize", "导入 " + ("、".join(Path(s).name for s in body.sources or []) or "数据根目录"),
                                 run).public()


@router.post("/actions/crop", response_model=Job)
def crop(body: CropIn, request: Request):
    d = _dir(body.path)
    center = (body.cx, body.cy) if body.cx is not None and body.cy is not None else None
    return _jobs(request).submit("export", f"{d.name}: crop {body.width}x{body.height}",
                                 lambda: pipeline.export_crop(d, body.width, body.height, center=center),
                                 target=d.as_posix()).public()


@router.post("/actions/references", response_model=Job)
def fetch_references(body: ReferencesIn, request: Request):
    d = _dir(body.path)

    def run():
        doc = actions.references_for(d, refresh=body.refresh)
        return {"peer_mode": doc.get("peer_mode"), **{g: len(doc.get(g, [])) for g in ("best", "peer")}}

    return _jobs(request).submit("references", f"{d.name}: references", run, target=d.as_posix()).public()
