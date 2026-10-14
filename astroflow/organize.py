"""Import a night's raw frames into the workspace, each target with the calibration frames it needs.

Frames are recognised by their headers, so any capture program and any folder layout works (ASIAIR, NINA, SharpCap,
Ekos, a memory card, or a target folder that already holds Light/Dark/Bias/Flat), and so do a camera's own RAW files
(CR2, CR3, NEF, ARW, DNG, RAF ...: astroflow.frameio): the frame type comes from IMAGETYP (else from the file or folder
name; RAW files never record it), the target from OBJECT (else the folder name), the night from the capture time (local
time minus 12 h, so frames after midnight stay with the evening). Lights are grouped by target and night into

    <data root>/In Processing/<YYYYMonDD>/<Target>/{Light,Dark,Bias,Flat}

and each group gets its calibration frames from the imported folders first (frames shot with the data), else from the
calibration library under the data root ("Dark Library", "Bias Library", "Flat"; any layout inside):

    darks   same camera, sensor size, binning, gain (ISO for DSLRs), offset and exposure; same cooling set-point
            (within 1 °C, the closest wins). Without temperature data (DSLR, uncooled camera) darks of the same night
            are preferred.
    bias    same camera, size, binning, gain and offset (set-point as for darks)
    flats   same camera, size, binning and filter, shot the same night (any gain: flats are often taken at another
            ISO), with their dark flats if there are any (WBPP reads dark flats as darks)

Calibration frames imported on their own (e.g. darks shot later) go to the library, and the targets in In Processing
that lack such frames get them. Processing products (WBPP Output, Post, masters) and ASIAIR previews are never
imported. Calibration frames are always copied (one set can serve several targets); lights are copied or moved.

    python -m astroflow.organize --source <folder> [--apply] [--copy]   # import a folder (dry run without --apply)
    python -m astroflow.organize [--apply]                              # new folders put in the data root
    python -m astroflow.organize --refresh [--apply]                    # give staged targets matching library frames
"""
import argparse
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astropy.io import fits

from . import config, frameio, jobctx, multinight
from .i18n import mark, tr

FOLDER = {"light": "Light", "dark": "Dark", "darkflat": "Dark", "bias": "Bias", "flat": "Flat"}
IMAGETYP = {"light": "Light", "dark": "Dark", "darkflat": "Dark Flat", "bias": "Bias", "flat": "Flat"}
PRODUCT_DIRS = {"output", "calibrated", "registered", "debayered", "cosmetized", "master", "masters", "logs",
                "fastintegration", "post", "thumbnails", "previews", "metrics"}
TEMP_TOLERANCE = 1.0          # °C between set-points; 0.5 °C changes IMX571 dark current by only ~6 %
SENSOR_TEMP_TOLERANCE = 3.0   # °C between measured sensor temperatures, when no set-point was recorded
ROTATOR_WARN_DEG = 3
ORIGIN_LABEL = {"import": mark("随数据"), "library": mark("校准帧库"), "target": mark("目标已有")}


def root():
    return config.ASTRO_ROOT


def staging():
    return config.ASTRO_ROOT / "In Processing"


def libraries():
    r = config.ASTRO_ROOT
    return {"darks": r / "Dark Library", "bias": r / "Bias Library", "flats": r / "Flat"}


def session_name(night):
    return f"{night.year}{night.strftime('%b')}{night.day:02d}"


# ----------------------------------------------------------------------------------------------- reading frames

_NAME_TYPES = [(re.compile(r"^(dark[\s_-]?flats?|flat[\s_-]?darks?)(?![a-z])"), "darkflat"),
               (re.compile(r"^lights?(?![a-z])"), "light"),
               (re.compile(r"^darks?(?![a-z])"), "dark"),
               (re.compile(r"^flats?(?![a-z])"), "flat"),
               (re.compile(r"^(bias(es)?|offsets?)(?![a-z])"), "bias")]


