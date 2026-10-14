"""The job queue and the actions that create jobs (organise, stack, process, comet stack, crop, references, frame
check, combining nights, processing everything, freeing disk space, archiving)."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .. import framecheck, jobctx, multinight, organize, pipeline, settings, storage, wbpp
from ..i18n import mark, tr
from ..services import actions, targets
from .models import (ArchiveIn, BatchIn, BatchOut, BatchRow, CleanupIn, CombineIn, CometIn, CropIn, FrameCheckIn, Job,
                     JobDetail, Ok, OrganizeIn, PathIn, ProcessIn, ReferencesIn)
from .paths import target_dir

router = APIRouter(prefix="/api", tags=["jobs"])
STEP_NAMES = {"stack": mark("叠加"), "comet": mark("彗星叠加"), "process": mark("处理")}


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

    names = tr("、").join(Path(s).name for s in body.sources or []) or tr("数据根目录")
    return _jobs(request).submit("organize", tr("导入 {what}", what=names), run).public()


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


@router.post("/actions/frames", response_model=Job)
def check_frames(body: FrameCheckIn, request: Request):
    d = target_dir(body.path)

    def run():
        s = framecheck.analyze(d, force=body.force)["summary"]
        return {k: s[k] for k in ("total", "measured", "suspicious")}

    return _jobs(request).submit("frames", tr("{target}: 单帧检查", target=d.name), run, target=d.as_posix()).public()


@router.post("/actions/combine", response_model=Job)
def combine_nights(body: CombineIn, request: Request):
    nights = [target_dir(n) for n in body.nights]
    if len(nights) < 2 or len({n.name for n in nights}) != 1:
        raise HTTPException(400, "choose at least two nights of the same target")
    dest = multinight.combined_dir(nights[0].name)
    return _jobs(request).submit("combine", tr("{target}: 合并 {n} 晚", target=nights[0].name, n=len(nights)),
                                 lambda: {"path": multinight.combine(nights).as_posix()},
                                 target=dest.as_posix()).public()


def _busy(request):
    return {j.target for j in _jobs(request).jobs() if j.state in ("queued", "running")}


@router.get("/batch/plan", response_model=list[BatchRow])
def batch_plan(request: Request):
    """What processing everything would do for each target."""
    busy = _busy(request)
    rows = []
    for t in targets.list_targets(extra=settings.get().extra_targets):
        steps, skip = actions.batch_step(t)
        if t["path"] in busy:
            steps, skip = [], tr("正在处理")
        rows.append({"path": t["path"], "name": t["name"], "night": t["night"], "nights": t["nights"], "steps": steps,
                     "skip": skip})
    return rows


@router.post("/actions/batch", response_model=BatchOut)
def process_all(body: BatchIn, request: Request):
    """One job per target, each doing everything that target still needs (actions.run_all)."""
    busy = _busy(request)
    jobs, skipped = [], []
    for path in body.paths:
        d = target_dir(path)
        t = targets.summary(d)
        steps, skip = actions.batch_step(t)
        if d.as_posix() in busy:
            skip = tr("正在处理")
        if skip:
            skipped.append({"path": t["path"], "name": t["name"], "night": t["night"], "steps": [], "skip": skip})
            continue
        what = " + ".join(tr(STEP_NAMES[s]) for s in steps)
        jobs.append(_jobs(request).submit("process", f"{d.name}: {what}", lambda d=d: actions.run_all(d),
                                          target=d.as_posix()).public())
    return {"jobs": jobs, "skipped": skipped}


@router.post("/actions/cleanup", response_model=Job)
def free_space(body: CleanupIn, request: Request):
    dirs = [target_dir(p) for p in body.paths]
    if not dirs:
        raise HTTPException(400, "no targets chosen")

    def run():
        freed = {}
        for i, d in enumerate(dirs):
            jobctx.emit("cleanup.item", index=i, total=len(dirs), target=d.name)
            freed[d.as_posix()] = storage.clean(d)
        return {"freed": sum(freed.values()), "targets": freed}

    title = tr("清理 {target}", target=dirs[0].name) if len(dirs) == 1 else tr("清理 {n} 个目标", n=len(dirs))
    return _jobs(request).submit("cleanup", title, run, target=dirs[0].as_posix() if len(dirs) == 1 else None).public()


@router.post("/actions/archive", response_model=Job)
def archive(body: ArchiveIn, request: Request):
    d = target_dir(body.path)
    try:
        dest = storage.archive_destination(d)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if dest.exists():
        raise HTTPException(409, tr("{path} 已经存在", path=dest))

    def run():
        freed = storage.clean(d) if body.clean else 0
        return {"path": storage.archive(d).as_posix(), "freed": freed}

    return _jobs(request).submit("archive", tr("{target}: 归档到 Processed", target=d.name), run,
                                 target=d.as_posix()).public()
