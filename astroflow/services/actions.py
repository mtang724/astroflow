"""Processing actions that both the app's API and the agent's tools start. Each runs inside a job (progress and Cancel
through jobctx); the API returns the result as it is, the agent adds its PixInsight budget and reports to the model."""
from pathlib import Path

from .. import comet, objects, pipeline, references


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