def type_from_keyword(value):
    """IMAGETYP / FRAME values of any capture program ('Light', 'LIGHT', 'Light Frame', 'Flat Field', 'DARKFLAT',
    'Flat Dark', 'Bias Frame', 'Offset' ...) -> light | dark | flat | bias | darkflat, or None."""
    v = re.sub(r"[\s_-]+", "", str(value or "")).lower()
    if "dark" in v and "flat" in v:
        return "darkflat"
    for word, kind in (("flat", "flat"), ("dark", "dark"), ("bias", "bias"), ("offset", "bias"), ("zero", "bias"),
                       ("light", "light"), ("science", "light"), ("object", "light")):
        if word in v:
            return kind
    return None


def type_from_name(name):
    """A file or folder name that starts with a frame type: Light_M51_..., Darks, DARKFLAT, bias-001 ... (not
    'Flatiron')."""
    n = name.lower()
    return next((kind for pattern, kind in _NAME_TYPES if pattern.match(n)), None)


def _first(h, *keys):
    for k in keys:
        v = h.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return None


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _value(v):
    """Header values compared for equality (GAIN 100 and 100.0, ISO '3200' and 3200 are the same)."""
    f = _float(v)
    return f if f is not None else (str(v).strip() if v is not None else None)


def local_time(path, h):
    """Local capture time: from the file name (ASIAIR and NINA write local time there), DATE-LOC, else the UTC DATE-OBS
    shifted by the site's longitude (solar time) or, without one, by this computer's time zone."""
    name = Path(path).name
    m = re.search(r"(?<!\d)(\d{8})-(\d{6})(?!\d)", name)                          # ASIAIR: _20250427-223309_
    if m:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    m = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[_T ](\d{2})-(\d{2})-(\d{2})(?!\d)", name)   # NINA: 2024-01-05_21-33-12
    if m:
        return datetime(*map(int, m.groups()))
    if _first(h, "DATE-LOC"):
        return datetime.fromisoformat(str(h["DATE-LOC"]).strip()[:19])
    if _first(h, "DATE-OBS"):
        utc = datetime.fromisoformat(str(h["DATE-OBS"]).strip()[:19])
        lon = _float(h.get("SITELONG"))
        if lon is not None:
            return utc + timedelta(hours=lon / 15)
        return utc.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    raise ValueError("no capture time (file name, DATE-LOC or DATE-OBS)")


def read_meta(path):
    """What matching needs from one frame's header (FITS, or a RAW file's EXIF); "type" is None when it does not say."""
    path = Path(path)
    h = frameio.header(path)
    imagetyp = str(_first(h, "IMAGETYP", "FRAME", "FRAMETYP") or "")
    gain, iso = _first(h, "GAIN"), _first(h, "ISO", "ISOSPEED")
    m = {"path": path,
         "type": type_from_keyword(imagetyp),
         "master": "master" in imagetyp.lower() or path.name.lower().startswith("master"),
         "object": str(_first(h, "OBJECT") or "").strip(),
         "exptime": _float(_first(h, "EXPTIME", "EXPOSURE")) or 0.0,
         "gain": _value(gain if gain is not None else iso),
         "iso": gain is None and iso is not None,
         "offset": _value(_first(h, "OFFSET")),
         "settemp": _float(_first(h, "SET-TEMP", "SET_TEMP", "SETTEMP")),
         "ccdtemp": _float(_first(h, "CCD-TEMP", "CCD_TEMP", "CCDTEMP", "TEMPERAT")),
         "bin": int(_float(_first(h, "XBINNING")) or 1),
         "size": (h.get("NAXIS1"), h.get("NAXIS2")),
         "camera": str(_first(h, "INSTRUME") or "").strip(),
         "filter": str(_first(h, "FILTER") or "").strip() or None,
         "rotator": _float(_first(h, "ROTATOR", "ROTATANG"))}
    m["typed_by_header"] = m["type"] is not None
    m["local_time"] = local_time(path, h)
    m["night"] = (m["local_time"] - timedelta(hours=12)).date()
    return m


def _product_dir(name):
    n = name.lower()
    return n.startswith(".") or n in PRODUCT_DIRS or n.endswith(".pxiproject")


