"""How much disk a target takes, freeing what can be made again, and archiving a finished target to Processed.

A target's space by part (usage):

    frames        Light / Dark / Flat / Bias           the raw data: never removed here (a multi-night target's are
                                                       links to its nights' frames: they take no space of their own)
    masters       the rest of Output                   WBPP's master frames and logs, and anything else kept there
    wbpp_frames   WBPP's single-frame folders           calibrated, cosmetized, debayered, measured, registered:
                                                       removable (WBPP makes them again)
    checkpoints   Post/<stage output>.xisf             every stage's result but the last: removable (pipeline.run
                  (comets also Post/frames, Post/work)  re-runs the stages that made a missing input)
    results       the rest of Post                     finals, previews, metrics, state, share images

Removable parts are only those WBPP or a recipe makes again from what is kept, found by name (never anything else a
user or another program put in Output). A comet's registered frames are always kept: the comet stack is made from them.
"""
import json
import os
import shutil
from pathlib import Path

from . import config, jobctx, jsonfile, multinight, objects, pipeline

FRAME_DIRS = ("Light", "Dark", "Flat", "Bias")
WBPP_FOLDERS = {"calibrated", "cosmetized", "debayered", "measured", "registered", "ldd_lps", "fastintegration"}
REMOVABLE = ("wbpp_frames", "checkpoints")
FINAL_OUTPUT = "50_final"                      # every recipe's last stage writes it; crops and shares start from it


def _checkpoint_names():
    names = {s[k] for stages in pipeline.RECIPES.values() for s in stages for k in ("output", "stars_output") if k in s}
    return {f"{n}.xisf" for n in names - {FINAL_OUTPUT}}


def _size(path, own_only=False):
    """(bytes, files) of a file or a folder tree; own_only: leaving out files hard-linked from elsewhere."""
    p = Path(path)
    if p.is_file():
        return p.stat().st_size, 1
    total = files = 0
    for dirpath, _, filenames in os.walk(p):
        for name in filenames:
            try:
                st = os.stat(os.path.join(dirpath, name))
            except OSError:
                continue
            files += 1
            if not (own_only and st.st_nlink > 1):
                total += st.st_size
    return total, files


def _is_comet(d):
    return objects.recipe_for(Path(d).name)[1] == "comet"


def removable_paths(d):
    """{part: [paths]} that clean() would delete."""
    d = Path(d)
    out = {"wbpp_frames": [], "checkpoints": []}
    output = d / "Output"
    if output.is_dir():
        folders = WBPP_FOLDERS - ({"registered"} if _is_comet(d) else set())
        out["wbpp_frames"] = sorted(p for p in output.iterdir() if p.is_dir() and p.name.lower() in folders)
    post = d / "Post"
    if post.is_dir():
        names = _checkpoint_names()
        out["checkpoints"] = sorted(p for p in post.iterdir() if p.is_file() and p.name in names)
        if (post / "comet_stack.fits").exists():
            out["checkpoints"] += [post / n for n in ("frames", "work") if (post / n).is_dir()]
    return out


def usage(d):
    """{total, removable, parts: [{id, bytes, files, removable}]} of one target."""
    d = Path(d)
    rem = removable_paths(d)
    parts = {k: [0, 0] for k in ("frames", "masters", "wbpp_frames", "checkpoints", "results")}

    linked = multinight.is_combined(d)

    def add(part, path):
        b, n = _size(path, own_only=linked and part == "frames")
        parts[part][0] += b
        parts[part][1] += n

    for sub in FRAME_DIRS:
        if (d / sub).exists():
            add("frames", d / sub)
    for part, paths in rem.items():
        for p in paths:
            add(part, p)
    removed = {p for paths in rem.values() for p in paths}
    output, post = d / "Output", d / "Post"
    for p in output.iterdir() if output.is_dir() else []:
        if p not in removed:
            add("masters", p)
    for p in post.iterdir() if post.is_dir() else []:
        if p not in removed:
            add("results", p)
    rows = [{"id": k, "bytes": b, "files": n, "removable": k in REMOVABLE} for k, (b, n) in parts.items()]
    return {"total": sum(r["bytes"] for r in rows), "removable": sum(r["bytes"] for r in rows if r["removable"]),
            "parts": rows}


def clean(d, parts=REMOVABLE, log=print):
    """Delete the removable parts of a target; returns the bytes freed."""
    freed = 0
    for part, paths in removable_paths(d).items():
        if part not in parts:
            continue
        for p in paths:
            jobctx.check_cancelled()
            freed += _size(p)[0]
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            log(f"removed {p}")
    return freed


# ----------------------------------------------------------------------------------------------- archiving

def archive_destination(d):
    """Processed/<night>/<target> for In Processing/<night>/<target> (multi-night targets: Processed/Multi-night/...)."""
    d = Path(d)
    if d.parent.parent.resolve() != config.IN_PROCESSING.resolve():
        raise ValueError(f"{d} is not in In Processing")
    return config.PROCESSED / d.parent.name / d.name


def archive(d, log=print):
    """Move a target from In Processing to Processed (same night folder), keeping its night's filter record and
    pointing its processing records at the new place. Returns the new folder."""
    d = Path(d)
    dest = archive_destination(d)
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    night = d.parent
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = night / "session.json"
    if session.exists() and not (dest.parent / "session.json").exists():
        shutil.copy2(session, dest.parent / "session.json")
    jobctx.check_cancelled()
    try:
        os.rename(d, dest)                            # one step on the same drive: never a half-copied target
    except OSError as e:
        raise OSError(f"could not move {d} (a file in it may be open in PixInsight or another program): {e}") from e
    _relocate_records(dest, d, dest)
    if night.name != multinight.FOLDER and not any(p.is_dir() for p in night.iterdir()):
        session.unlink(missing_ok=True)               # the last target of that night: nothing left to describe
        if not any(night.iterdir()):
            night.rmdir()
    log(f"archived {d} -> {dest}")
    return dest


def _relocate_records(target, old, new):
    """Paths in Post/state.json (master, previews, saved files) follow the moved folder."""
    state = Path(target) / "Post" / "state.json"
    if not state.exists():
        return
    old_p, new_p = Path(old).as_posix(), Path(new).as_posix()

    def fix(v):
        if isinstance(v, str) and (v == old_p or v.startswith(old_p + "/")):
            return new_p + v[len(old_p):]
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        if isinstance(v, list):
            return [fix(x) for x in v]
        return v

    jsonfile.write(state, fix(json.loads(state.read_text(encoding="utf-8"))))
