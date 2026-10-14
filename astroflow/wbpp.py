"""Calibrate, register, integrate (and plate-solve) one target with WBPP's command-line automation mode.

Settings not passed here come from the user's last WBPP session (Settings persisted by PixInsight). Frames may be FITS
or camera RAW files (PixInsight's RAW module reads them; the folder name tells WBPP their type). A multi-night target
(astroflow.multinight) groups calibration by night with the keyword NIGHT, read from its NIGHT_<night> folders.
"""
import glob
import re
from pathlib import Path

from . import config, frameio, multinight, pi

FRAME_DIRS = ("Light", "Dark", "Bias", "Flat")   # never pass the target folder itself: WBPP would ingest the JPG thumbnails


def wbpp_args(target_dir, platesolve=True, extra=None):
    target_dir = Path(target_dir)
    args = ["automationMode=true"]
    for sub in FRAME_DIRS:
        d = target_dir / sub
        if frameio.frame_files(d) or (d.is_dir() and any(d.rglob("*.xisf"))):     # WBPP scans subfolders too
            args.append(f"dir={d.as_posix()}")
    if multinight.is_combined(target_dir):
        args.append(f"keywords={multinight.KEYWORD} pre")       # calibrate per night, integrate all together
    args += [f"outputDirectory={(target_dir / 'Output').as_posix()}",
             f"platesolve={'true' if platesolve else 'false'}",
             "platesolveFallbackManual=false",
             "frameSelectionInteractive=false",
             "localNormalizationInteractiveMode=false",
             "imageRegistration=true",
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


def run(target_dir, platesolve=True, extra=None, timeout=6 * 3600):
    target_dir = Path(target_dir)
    rc, secs = pi.run_script(config.WBPP_JS, wbpp_args(target_dir, platesolve, extra), timeout=timeout,
                             idle_limit=1800)   # online plate solving idles while waiting for VizieR
    out = {"returncode": rc, "seconds": round(secs), "masters": [p.as_posix() for p in masters(target_dir)]}
    out.update(summarize_log(target_dir))
    if not out["masters"]:
        raise pi.PIError(f"WBPP produced no master light for {target_dir}. See {out.get('log')}")
    return out