def scan(folder, skip=(), origin="import"):
    """Raw frames under `folder` (any depth) -> (frames, notes). Processing products, masters, ASIAIR previews and the
    `skip` folders are left out; a frame whose header has no type gets it from its file or folder name."""
    folder = Path(folder)
    skip = {Path(s).resolve() for s in skip}
    frames, unreadable, untyped, previews = [], [], [], 0
    for dirpath, dirnames, filenames in os.walk(folder):
        d = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames if not _product_dir(n) and (d / n).resolve() not in skip)
        for name in sorted(filenames):
            p = d / name
            if not frameio.is_frame(p):
                continue
            if name.lower().startswith("preview_"):
                previews += 1
                continue
            try:
                m = read_meta(p)
            except (OSError, ValueError, TypeError) as e:    # truncated file, no capture time ...
                unreadable.append(f"{p.name}（{e}）")
                continue
            if m["master"]:
                continue
            m["type"] = m["type"] or type_from_name(p.name) or _type_from_folders(p, folder)
            if m["type"] is None:
                untyped.append(p.name)
                continue
            m["root"], m["origin"] = folder, origin
            frames.append(m)
    notes = []
    if unreadable:
        notes.append(tr("{n} 个文件读不了：{files}", n=len(unreadable), files=_some(unreadable)))
    if untyped:
        notes.append(tr("{n} 个文件看不出是光照帧还是校准帧（文件头没有 IMAGETYP，文件名和文件夹名也看不出）：{files}",
                        n=len(untyped), files=_some(untyped)))
    if previews:
        notes.append(tr("跳过了 {n} 张 ASIAIR 预览图（Preview_*）", n=previews))
    return frames, notes


def _some(names):
    """The first few names of a list, for a note."""
    return tr("，").join(names[:5]) + (" …" if len(names) > 5 else "")


def _type_from_folders(path, top):
    for d in [path.parent, *path.parent.parents]:
        kind = type_from_name(d.name)
        if kind or d == top:
            return kind
    return None


_GENERIC_DIR = re.compile(r"^(autorun|plan|preview|live|captures?|sharpcap captures|images?|data|raw|"
                          r"\d{4}-?\d{2}-?\d{2}.*|\d{4}[a-z]{3}\d{2})$", re.I)


def target_of(m):
    """Folder-safe target name: OBJECT ('M 51' -> 'M51'), else the nearest folder that is not a frame type or a date."""
    name = m["object"]
    if not name:
        for d in [m["path"].parent, *m["path"].parent.parents]:
            if type_from_name(d.name) is None and not _GENERIC_DIR.match(d.name):
                name = d.name
                break
            if d == m["root"]:
                break
    name = re.sub(r"^M\s+(\d+)$", r"M\1", name.strip())
    return re.sub(r'[<>:"/\\|?*]', "", name).strip(" .") or "Unknown"


# ----------------------------------------------------------------------------------------------- matching

def _same_sensor(a, b, gain=True):
    if (a["camera"], a["size"], a["bin"]) != (b["camera"], b["size"], b["bin"]):
        return False
    return not gain or (a["gain"], a["offset"]) == (b["gain"], b["offset"])


def _same_exposure(a, b):
    return abs(a["exptime"] - b["exptime"]) <= max(0.01, 0.01 * a["exptime"])


def _temp_gap(ref, cal):
    """(difference, tolerance) of the temperatures that decide dark current, or (None, None) without data."""
    if ref["settemp"] is not None and cal["settemp"] is not None:
        return abs(ref["settemp"] - cal["settemp"]), TEMP_TOLERANCE
    if ref["ccdtemp"] is not None and cal["ccdtemp"] is not None:
        return abs(ref["ccdtemp"] - cal["ccdtemp"]), SENSOR_TEMP_TOLERANCE
    return None, None


def _temp_of(m):
    return m["settemp"] if m["settemp"] is not None else m["ccdtemp"]


def _closest(ref, frames):
    """Frames at the temperature closest to the reference light's (within tolerance; an exact set-point beats a near
    one). Without temperature data, those of the same night if there are any."""
    usable, gaps = [], []
    for c in frames:
        gap, tol = _temp_gap(ref, c)
        if gap is None or gap <= tol:
            usable.append(c)
            gaps.append(gap)
    if not usable:
        return []
    if all(gap is None for gap in gaps):
        same_night = [c for c in usable if c["night"] == ref["night"]]
        return same_night or usable
    best = min(gap for gap in gaps if gap is not None)
    return [c for c, gap in zip(usable, gaps, strict=True) if gap == best]


