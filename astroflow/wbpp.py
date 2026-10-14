"""Calibrate, register, integrate (and plate-solve) one target with WBPP's command-line automation mode.

Automation mode does not load the WBPP settings saved in PixInsight: what is not passed here is WBPP's factory default.
Passed: subframe weighting by PSF signal, no local normalization (video ep6: slow, and not reliably better), autocrop.
Frames may be FITS or camera RAW files (PixInsight's RAW module reads them; the folder name tells WBPP their type).
A multi-night target (astroflow.multinight) groups calibration by night with the keyword NIGHT, read from its
NIGHT_<night> folders.

WBPP gets its folders on PixInsight's command line, which garbles anything that is not ASCII; WBPP then finds no frames
and says nothing. A data folder with Chinese characters, or NINA's file names (they contain ℃), would never stack. So on
Windows such frames are hard-linked (no extra space) under an ASCII folder on the same drive, with ASCII names, and
WBPP's Output is moved into the target afterwards.
"""
import glob
import hashlib
import os
import re
import shutil
import sys
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from . import config, dualband, frameio, multinight, pi

FRAME_DIRS = ("Light", "Dark", "Bias", "Flat")   # never pass the target folder itself: WBPP would ingest the JPG thumbnails


def wbpp_args(target_dir, platesolve=True, extra=None, frames_root=None, output=None):
    """frames_root: where the frame folders are (the target, or its ASCII copy: _ascii_input); output: WBPP's output."""
    target_dir = Path(target_dir)
    root = Path(frames_root or target_dir)
    args = ["automationMode=true"]
    for sub in FRAME_DIRS:
        d = root / sub
        if frameio.frame_files(d) or (d.is_dir() and any(d.rglob("*.xisf"))):     # WBPP scans subfolders too
            args.append(f"dir={d.as_posix()}")
    if multinight.is_combined(target_dir):                     # calibrate per night, integrate all together
        kw = f"{multinight.KEYWORD} pre"
        if multinight.has_bands(target_dir):                   # ... or per dual-band filter set (astroflow.dualband)
            kw += f";{dualband.KEYWORD} post"
        args.append(f"keywords={kw}")
    args += [f"outputDirectory={Path(output or target_dir / 'Output').as_posix()}",
             f"platesolve={'true' if platesolve else 'false'}",
             "platesolveFallbackManual=false",
             "frameSelectionInteractive=false",
             "localNormalizationInteractiveMode=false",
             "imageRegistration=true",
             "subframeWeightingEnabled=true",
             "subframesWeightsMethod=0",                # PSF Signal Weight
             "localNormalization=false",
             "integrate=true",
             "autocrop=true"]
    for k, v in (extra or {}).items():
        args.append(f"{k}={str(v).lower() if isinstance(v, bool) else v}")
    return args


def masters(target_dir):
    """Master lights produced by WBPP, autocropped versions first."""
    m = Path(target_dir) / "Output" / "master"
    files = sorted(glob.glob(str(m / "masterLight_*.xisf")))
    crop = [f for f in files if f.endswith("_autocrop.xisf")]
    rest = [f for f in files if f not in crop]
    return [Path(f) for f in crop + rest]


def summarize_log(target_dir):
    """Pull the useful lines out of the newest WBPP log: frame counts, rejections, plate solving, errors."""
    logs = sorted((Path(target_dir) / "Output" / "logs").glob("*.log"))
    if not logs:
        return {"log": None}
    text = logs[-1].read_text(encoding="utf-8", errors="replace")
    keep = re.compile(r"(?i)(error|warning|failed|solved|astrometric|integrat\w* \d+|rejected|active frames|"
                      r"reference frame|master\w* generated|elapsed)")
    lines = [ln.strip() for ln in text.splitlines() if keep.search(ln)]
    return {"log": logs[-1].as_posix(), "highlights": lines[-60:]}


def _frame_paths(target_dir):
    for sub in FRAME_DIRS:
        d = Path(target_dir) / sub
        if d.is_dir():
            yield from (p for p in d.rglob("*") if p.is_file() and (frameio.is_frame(p) or p.suffix.lower() == ".xisf"))


def _ascii_name(name, taken):
    """'..._-10.00℃_...fits' -> '..._-10.00C_...fits'; other characters that have no ASCII form are dropped."""
    stem, ext = os.path.splitext(name)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^\w.\- ]+", "_", stem).strip() or "frame"
    out, i = stem + ext, 1
    while out.lower() in taken:
        out, i = f"{stem}_{i}{ext}", i + 1
    taken.add(out.lower())
    return out


def _stage_root(target_dir):
    """An ASCII folder on the target's drive (hard links only work within one drive)."""
    return Path(Path(target_dir).anchor) / "astroflow-wbpp"


@contextmanager
def _ascii_input(target_dir):
    """(frames_root, output) for WBPP: the target itself when every path is ASCII, else an ASCII copy of its frame
    folders (links), whose Output is moved into the target when WBPP is done."""
    target_dir = Path(target_dir)
    frames = list(_frame_paths(target_dir))
    if sys.platform != "win32" or (str(target_dir).isascii() and all(p.name.isascii() for p in frames)):
        yield target_dir, target_dir / "Output"
        return
    stage = _stage_root(target_dir) / hashlib.sha1(str(target_dir).encode()).hexdigest()[:12]
    shutil.rmtree(stage, ignore_errors=True)        # only ever links and copies made here
    taken = {}
    for p in frames:
        rel = p.relative_to(target_dir)
        folder = stage.joinpath(*(_ascii_name(part, set()) for part in rel.parts[:-1]))
        folder.mkdir(parents=True, exist_ok=True)
        dst = folder / _ascii_name(rel.name, taken.setdefault(folder, set()))
        try:
            os.link(p, dst)
        except OSError:                              # another drive, or a file system without hard links
            shutil.copy2(p, dst)
    try:
        yield stage, stage / "Output"
    finally:
        out = stage / "Output"
        if out.is_dir():
            for src in out.rglob("*"):
                if src.is_file():
                    dst = target_dir / "Output" / src.relative_to(out)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(src, dst)
        shutil.rmtree(stage, ignore_errors=True)


def run(target_dir, platesolve=True, extra=None, timeout=6 * 3600):
    target_dir = Path(target_dir)
    with _ascii_input(target_dir) as (root, output):
        rc, secs = pi.run_script(config.WBPP_JS, wbpp_args(target_dir, platesolve, extra, root, output),
                                 timeout=timeout, idle_limit=1800)   # online plate solving idles while waiting for VizieR
    out = {"returncode": rc, "seconds": round(secs), "masters": [p.as_posix() for p in masters(target_dir)]}
    out.update(summarize_log(target_dir))
    if not out["masters"]:
        raise pi.PIError(f"WBPP produced no master light for {target_dir}. See {out.get('log')}")
    return out
