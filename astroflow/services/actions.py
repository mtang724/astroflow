"""Processing actions that both the app's API and the agent's tools start. Each runs inside a job (progress and Cancel
through jobctx); the API returns the result as it is, the agent adds its PixInsight budget and reports to the model."""
from pathlib import Path

from .. import comet, framecheck, multinight, objects, pipeline, references, wbpp
from ..i18n import tr


def comet_stack(target_dir, reuse_sxt=False):
    """Stack a comet target from WBPP's registered frames (astroflow.comet: separate star and nucleus layers, cloud and
    satellite-trail rejection) and make the comet layer the start image of the 'comet' recipe. Returns a summary."""
    d = Path(target_dir)
    post = d / "Post"
    frames = post / "frames"
    if not list(frames.glob("*.fits")):
        comet.convert_registered(d, frames)
    diag = comet.run(frames, post, reuse_sxt=reuse_sxt)
    w = pipeline.Work(d, "comet")
    w.state["master"] = (post / "comet_stack.fits").as_posix()
    w.save()
    return {"frames": [{k: f[k] for k in ("name", "exptime", "relative_weight", "cloud_fraction", "trails")}
                       for f in diag["frames"]],
            "motion": diag["motion"], "white_balance": diag["white_balance"], "stack": diag["stack"],
            "weights_preview": (post / "weights.jpg").as_posix()}


def references_for(target_dir, refresh=False):
    """The target's reference works (AstroBin), fetched when missing, when asked to refresh, or when the cached ones
    were picked for the other kind of night (broadband vs multiband peers)."""
    d = Path(target_dir)
    mode = "multiband" if objects.session_info(d).get("filter_class") == "osc_multiband" else "broadband"
    doc = None if refresh else references.load(d.name)
    if doc is None or doc.get("peer_mode", "broadband") != mode:
        doc = references.fetch(d.name, n=6, fov_radius=1.44, peer=mode)
    return doc


def batch_step(summary):
    """What processing everything would still do for a target (targets.summary): (steps, reason it is skipped).
    Steps: stack (WBPP), comet (the comet stack), process (the recipe's stages not run yet)."""
    restack = summary["master"] and framecheck.restack_needed(summary["path"])   # frames left out since stacking
    if summary["finished"] and not restack:
        return [], tr("已完成")
    if not restack and summary["recipe"] in pipeline.RECIPES and summary["master"] and             {s["stage"] for s in pipeline.RECIPES[summary["recipe"]]} <= set(summary["stages_done"]):
        return [], tr("已出图")
    if not summary["recipe"]:
        return [], tr("认不出是什么天体，先在“处理流程”里选配方")
    combined = multinight.info(multinight.combined_dir(summary["name"])) if summary["night"] else None
    if combined and summary["night"] in [n["night"] for n in combined["nights"]]:
        return [], tr("已合并进多晚目标，处理合并的那个")
    if not summary["master"] and summary["lights"] == 0:
        return [], tr("没有光照帧")
    steps = []
    if summary["type"] == "comet":
        if not summary["master"] or restack:
            steps += ([] if summary["registered"] and not restack else ["stack"]) + ["comet"]
    elif not summary["master"] or restack:
        steps.append("stack")
    return steps + ["process"], None


def run_all(target_dir):
    """Everything a target still needs, in one job: WBPP when there is no master, the comet stack for a comet, then the
    recipe's stages that have not run."""
    d = Path(target_dir)
    from . import targets
    steps, skip = batch_step(targets.summary(d))
    if skip:
        return {"skipped": skip}
    out = {}
    if "stack" in steps:
        out["stack"] = wbpp.run(d)
    if "comet" in steps:
        out["comet"] = comet_stack(d)
    out["stages"] = [r["stage"] for r in pipeline.run(d)]
    return out