def _everything(ref, frames):
    return frames


def _dark_for(ref, c):
    return c["type"] == "dark" and _same_sensor(ref, c) and _same_exposure(ref, c)


def _bias_for(ref, c):
    return c["type"] == "bias" and _same_sensor(ref, c)


def _flat_for(ref, c):
    return (c["type"] == "flat" and _same_sensor(ref, c, gain=False) and c["filter"] == ref["filter"]
            and c["night"] == ref["night"])


def _darkflat_for(flat, c):
    return c["type"] == "darkflat" and _same_sensor(flat, c) and _same_exposure(flat, c)


def _first_match(sources, ref, test, choose):
    """Matching frames from the first source that has any: the imported folders come before the library."""
    for frames in sources:
        hit = choose(ref, [c for c in frames if test(ref, c)])
        if hit:
            return hit
    return []


def _distinct(frames, keys):
    """One representative frame per combination of `keys`."""
    seen = {}
    for m in frames:
        seen.setdefault(tuple(round(m[k], 3) if k == "exptime" else m[k] for k in keys), m)
    return list(seen.values())


def match_calibration(lights, sources):
    """The darks, bias and flats a group of lights needs, from `sources` (lists of frames, best first).
    Returns ({"darks": [...], "bias": [...], "flats": [...]}, warnings)."""
    found = {"darks": [], "bias": [], "flats": []}
    warnings = []
    for ref in _distinct(lights, ("camera", "size", "bin", "gain", "offset", "exptime", "settemp")):
        darks = _first_match(sources, ref, _dark_for, _closest)
        gap = _temp_gap(ref, darks[0])[0] if darks else None
        if not darks:
            warnings.append(tr("缺少暗场：{need}", need=_need(ref, exposure=True)))
        elif gap:
            warnings.append(tr("暗场 {dark} °C，光照帧 {light} °C（在 {tolerance} °C 容差内）",
                               dark=f"{_temp_of(darks[0]):g}", light=f"{_temp_of(ref):g}", tolerance=f"{TEMP_TOLERANCE:g}"))
        elif gap is None and darks[0]["night"] != ref["night"]:
            warnings.append(tr("相机没有记录温度，暗场是 {night} 拍的，不是同一晚，可能不完全匹配", night=darks[0]["night"]))
        found["darks"] += darks
    flat_sets = []
    for ref in _distinct(lights, ("camera", "size", "bin", "filter")):
        flats = _first_match(sources, ref, _flat_for, _everything)
        if not flats:
            warnings.append(tr("缺少这一晚的平场：{night}，滤镜 {filter}", night=ref["night"], filter=ref["filter"])
                            if ref["filter"] else tr("缺少这一晚的平场：{night}", night=ref["night"]))
        found["flats"] += flats
        flat_sets += _distinct(flats, ("camera", "size", "bin", "gain", "offset", "exptime"))
    dark_flats = [c for f in flat_sets for c in _first_match(sources, f, _darkflat_for, _closest)]
    found["darks"] += dark_flats
    for ref in _distinct(lights, ("camera", "size", "bin", "gain", "offset", "settemp")):
        bias = _first_match(sources, ref, _bias_for, _closest)
        if not bias and not dark_flats:
            warnings.append(tr("缺少偏置：{need}", need=_need(ref)))
        found["bias"] += bias
    light_rot = {lt["rotator"] for lt in lights if lt["rotator"] is not None}
    flat_rot = {f["rotator"] for f in found["flats"] if f["rotator"] is not None}
    if light_rot and flat_rot and max(abs(a - b) for a in light_rot for b in flat_rot) > ROTATOR_WARN_DEG:
        warnings.append(tr("平场和光照帧的旋转角度不同：光照帧 {lights}，平场 {flats}", lights=sorted(light_rot),
                           flats=sorted(flat_rot)))
    return {k: list({m["path"]: m for m in v}.values()) for k, v in found.items()}, warnings


# ----------------------------------------------------------------------------------------------- planning

