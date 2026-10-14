"""One target shot over several nights, stacked as one: each night's lights are calibrated with that night's flats (and
darks), then all of them are registered and integrated together.

The nights stay where the importer put them (In Processing/<night>/<target>). The combined target
In Processing/Multi-night/<target> holds links to their frames, one folder per night:

    Light/NIGHT_2026May17/...   Flat/NIGHT_2026May17/...   Dark/NIGHT_2026May17/... (or Dark/ when every night has the
                                                                                     same darks; Bias likewise)

WBPP reads NIGHT_<value> in a path as the grouping keyword NIGHT. Passed as keywords=NIGHT pre, it makes calibration
frames serve only the lights of their own night (frames without it serve every night) and leaves integration alone, so
all nights end up in one master. Links are hard links where the file system allows them (no extra disk space), copies
elsewhere. Running combine() again brings the target up to date (a night added or removed, frames excluded in a night);
frames excluded in the combined target itself (its Excluded/ folder) stay out. combined.json lists the nights (written
first, so a run cut short still belongs to astroflow).
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from . import config, frameio, jobctx, jsonfile

FOLDER = "Multi-night"           # In Processing/Multi-night/<target>
KEYWORD = "NIGHT"
KINDS = ("Light", "Flat", "Dark", "Bias")
SHARABLE = ("Dark", "Bias")      # one folder for all nights when every night has the same frames


def is_combined(d):
    return (Path(d) / "combined.json").exists()


def info(d):
    """combined.json of a combined target ({nights: [{night, path, lights}], ...}), None for any other folder."""
    p = Path(d) / "combined.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def combined_dir(name):
    return config.IN_PROCESSING / FOLDER / name


def _night_order(night):
    try:
        return datetime.strptime(night, "%Y%b%d").strftime("%Y%m%d")
    except ValueError:
        return night


def candidates(name):
    """The nights of a target in In Processing: [{night, path, lights}], oldest first."""
    root = config.IN_PROCESSING
    if not root.is_dir():
        return []
    out = []
    for night in root.iterdir():
        d = night / name
        if night.name != FOLDER and (d / "Light").is_dir():
            out.append({"night": night.name, "path": d.as_posix(), "lights": len(frameio.frame_files(d / "Light"))})
    return sorted(out, key=lambda n: _night_order(n["night"]))


def combine(nights, log=print):
    """Make the combined target of these night targets (all with the same target name), or bring it up to date.
    Returns its folder.

    Nothing is lost on the way: nights recorded earlier whose folders are gone (archived, deleted) keep their frames
    here, and a frame no longer wanted is only deleted when another copy exists (a hard link, or the same file in a
    night); otherwise it is moved to Excluded/."""
    srcs = sorted((Path(n) for n in nights), key=lambda s: _night_order(s.parent.name))
    names = {s.name for s in srcs}
    if len(srcs) < 2 or len(names) != 1:
        raise ValueError("choose at least two nights of the same target")
    if any(not (s / "Light").is_dir() for s in srcs):
        raise ValueError("every night needs a Light folder")
    dest = combined_dir(names.pop())
    if not is_combined(dest) and any(frameio.frame_files(dest / k) for k in KINDS):
        raise FileExistsError(f"{dest} already holds frames that were not linked there by astroflow")
    previous = (info(dest) or {}).get("nights", [])
    chosen = {s.as_posix() for s in srcs}
    gone = [n for n in previous if n["path"] not in chosen and not Path(n["path"]).is_dir()]
    _write_info(dest, srcs, gone, complete=False)          # first: a run cut short is still recognised as ours
    excluded = dest / "Excluded"
    wanted = {rel: src for rel, src in _layout(srcs).items() if not (excluded / rel).exists()}
    keep = {f"{KEYWORD}_{n['night']}" for n in gone}
    elsewhere = [Path(n["path"]) for n in previous] + srcs
    for kind in KINDS:                                     # frames of nights or files no longer chosen
        for p in frameio.frame_files(dest / kind):
            rel = p.relative_to(dest)
            if rel not in wanted and not (len(rel.parts) > 2 and rel.parts[1] in keep):
                _drop(dest, p, elsewhere, log)
    for i, (rel, src) in enumerate(sorted(wanted.items())):
        if i % 50 == 0:
            jobctx.check_cancelled()
            jobctx.emit("combine.progress", index=i, total=len(wanted))
        _link(src, dest / rel, lambda p: _drop(dest, p, elsewhere, log))
    _prune_empty(dest)
    _write_info(dest, srcs, gone, complete=True)
    _write_session(dest, srcs)
    _write_manifest(dest, srcs)
    log(f"combined {len(srcs)} nights into {dest}" + (f" (kept the frames of {len(gone)} nights no longer on disk)"
                                                     if gone else ""))
    return dest


def _write_info(dest, srcs, gone, complete):
    nights = [{"night": s.parent.name, "path": s.as_posix(), "lights": len(frameio.frame_files(s / "Light"))}
              for s in srcs] + [{**n, "missing": True} for n in gone]
    jsonfile.write(dest / "combined.json", {"nights": sorted(nights, key=lambda n: _night_order(n["night"])),
                                            "complete": complete,
                                            "updated": datetime.now().isoformat(timespec="seconds")})


def _drop(dest, p, nights, log):
    """Take a frame out of the combined target: delete it when another copy exists (a hard link, or the same file in
    one of the nights), else move it to Excluded/ - it may be the last copy."""
    rel = p.relative_to(dest)
    size = p.stat().st_size
    if p.stat().st_nlink > 1 or any((n / rel.parts[0] / p.name).is_file() and
                                    (n / rel.parts[0] / p.name).stat().st_size == size for n in nights):
        p.unlink()
        return
    target = dest / "Excluded" / rel
    while target.exists():
        target = target.with_name(target.stem + "_1" + target.suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(p, target)
    log(f"kept {rel} in Excluded (no other copy of it)")


def _layout(srcs):
    """{path in the combined target: source file} for every frame of these nights."""
    out = {}
    for kind in KINDS:
        per_night = {s: frameio.frame_files(s / kind) for s in srcs}
        shared = kind in SHARABLE and _same_frames(per_night.values())
        for s, files in per_night.items():
            sub = Path(kind) if shared else Path(kind) / f"{KEYWORD}_{s.parent.name}"
            for f in files:
                out[sub / f.relative_to(s / kind)] = f
            if shared:
                break                                        # one copy serves every night
    return out


def _same_frames(sets):
    keys = [{(p.name, p.stat().st_size) for p in files} for files in sets]
    return bool(keys[0]) and all(k == keys[0] for k in keys)


def _link(src, dst, drop):
    """A hard link to src at dst (a copy where the file system has no hard links, e.g. exFAT). A different file already
    at dst is handed to `drop` first."""
    if dst.exists():
        if dst.stat().st_size == src.stat().st_size:
            return
        drop(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        part = dst.with_name(dst.name + ".partial")
        shutil.copy2(src, part)
        os.replace(part, dst)


def _prune_empty(dest):
    for kind in KINDS:
        folder = dest / kind
        for d in [d for d in folder.iterdir() if d.is_dir()] if folder.is_dir() else []:
            if not any(d.iterdir()):
                d.rmdir()


def _write_session(dest, srcs):
    """The filter of the first night that has one recorded (objects.session_info reads it)."""
    for s in srcs:
        p = s.parent / "session.json"
        if p.exists():
            jsonfile.write(dest / "session.json", json.loads(p.read_text(encoding="utf-8")))
            return


def _write_manifest(dest, srcs):
    """The nights' calibration warnings, each marked with its night (services.targets reads the WARNING lines)."""
    lines = []
    for s in srcs:
        m = s / "calibration_manifest.txt"
        if m.exists():
            lines += [f"WARNING: {s.parent.name}：{ln[9:].strip()}" for ln in m.read_text(encoding="utf-8").splitlines()
                      if ln.startswith("WARNING:")]
    (dest / "calibration_manifest.txt").write_text("".join(f"{ln}\n" for ln in lines), encoding="utf-8")
