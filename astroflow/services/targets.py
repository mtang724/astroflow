"""What is on disk: processing targets, their status, previews and finished images.

A target is a folder with Light/ (+ Dark/Bias/Flat) and, once processed, Post/ (state.json, checkpoints, previews,
finals). Targets live in <data root>/In Processing/<night>/<name>; any other folder can be opened as well (the comet
was organised by hand in <data root>/C2025-R3).
"""
import json
from collections import Counter
from pathlib import Path

from .. import config, objects, pipeline, references, wbpp

FINAL_EXTS = (".png", ".jpg", ".tif")


def _state(d):
    sp = Path(d) / "Post" / "state.json"
    return json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}


def _count(d, sub):
    p = Path(d) / sub
    return len(list(p.glob("*.fit*"))) if p.is_dir() else 0


def summary(d):
    """Cheap status for lists (no FITS headers read). master: the recipe's start image exists - for a comet that is
    astroflow.comet's stack on the nucleus (made from WBPP's registered frames), not WBPP's star-aligned master."""
    d = Path(d)
    st = _state(d)
    session = objects.session_info(d)
    recipe, typ = objects.recipe_for(d.name, filter_class=session.get("filter_class"))
    in_staging = d.parent.parent == config.IN_PROCESSING
    if typ == "comet":
        master = (d / "Post" / "comet_stack.fits").exists()
    else:
        master = bool(wbpp.masters(d)) or bool(st.get("master"))
    return {"name": d.name, "path": d.as_posix(), "night": d.parent.name if in_staging else "",
            "lights": _count(d, "Light"), "darks": _count(d, "Dark"), "bias": _count(d, "Bias"),
            "flats": _count(d, "Flat"), "master": master, "registered": _registered(d),
            "type": typ, "recipe": st.get("recipe") or recipe, "stages_done": list((st.get("stages") or {}).keys()),
            "finished": bool(st.get("finished")), "filter_class": session.get("filter_class")}


def _registered(d):
    """WBPP has calibrated and registered the lights (what a comet stack starts from)."""
    folder = Path(d) / "Output" / "registered"
    return folder.is_dir() and any(True for _ in folder.rglob("*.xisf"))


def list_targets(extra=()):
    """Every target under In Processing plus extra folders (opened by the user), newest night first."""
    dirs = [d for d in config.IN_PROCESSING.glob("*/*") if d.is_dir()] if config.IN_PROCESSING.exists() else []
    dirs = sorted(dirs, key=lambda d: (d.parent.name, d.name))
    out = [summary(d) for d in dirs]
    known = {o["path"] for o in out}
    out += [summary(d) for d in map(Path, extra) if d.is_dir() and d.as_posix() not in known]
    return out


def acquisition(d, max_headers=60):
    """Acquisition summary from the light frames' FITS headers."""
    from astropy.io import fits
    lights = sorted((Path(d) / "Light").glob("*.fit*"))
    hdrs = []
    for p in lights[:max_headers]:
        try:
            hdrs.append(fits.getheader(p))
        except (OSError, ValueError):          # a truncated or corrupt frame must not break the target page
            continue
    if not hdrs:
        return {}
    h0 = hdrs[0]
    return {"object": h0.get("OBJECT"), "frames": len(lights),
            "exposures_s": dict(Counter(float(h.get("EXPTIME", 0)) for h in hdrs)),
            "total_h": round(sum(float(h.get("EXPTIME", 0)) for h in hdrs) / 3600, 2),
            "camera": h0.get("INSTRUME"), "gain": h0.get("GAIN"), "offset": h0.get("OFFSET"),
            "set_temp": h0.get("SET-TEMP"), "focal_mm": h0.get("FOCALLEN"), "pixel_um": h0.get("XPIXSZ"),
            "filter": h0.get("FILTER", "none (OSC broadband)"), "bayer": h0.get("BAYERPAT"),
            "date_obs": h0.get("DATE-OBS")}


def calibration_warnings(d):
    manifest = Path(d) / "calibration_manifest.txt"
    if not manifest.exists():
        return []
    return [ln[9:].strip() for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.startswith("WARNING:")]


def stages(d):
    """The recipe's stages with what has run: seconds, previews, overrides used."""
    d = Path(d)
    st = _state(d)
    recipe = st.get("recipe") or summary(d)["recipe"]
    if recipe not in pipeline.RECIPES:
        return []
    done = st.get("stages") or {}
    out = []
    for spec in pipeline.RECIPES[recipe]:
        rec = done.get(spec["stage"])
        out.append({"stage": spec["stage"], "done": rec is not None,
                    "seconds": rec.get("seconds") if rec else None,
                    "previews": [p for p in (rec.get("previews") if rec else []) if Path(p).exists()],
                    "overrides": rec.get("overrides") if rec else None})
    return out


def finals(d):
    post = Path(d) / "Post"
    return sorted(p.as_posix() for p in post.glob(f"{Path(d).name}_*") if p.suffix.lower() in FINAL_EXTS)


def reference_images(d, group=None):
    doc = references.load(Path(d).name) or {}
    groups = [group] if group else ["best", "peer"]
    return [{"group": g, "title": e.get("title"), "author": e.get("author"), "likes": e.get("likes"),
             "url": e.get("url"), "file": e.get("file")}
            for g in groups for e in doc.get(g, []) if e.get("file") and Path(e["file"]).exists()]


def detail(d):
    """Everything a target page shows (reads FITS headers: not for lists)."""
    d = Path(d)
    return {**summary(d), "session": objects.session_info(d), "acquisition": acquisition(d),
            "calibration_warnings": calibration_warnings(d), "catalogue": objects.lookup(d.name),
            "stages": stages(d), "finals": finals(d), "references": reference_images(d),
            "report": (d / "Post" / "report.md").as_posix() if (d / "Post" / "report.md").exists() else None}