def build_plan(sources=None, refresh=False):
    """Plan an import of `sources` (folders; default: new folders put in the data root). refresh=True instead gives the
    targets already in In Processing the library frames they lack (their lights stay put).

    Returns (plan, notes). Plan items: {kind: target (a new target) | fill (an existing target gets calibration
    frames) | library (calibration frames for the library), target, night, dest, lights, darks, bias, flats,
    warnings, lights_in_place}; notes: remarks about files that were not used."""
    library, notes = [], []
    for folder in libraries().values():
        if folder.is_dir():
            frames, n = scan(folder, origin="library")
            library += [m for m in frames if m["type"] != "light"]
            notes += n
    if refresh:
        return _complete_staged(library), notes

    managed = [staging(), config.PROCESSED, *libraries().values()]
    frames = []
    for src in sources or [root()]:
        found, n = scan(src, skip=managed)
        frames += found
        notes += n
    lights = [m for m in frames if m["type"] == "light"]
    calibration = [m for m in frames if m["type"] != "light"]

    plan = []
    groups = defaultdict(list)
    for m in lights:
        groups[(m["night"], target_of(m))].append(m)
    for (night, target), group in sorted(groups.items()):
        matched, warnings = match_calibration(group, [calibration, library])
        plan.append({"kind": "target", "target": target, "night": str(night),
                     "dest": staging() / session_name(night) / target, "lights": group, **matched,
                     "warnings": warnings, "lights_in_place": False})
    if lights:
        used = {m["path"] for it in plan for k in ("darks", "bias", "flats") for m in it[k]}
        unused = [m for m in calibration if m["path"] not in used]
        if unused:
            notes.append(tr("导入的文件夹里有 {frames} 没有用上（没有和它们相配的光照帧）", frames=describe(unused)))
    elif calibration:
        new = [m for m in calibration if not _in_library(m["path"])]     # importing the library itself adds nothing
        if new:
            plan.append(_library_item(new))
        plan += _complete_staged(calibration)
    if not frames:
        notes.append(tr("没有找到可用的图像（FITS 或相机 RAW 文件）"))
    return plan, notes


def staged_targets():
    """Night targets in In Processing (not multi-night ones: those link to their nights' frames)."""
    return sorted(d for d in staging().glob("*/*") if (d / "Light").is_dir() and not multinight.is_combined(d))


def _complete_staged(candidates):
    """Items giving targets in In Processing what they lack from `candidates`; their own frames keep priority."""
    plan = []
    for d in staged_targets():
        lights = [m for m in scan(d / "Light", origin="target")[0] if m["type"] == "light"]
        if not lights:
            continue
        own = [m for sub in ("Dark", "Bias", "Flat") if (d / sub).is_dir()
               for m in scan(d / sub, origin="target")[0] if m["type"] != "light"]
        matched, warnings = match_calibration(lights, [own, candidates])
        if any(m["origin"] != "target" for k in ("darks", "bias", "flats") for m in matched[k]):
            plan.append({"kind": "fill", "target": d.name, "night": str(lights[0]["night"]), "dest": d,
                         "lights": lights, **matched, "warnings": warnings, "lights_in_place": True})
    return plan


def _in_library(path):
    p = Path(path).resolve()
    return any(p.is_relative_to(lib.resolve()) for lib in libraries().values())


def _library_item(frames):
    nights = sorted({str(m["night"]) for m in frames})
    return {"kind": "library", "target": tr("校准帧库"), "night": nights[0] if len(nights) == 1 else f"{nights[0]} – {nights[-1]}",
            "dest": root(), "lights": [], "darks": [m for m in frames if m["type"] in ("dark", "darkflat")],
            "bias": [m for m in frames if m["type"] == "bias"], "flats": [m for m in frames if m["type"] == "flat"],
            "warnings": [], "lights_in_place": True}


def _library_dir(m):
    """Where a calibration frame goes in the library (the folder names are only for people; matching reads headers)."""
    lib = libraries()
    temp = f"{m['settemp']:g}degree" if m["settemp"] is not None else session_name(m["night"])
    if m["type"] in ("dark", "darkflat"):
        return lib["darks"] / f"{m['exptime']:g}s" / temp
    if m["type"] == "bias":
        return lib["bias"] / temp
    return lib["flats"] / session_name(m["night"])


