"""Launch PixInsight headlessly and run PJSR scripts / jobs.

A job is a JSON file read by pjsr/runner.js. The runner writes a result JSON next to it and appends
progress lines to a log, because headless PixInsight has no readable console.
"""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil

from . import config, jobctx

_started = set()          # PixInsight processes this process started and that are still running


class PIError(RuntimeError):
    pass


def running_instances():
    """PixInsight processes currently running (the user's GUI or another headless job)."""
    found = []
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info["name"] or "").lower().startswith("pixinsight"):
            found.append(p.info)
    return found


def _lock_path():
    return config.RUNS / "pixinsight.lock"   # config.RUNS: bootstrap scripts, a path without spaces or CJK characters


# ---------------------------------------------------------------------------- watchdog helpers

def _cpu_seconds(pid):
    """User+system CPU time of a process (None if it is gone)."""
    try:
        t = psutil.Process(pid).cpu_times()
        return t.user + t.system
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def window_titles(pid):
    """Visible top-level window titles of a process (a modal error box shows up here). Windows only; elsewhere the
    CPU-idle watchdog alone has to recognise a stuck dialog."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(hwnd, buf, 256)
            if buf.value:
                titles.append(buf.value)
        return True

    u32.EnumWindows(cb, 0)
    return titles


def kill_tree(pid, timeout=30):
    """Kill a process and everything it started (PixInsight may spawn helpers), waiting for them to exit."""
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = root.children(recursive=True) + [root]
    for p in procs:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=timeout)


def kill_started():
    """Kill the PixInsight processes this process started (the app's backend is exiting: none may outlive it)."""
    for pid in list(_started):
        kill_tree(pid, timeout=10)


class _Lock:
    """One headless PixInsight at a time. A second instance gets settings slot 2, which lacks the Gaia
    database paths configured in the GUI (SPCC fails) and makes BlurXTerminator crash (access violation)."""

    def __init__(self, wait=6 * 3600):
        self.wait = wait

    def __enter__(self):
        self.path = _lock_path()                 # fixed for this job, even if the runs folder setting changes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                if self._stale():
                    self.path.unlink(missing_ok=True)
                    continue
                if time.time() - t0 > self.wait:
                    raise PIError("timed out waiting for another astroflow PixInsight job to finish") from None
                jobctx.emit("pi.waiting", reason="another astroflow PixInsight job is running")
                jobctx.sleep(5)

    def _stale(self):
        try:
            pid = int(self.path.read_text())
        except (OSError, ValueError):
            return True
        return not psutil.pid_exists(pid)

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def _watch(proc, name, t0, timeout, idle_limit):
    """Wait for a headless PixInsight to exit (returns its exit code); kill it on Cancel, timeout or idleness.
    A headless instance that stops using CPU is usually sitting on a modal dialog (bad parameter, error box) and would
    otherwise block until the timeout. WBPP passes a long idle_limit because online plate solving waits on the network
    with an idle CPU."""
    last_cpu, last_change = None, time.time()
    while True:
        try:
            return proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        if jobctx.current().cancelled:
            kill_tree(proc.pid)
            raise jobctx.Cancelled(f"cancelled while PixInsight was running {name}")
        now = time.time()
        cpu = _cpu_seconds(proc.pid)
        if cpu is not None and (last_cpu is None or cpu - last_cpu > 0.5):
            last_cpu, last_change = cpu, now
        stuck = now - last_change > idle_limit
        if stuck or now - t0 > timeout:
            titles = window_titles(proc.pid)
            kill_tree(proc.pid)
            why = f"idle for {idle_limit}s (probably a modal dialog)" if stuck else f"timed out after {timeout}s"
            raise PIError(f"PixInsight {why} running {name}; open windows: {titles}")


def run_script(script, args=(), timeout=4 * 3600, require_slot1=True, wait_other=3600, idle_limit=600):
    """Run a PJSR script in a new headless PixInsight instance and wait for it to exit.

    Arguments reach the script as jsArguments (comma-separated, so no commas inside values).
    Jobs are serialised through a lock; with require_slot1, a PixInsight the user has open is reported
    instead of silently pushing the job into settings slot 2 (where RC tools and SPCC fail).
    """
    for a in args:
        if "," in str(a):
            raise PIError(f"PixInsight script arguments cannot contain commas: {a}")
    arg = ",".join([Path(script).as_posix()] + [str(a) for a in args])
    cmd = [str(config.PI_EXE), "-n", "--automation-mode", "--no-splash", f"-r={arg}", "--force-exit"]
    with _Lock():
        if require_slot1:
            t_wait = time.time()
            while running_instances():
                if time.time() - t_wait > wait_other:
                    raise PIError("PixInsight is already running (probably your GUI session). Close it so the "
                                  "headless job gets settings slot 1 (Gaia database, RC tools), then retry.")
                jobctx.emit("pi.waiting", reason="PixInsight is open (close it so the headless job gets slot 1)")
                jobctx.sleep(10)
        t0 = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _started.add(proc.pid)
        try:
            jobctx.emit("pi.started", script=Path(script).name, pid=proc.pid)
            rc = _watch(proc, Path(script).name, t0, timeout, idle_limit)
        finally:
            _started.discard(proc.pid)
    jobctx.emit("pi.finished", script=Path(script).name, rc=rc, seconds=round(time.time() - t0, 1))
    return rc, time.time() - t0


def run_job(job, timeout=3600, label="job", idle_limit=600):
    """Run pjsr/runner.js on a job dict. Returns the result dict written by the runner."""
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = config.RUNS / f"{label}-{run_id}"
    d.mkdir(parents=True, exist_ok=True)
    job = dict(job)
    job.setdefault("result", (d / "result.json").as_posix())
    job.setdefault("log", (d / "pi.log").as_posix())
    (d / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")

    # Same preamble as AdP/AperturePhotometry.js: the solver library needs TITLE/SETTINGS_MODULE and the pjsr
    # constant headers before WCSmetadata/AstronomicalCatalogs, otherwise it throws at load time and the
    # headless instance sits on an error box without ever running the job.
    adp = (config.PI_SCRIPTS / "AdP").as_posix()
    boot = ['#define TITLE "astroflow"',
            '#define SETTINGS_MODULE "ASTROFLOW"',
            '#define STAR_CSV_FILE (File.systemTempDirectory + "/astroflow-stars.csv")']
    boot += [f"#include <pjsr/{h}.jsh>" for h in ("DataType", "StdButton", "StdIcon", "UndoFlag", "TextAlign", "ColorSpace")]
    boot += [f'#include "{adp}/WCSmetadata.jsh"', f'#include "{adp}/AstronomicalCatalogs.jsh"',
             "#define USE_SOLVER_LIBRARY true",
             f'#include "{adp}/ImageSolver.js"', f'#include "{adp}/SearchCoordinatesDialog.js"']
    boot += [f'#include "{(config.PJSR_DIR / n).as_posix()}"' for n in ("lib.js", "steps.js", "runner.js")]
    boot += [f'astroflowMain("{(d / "job.json").as_posix()}");', ""]
    script = d / "run.js"
    script.write_text("\n".join(boot), encoding="utf-8")
    jobctx.emit("pi.job", label=label, dir=d.as_posix(), log=Path(job["log"]).as_posix())

    rc, secs = run_script(script, timeout=timeout, idle_limit=idle_limit)
    res_path = Path(job["result"])
    if not res_path.exists():
        log = Path(job["log"])
        tail = log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else "(no log)"
        raise PIError(f"PixInsight exited (rc={rc}) without a result. Log tail:\n{tail}")
    res = json.loads(res_path.read_text(encoding="utf-8"))
    res["_seconds"] = round(secs, 1)
    res["_run_dir"] = d.as_posix()
    if not res.get("ok"):
        raise PIError(f"PixInsight job failed: {res.get('error')}\n{res.get('stack', '')}")
    return res
