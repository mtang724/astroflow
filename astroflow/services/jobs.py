"""Serial job queue: one job at a time (headless PixInsight allows a single instance), each in a worker thread with
its own job context, so library code can report progress (jobctx.emit) and stop on Cancel (jobctx.check_cancelled).

    jobs = JobManager()
    jobs.subscribe(lambda kind, data: ...)        # called from the worker thread: marshal to the UI thread yourself
    job = jobs.submit("process", "M8: run pipeline", lambda: pipeline.run(...), target="M8")
    jobs.cancel(job.id)

Listener events: job.queued / job.started / job.finished {job}, job.event {job_id, kind, data}, job.log {job_id, line}.
"""
import contextlib
import io
import queue
import threading
import time
import traceback
import uuid
from collections import deque
from dataclasses import dataclass, field

from .. import jobctx
from ..i18n import tr


@dataclass
class Job:
    id: str
    kind: str                       # organize | stack | process | comet | agent | export | ...
    title: str
    target: str | None = None
    state: str = "queued"           # queued | running | done | failed | cancelled
    progress: str = ""              # for people: "<step> · <what it is doing>"
    stage: str | None = None        # pipeline stage being run, for the UI to mark
    error: str | None = None
    result: object = None
    queued_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    log: deque = field(default_factory=lambda: deque(maxlen=5000))
    step: str = ""                  # the two parts of `progress` (STEPS and DOING below)
    doing: str = ""

    def public(self):
        return {"id": self.id, "kind": self.kind, "title": self.title, "target": self.target, "state": self.state,
                "progress": self.progress, "stage": self.stage, "error": self.error, "queued_at": self.queued_at,
                "started_at": self.started_at, "finished_at": self.finished_at}


class _LineWriter(io.TextIOBase):
    """stdout replacement that hands complete lines to a callback (library code still prints in places)."""

    def __init__(self, on_line):
        self._on_line, self._buf = on_line, ""

    def write(self, s):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._on_line(line)
        return len(s)

    def flush(self):
        if self._buf.strip():
            self._on_line(self._buf)
        self._buf = ""


STEPS = {             # events that move a job to its next step
    "stage.started": lambda d: f"{d['stage']} ({d['index'] + 1}/{d['total']})",
    "comet.step": lambda d: f"comet: {d['step']} ({d['index'] + 1}/{d['total']})",
    "organize.item": lambda d: f"{d['target']} ({d['index'] + 1}/{d['total']})",
    "frames.progress": lambda d: tr("{done}/{n} 帧", done=d["index"] + 1, n=d["total"]),
    "combine.progress": lambda d: tr("{done}/{n} 个文件", done=d["index"], n=d["total"]),
    "cleanup.item": lambda d: f"{d['target']} ({d['index'] + 1}/{d['total']})",
}
DOING = {             # what the current step is doing right now
    "pi.waiting": lambda d: f"waiting: {d['reason']}",
    "pi.started": lambda d: "PixInsight",
    "pi.finished": lambda d: "",
}


class JobManager:
    def __init__(self):
        self._listeners = []
        self._jobs = {}
        self._queue = queue.Queue()
        self._running = None                  # (job, JobContext)
        self._lock = threading.Lock()
        threading.Thread(target=self._work, name="astroflow-jobs", daemon=True).start()

    # ------------------------------------------------------------------ public
    def subscribe(self, fn):
        self._listeners.append(fn)

    def submit(self, kind, title, fn, target=None):
        job = Job(uuid.uuid4().hex[:8], kind, title, target)
        with self._lock:
            self._jobs[job.id] = job
        self._emit("job.queued", {"job": job.public()})
        self._queue.put((job, fn))
        return job

    def cancel(self, job_id):
        with self._lock:                      # the worker may be starting this very job
            job = self._jobs.get(job_id)
            if job is None or job.state in ("done", "failed", "cancelled"):
                return False
            dropped = job.state == "queued"
            if dropped:
                job.state, job.finished_at = "cancelled", time.time()
            elif self._running and self._running[0] is job:
                self._running[1].cancel()     # takes effect at the next check (PixInsight is killed within ~2 s)
        if dropped:
            self._emit("job.finished", {"job": job.public()})
        return True

    def jobs(self):
        with self._lock:
            return list(self._jobs.values())

    def get(self, job_id):
        return self._jobs.get(job_id)

    def busy(self):
        return self._running is not None or not self._queue.empty()

    # ------------------------------------------------------------------ worker
    def _work(self):
        while True:
            job, fn = self._queue.get()
            ctx = jobctx.JobContext(emit=lambda kind, data, j=job: self._job_event(j, kind, data))
            with self._lock:
                if job.state == "cancelled":
                    continue
                self._running = (job, ctx)
                job.state, job.started_at = "running", time.time()
            self._emit("job.started", {"job": job.public()})
            out = _LineWriter(lambda line, j=job: self._log(j, line))
            try:
                with jobctx.use(ctx), contextlib.redirect_stdout(out):
                    job.result = fn()
                job.state = "done"
            except jobctx.Cancelled:
                job.state = "cancelled"
            except Exception as e:
                job.state, job.error = "failed", f"{type(e).__name__}: {e}"
                self._log(job, traceback.format_exc())
            finally:
                out.flush()
                job.finished_at = time.time()
                with self._lock:
                    self._running = None
                self._emit("job.finished", {"job": job.public()})

    def _job_event(self, job, kind, data):
        try:
            if kind in STEPS:
                job.step, job.doing = STEPS[kind](data), ""
            elif kind in DOING:
                job.doing = DOING[kind](data)
        except KeyError:                      # an event without the expected fields: keep the old text
            pass
        if kind == "stage.started":
            job.stage = data.get("stage")
        job.progress = " · ".join(p for p in (job.step, job.doing) if p)
        self._emit("job.event", {"job_id": job.id, "kind": kind, "data": data, "progress": job.progress,
                                 "stage": job.stage})

    def _log(self, job, line):
        job.log.append(line)
        self._emit("job.log", {"job_id": job.id, "line": line})

    def _emit(self, kind, data):
        for fn in list(self._listeners):
            try:
                fn(kind, data)
            except Exception:
                traceback.print_exc()