def _destination(item, m):
    if item["kind"] == "library":
        return _library_dir(m) / m["path"].name
    return Path(item["dest"]) / FOLDER[m["type"]] / m["path"].name


def _to_copy(item):
    frames = [m for k in ("darks", "bias", "flats") for m in item[k] if m["origin"] != "target"]
    frames += [] if item["lights_in_place"] else item["lights"]
    return sum(1 for m in frames if not _destination(item, m).exists())


# ----------------------------------------------------------------------------------------------- describing

def _exposure_text(e):
    return f"{e:g} s" if e >= 1 else f"{e * 1000:.0f} ms"


def _gain_text(m):
    if m["gain"] is None:
        return ""
    g = f"{m['gain']:g}" if isinstance(m["gain"], float) else m["gain"]
    return f"ISO {g}" if m["iso"] else tr("增益 {gain}", gain=g)


def _need(ref, exposure=False):
    parts = [_exposure_text(ref["exptime"]) if exposure else "", _gain_text(ref),
             f"{ref['settemp']:g} °C" if ref["settemp"] is not None else ""]
    return tr("、").join(p for p in parts if p) or tr("这台相机")


def describe(frames):
    """'12 × 300 s · ISO 3200', one part per kind of frame (exposure, gain, set-point, filter)."""
    counts = defaultdict(int)
    for m in frames:
        temp = f"{m['settemp']:g} °C" if m["settemp"] is not None else ""
        counts[(round(m["exptime"], 4), _gain_text(m), temp, m["filter"] or "")] += 1
    return tr("，").join(" · ".join(p for p in (f"{n} × {_exposure_text(e)}", g, t, f) if p)
                    for (e, g, t, f), n in sorted(counts.items())) or "-"


def _frame_set(frames):
    origins = {m["origin"] for m in frames}
    return {"count": len(frames), "detail": describe(frames),
            "origin": origins.pop() if len(origins) == 1 else ("mixed" if origins else "")}


def summary(plan):
    """Plain rows for display (the desktop app's import table, the agent)."""
    rows = []
    for it in plan:
        sources = {m["path"].parent.as_posix() for k in ("lights", "darks", "bias", "flats") for m in it[k]
                   if m["origin"] == "import"}
        rows.append({"kind": it["kind"], "target": it["target"], "night": it["night"],
                     "dest": Path(it["dest"]).as_posix(), "exists": Path(it["dest"]).is_dir(),
                     "sources": sorted(sources),
                     **{k: _frame_set(it[k]) for k in ("lights", "darks", "bias", "flats")},
                     "to_copy": _to_copy(it), "warnings": it["warnings"]})
    return rows


def imported_counts(plan):
    """How many frames of each kind the plan takes from the imported folders (one calibration frame may serve
    several targets: counted once)."""
    return {k: len({m["path"] for it in plan for m in it[k] if m["origin"] == "import"})
            for k in ("lights", "darks", "bias", "flats")}


def print_plan(plan, notes):
    kinds = {"target": tr("新目标"), "fill": tr("补全已有目标"), "library": tr("加入校准帧库")}
    for row in summary(plan):
        print("\n=== " + tr("{kind}：{target}  {night}  -> {dest}  （要复制 {n} 个文件）", kind=kinds[row["kind"]],
                                target=row["target"], night=row["night"], dest=row["dest"], n=row["to_copy"]))
        for key, label in (("lights", mark("光照帧")), ("darks", mark("暗场")), ("bias", mark("偏置")),
                           ("flats", mark("平场"))):
            fs = row[key]
            origin = tr(ORIGIN_LABEL[fs["origin"]]) if fs["origin"] in ORIGIN_LABEL else \
                tr("多处") if fs["origin"] == "mixed" else ""
            print(f"  {tr(label)}：{fs['detail']}" + (f"（{origin}）" if origin else ""))
        for w in row["warnings"]:
            print(f"  !! {w}")
    for n in notes:
        print("\n" + tr("（注意）{note}", note=n))


# ----------------------------------------------------------------------------------------------- carrying out

