"""Per-thread job context: long-running library code reports progress and notices cancellation without knowing who
runs it. From the command line nobody listens and nothing is ever cancelled; the desktop app's worker thread installs
a context whose `emit` forwards events to the UI and whose cancel event is set by the Cancel button.

    with jobctx.use(jobctx.JobContext(emit=on_event)) as ctx:
        pipeline.run(...)          # inside: jobctx.emit("stage.started", stage="linear"); jobctx.check_cancelled()
    ctx.cancel()                   # from another thread

A context can be part of a larger job (`parent`, e.g. one agent message inside a queued job): cancelling the job
cancels it too, and its events also reach the job's listener.
"""
import threading
import time
from contextlib import contextmanager


class Cancelled(Exception):
    """The user cancelled the running job."""


class JobContext:
    def __init__(self, emit=None, parent=None):
        self._emit = emit
        self._parent = parent
        self._cancel = threading.Event()

    def emit(self, kind, **data):
        if self._emit is not None:
            self._emit(kind, data)
        if self._parent is not None:
            self._parent.emit(kind, **data)

    def cancel(self):
        self._cancel.set()

    @property
    def cancelled(self):
        return self._cancel.is_set() or (self._parent is not None and self._parent.cancelled)

    def check(self):
        if self.cancelled:
            raise Cancelled("cancelled by the user")

    def sleep(self, seconds):
        """time.sleep that ends early, raising Cancelled, when the job is cancelled."""
        end = time.monotonic() + seconds
        while True:
            self.check()
            left = end - time.monotonic()
            if left <= 0:
                return
            self._cancel.wait(min(left, 0.5))


_local = threading.local()
_IDLE = JobContext()          # used when no job is running: no listener, never cancelled


def current():
    return getattr(_local, "ctx", None) or _IDLE


@contextmanager
def use(ctx):
    previous = getattr(_local, "ctx", None)
    _local.ctx = ctx
    try:
        yield ctx
    finally:
        _local.ctx = previous


def emit(kind, **data):
    current().emit(kind, **data)


def check_cancelled():
    current().check()


def sleep(seconds):
    current().sleep(seconds)
