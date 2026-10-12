"""Import freshly shot darks (e.g. from the ASIAIR share) into the Dark Library, optionally waiting for them,
then re-match calibration, stack and process the targets that were waiting for them.

    python -m astroflow.darks --source "\\\\<asiair-ip>\\EMMC Images\\Autorun\\Dark" --exptime 300 --settemp -10 \\
                              --count 10 --since 2026-10-10 --wait --then process

--then: none | organize (organize --refresh --apply) | stack (+ WBPP for targets without a master)
        | restack (+ WBPP again for targets whose Dark folder grew) | process (+ DeepSeek agent on newly stacked)
Run it from PowerShell: SMB shares mounted in the user's session are not visible to Git-Bash-launched processes.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from astropy.io import fits

from . import config

def dark_library():
    return config.ASTRO_ROOT / "Dark Library"


def candidates(source, exptime, settemp, gain=100, offset=50, since=None, tol=1.0):
    out = []
    for p in sorted(Path(source).glob("Dark_*.fit*")):
        if p.name.endswith("_thn.jpg"):
            continue
        st = p.stat()
        if since and datetime.fromtimestamp(st.st_mtime).date() < since:
            continue
        if time.time() - st.st_mtime < 30:      # still being written
            continue
        try:
            h = fits.getheader(p)
        except Exception:
            continue                            # partial file
        if abs(float(h.get("EXPTIME", 0)) - exptime) > 0.01:
            continue
        if h.get("SET-TEMP") is None or abs(float(h["SET-TEMP"]) - settemp) > tol:
            continue
        if h.get("GAIN") != gain or h.get("OFFSET") != offset:
            continue
        out.append(p)
    return out


def _stats(path):
    import numpy as np
    d = fits.getdata(path).astype("float32")
    return float(np.median(d)), float(np.percentile(d, 99.9))


def dark_like(dirs, exptime, settemp, reference, gain=100, offset=50, since=None, tol=1.0):
    """Frames saved as Light (e.g. the ASIAIR plan was switched with the cap still on) whose pixel statistics
    match real darks of the same settings. reference: list of real dark paths to compare against."""
    if not reference:
        return []
    ref = [_stats(p) for p in reference[-3:]]
    med = sum(r[0] for r in ref) / len(ref)
    p999 = sum(r[1] for r in ref) / len(ref)
    out = []
    for d in dirs:
        for p in sorted(Path(d).glob("Light_*.fit*")):
            st = p.stat()
            if since and datetime.fromtimestamp(st.st_mtime).date() < since:
                continue
            if time.time() - st.st_mtime < 30:
                continue
            try:
                h = fits.getheader(p)
                if abs(float(h.get("EXPTIME", 0)) - exptime) > 0.01 or h.get("SET-TEMP") is None \
                        or abs(float(h["SET-TEMP"]) - settemp) > tol or h.get("GAIN") != gain or h.get("OFFSET") != offset:
                    continue
                m, q = _stats(p)
            except Exception:
                continue
            if abs(m - med) <= 0.02 * med and q <= 1.2 * p999:     # no light reached the sensor
                out.append(p)
    return out


def library_dir(exptime, settemp):
    return dark_library() / f"{exptime:g}s" / f"{settemp:g}degree"


def import_darks(files, dest):
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in files:
        relabel = p.name.startswith("Light_")
        name = ("Dark_" + p.name.split("_", 2)[2]) if relabel else p.name   # Light_<obj>_300.0s_... -> Dark_300.0s_...
        d = dest / name
        if d.exists():
            continue
        if relabel:
            # the copy gets IMAGETYP=Dark so WBPP/organize classify it correctly; the original stays untouched
            with fits.open(p) as hd:
                hd[0].header["IMAGETYP"] = "Dark"
                hd[0].header["OBJECT"] = ""
                hd[0].header.add_history(f"astroflow: relabelled from Light ({p.name}): dark-like statistics, cap on")
                hd.writeto(d)
        else:
            shutil.copy2(p, d)
        copied.append(d.name)
    return copied


def _py(*args):
    return subprocess.run([sys.executable, *args], cwd=str(config.PROJECT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--exptime", type=float, required=True)
    ap.add_argument("--settemp", type=float, required=True)
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--since", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    ap.add_argument("--wait", action="store_true", help="poll every minute until --count frames exist (max 4 h)")
    ap.add_argument("--dark-like", action="append", default=[],
                    help="also accept Light_* frames in this folder whose statistics match the real darks (repeatable)")
    ap.add_argument("--then", choices=["none", "organize", "stack", "restack", "process"], default="none",
                    help="restack = also re-run WBPP for targets that already have a master but just got more darks")
    a = ap.parse_args(argv)

    t0 = time.time()
    while True:
        files = candidates(a.source, a.exptime, a.settemp, since=a.since)
        extra = dark_like(a.dark_like, a.exptime, a.settemp, files, since=a.since) if a.dark_like else []
        files = files + extra
        print(f"[{time.strftime('%H:%M:%S')}] {len(files)}/{a.count} matching darks ({len(extra)} saved as Light)", flush=True)
        if len(files) >= a.count or not a.wait:
            break
        if time.time() - t0 > 4 * 3600:
            print("gave up waiting", flush=True)
            return 1
        time.sleep(60)
    if len(files) < a.count:
        return 1
    dest = library_dir(a.exptime, a.settemp)
    print("imported:", import_darks(files, dest), "->", dest, flush=True)   # all matching frames: more darks, cleaner master

    from .agent import tools
    before = {t["path"]: t["darks"] for t in tools.list_targets()}
    if a.then in ("organize", "stack", "restack", "process"):
        r = _py("organize.py", "--refresh", "--apply")
        print(r.stdout[-3000:], r.stderr[-1000:], flush=True)
    stacked = []
    if a.then in ("stack", "restack", "process"):
        from . import wbpp
        for t in tools.list_targets():
            more_darks = t["darks"] > before.get(t["path"], 0)
            if (not t["master"] and t["darks"] > 0) or (a.then == "restack" and t["master"] and more_darks):
                print(f"stacking {t['target']} ...", flush=True)
                res = wbpp.run(t["path"])
                res.pop("highlights", None)
                print(json.dumps(res, ensure_ascii=False), flush=True)
                stacked.append(t["target"])
    if a.then == "process":
        from .agent import run
        for name in stacked:
            print(f"agent: {name}", flush=True)
            print(run.run("按流程完整处理这个目标并给出成品。注意这晚使用了 Antlia 四通道多波段滤镜（见 session.json / "
                          "read_knowledge('filters')）。", name, verbose=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