def copy_or_move(src, dst_dir, move, imagetyp=None):
    """Copy (or move) a file into dst_dir. A copy is written as <name>.partial and renamed when complete, so an import
    cut short (Cancel, app closed, card pulled) never leaves a truncated frame under the real name. imagetyp: write it
    into the copy's header (the original lacks one; WBPP sorts frames by it). RAW files cannot take one: WBPP reads
    their type from the folder name (Light, Dark, Flat, Bias)."""
    if imagetyp and frameio.is_raw(src):
        imagetyp = None
    jobctx.check_cancelled()
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.resolve() == src.resolve():   # already in place: never "move" a file onto itself (would unlink it)
        return
    if dst.exists():
        if imagetyp or dst.stat().st_size == src.stat().st_size:
            if move:
                src.unlink()
            return
        raise FileExistsError(f"{dst} exists with a different size")
    if move and not imagetyp:
        try:
            os.rename(src, dst)          # same drive: instant and atomic
            return
        except OSError:
            pass                         # another drive: copy, then delete the original
    part = dst.with_name(dst.stem + ".partial")
    if imagetyp:
        with fits.open(src) as hd:
            hd[0].header["IMAGETYP"] = imagetyp
            hd.writeto(part, overwrite=True)
    else:
        shutil.copy2(src, part)
    os.replace(part, dst)
    if move:
        src.unlink()


def apply_plan(plan, move_lights=True, log=print):
    """Carry out the plan. move_lights=False copies the lights instead (importing from a card or network share);
    calibration frames are always copied."""
    for i, item in enumerate(plan):
        jobctx.check_cancelled()
        log(f"{item['kind']}: {item['target']} -> {item['dest']}")
        jobctx.emit("organize.item", index=i, total=len(plan), target=item["target"],
                    dest=Path(item["dest"]).as_posix())
        for key in ("darks", "bias", "flats"):
            for m in item[key]:
                if m["origin"] != "target":
                    copy_or_move(m["path"], _destination(item, m).parent, move=False, imagetyp=_imagetyp_fix(m))
        if not item["lights_in_place"]:
            for m in item["lights"]:
                copy_or_move(m["path"], Path(item["dest"]) / "Light", move=move_lights, imagetyp=_imagetyp_fix(m))
                thumb = m["path"].with_name(m["path"].stem + "_thn.jpg")
                if thumb.exists():
                    copy_or_move(thumb, Path(item["dest"]) / "Thumbnails", move=move_lights)
        if item["kind"] != "library":
            _write_manifest(item)
    if move_lights:
        for src in {m["path"].parent for it in plan if not it["lights_in_place"] for m in it["lights"]}:
            if src.exists() and not any(src.iterdir()):
                src.rmdir()
                log(f"Removed empty {src}")


def _imagetyp_fix(m):
    return None if m["typed_by_header"] else IMAGETYP[m["type"]]


def _write_manifest(item):
    """calibration_manifest.txt: what the target was given and what is missing (read by services.targets)."""
    with open(Path(item["dest"]) / "calibration_manifest.txt", "w", encoding="utf-8") as f:
        for key in ("lights", "darks", "bias", "flats"):
            f.write(f"[{key}]\n")
            for m in item[key]:
                f.write(f"{m['path'].name}\texp={m['exptime']:g}\tset={m['settemp']}\tccd={m['ccdtemp']}"
                        f"\tfrom={m['origin']}\n")
        for w in item["warnings"]:
            f.write(f"WARNING: {w}\n")


def main():
    if hasattr(sys.stdout, "reconfigure"):          # the plan is Chinese: never crash on a non-UTF-8 console
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="carry out the plan (default is a dry run)")
    ap.add_argument("--refresh", action="store_true",
                    help="give targets already in 'In Processing' the library frames they lack (lights stay put)")
    ap.add_argument("--source", action="append", help="folder to import (default: the data root); repeatable")
    ap.add_argument("--copy", action="store_true", help="copy lights instead of moving them")
    args = ap.parse_args()
    plan, notes = build_plan(sources=args.source, refresh=args.refresh)
    print_plan(plan, notes)
    if args.apply:
        apply_plan(plan, move_lights=not args.copy)
    else:
        print("\nDry run only. Re-run with --apply to execute.")


if __name__ == "__main__":
    sys.exit(main())
