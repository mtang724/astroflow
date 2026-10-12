"""Job queue, agent jobs and recipe-override services (no PixInsight)."""
import threading
import time
from types import SimpleNamespace

from astroflow import jobctx, pipeline
from astroflow.agent import session as session_mod
from astroflow.agent import tools
from astroflow.api.agents import AgentService
from astroflow.services import recipes
from astroflow.services.jobs import JobManager


def _wait(job, timeout=10):
    t0 = time.time()
    while job.state in ("queued", "running"):
        assert time.time() - t0 < timeout, "job did not finish"
        time.sleep(0.02)


def test_job_runs_reports_progress_and_captures_stdout():
    jobs = JobManager()
    events = []
    jobs.subscribe(lambda kind, data: events.append(kind))

    def work():
        jobctx.emit("stage.started", stage="linear", index=0, total=2)
        print("hello from the library")
        return 42

    job = jobs.submit("process", "test", work)
    _wait(job)
    assert job.state == "done" and job.result == 42
    assert job.progress == "linear (1/2)"
    assert list(job.log) == ["hello from the library"]
    assert events[0] == "job.queued" and events[-1] == "job.finished" and "job.event" in events


def test_running_job_can_be_cancelled_and_queued_job_skipped():
    jobs = JobManager()
    started = threading.Event()

    def long_work():
        started.set()
        while True:
            jobctx.check_cancelled()
            time.sleep(0.01)

    first = jobs.submit("process", "long", long_work)
    second = jobs.submit("process", "never", lambda: 1)
    assert started.wait(5)
    assert jobs.cancel(second.id) and second.state == "cancelled"
    assert jobs.cancel(first.id)
    _wait(first)
    assert first.state == "cancelled"
    time.sleep(0.1)
    assert second.result is None


def test_progress_keeps_the_stage_while_pixinsight_runs():
    jobs = JobManager()
    seen = []
    jobs.subscribe(lambda kind, data: seen.append((data["progress"], data["stage"])) if kind == "job.event" else None)

    def work():
        jobctx.emit("stage.started", stage="starless", index=3, total=6)
        jobctx.emit("pi.started", script="run.js", pid=1)
        jobctx.emit("pi.finished", script="run.js", rc=0, seconds=1.0)

    _wait(jobs.submit("process", "t", work))
    assert seen == [("starless (4/6)", "starless"), ("starless (4/6) · PixInsight", "starless"),
                    ("starless (4/6)", "starless")]


class _BusyToolLLM:
    """Calls a tool that runs until it is cancelled (like a PixInsight stage)."""

    def __init__(self, provider=None):
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}
        self.provider = SimpleNamespace(name="Fake", tools=True)
        self.planner, self.vision = "fake-model", ""
        self.turn = 0

    def chat(self, messages, tools=None, max_tokens=16000):
        self.turn += 1
        if self.turn == 1:
            call = SimpleNamespace(id="c1", function=SimpleNamespace(name="busy", arguments="{}"))
            return SimpleNamespace(content="", tool_calls=[call])
        return SimpleNamespace(content="完成。", tool_calls=None)


def test_stopping_an_agent_job_in_the_queue_stops_the_agent(tmp_settings, monkeypatch):
    monkeypatch.setattr(session_mod, "LLM", _BusyToolLLM)
    running = threading.Event()

    def busy():
        running.set()
        while True:
            jobctx.check_cancelled()
            time.sleep(0.01)

    monkeypatch.setitem(tools.REGISTRY, "busy", {"fn": busy, "schema": {}})
    jobs = JobManager()
    agents = AgentService(jobs, SimpleNamespace(publish=lambda kind, data: None))
    sid = agents.create()["sid"]
    job = agents.send(sid, "处理这个目标")
    assert running.wait(5)
    assert jobs.cancel(job.id)                      # the Jobs panel's Stop button, not the chat's
    _wait(job)
    assert job.state == "cancelled"
    assert agents.public(sid)["events"][-1]["kind"] == "cancelled"


def test_failed_job_keeps_error_and_traceback():
    jobs = JobManager()
    job = jobs.submit("process", "boom", lambda: 1 / 0)
    _wait(job)
    assert job.state == "failed" and "ZeroDivisionError" in job.error
    assert any("Traceback" in line for line in job.log)


def test_recipe_fields_and_overrides_roundtrip(tmp_path):
    spec = recipes.spec("comet")
    sat = next(st for s in spec if s["stage"] == "starless" for st in s["steps"] if st["id"] == "sat")
    keys = {f["key"]: f for f in sat["fields"]}
    assert keys["boost"]["type"] == "float" and keys["passes"]["type"] == "int" and "id" not in keys
    nxt = next(st for s in spec if s["stage"] == "linear" for st in s["steps"] if st["id"] == "nxt")
    assert {f["key"] for f in nxt["fields"]} >= {"params.denoise", "params.denoise_color"}

    recipes.set_field(tmp_path, "starless", "sat", "boost", 0.85)
    recipes.set_field(tmp_path, "linear", "nxt", "params.denoise", 0.5)
    assert recipes.overrides(tmp_path) == {"starless": {"sat": {"boost": 0.85}},
                                           "linear": {"nxt": {"params": {"denoise": 0.5}}}}
    eff = recipes.effective("comet", tmp_path)
    f = next(f for s in eff if s["stage"] == "starless" for st in s["steps"] if st["id"] == "sat"
             for f in st["fields"] if f["key"] == "boost")
    assert f["value"] == 0.85 and f["default"] == 0.80 and f["edited"]

    recipes.set_field(tmp_path, "linear", "nxt", "params.denoise", None)
    assert recipes.overrides(tmp_path) == {"starless": {"sat": {"boost": 0.85}}}
    recipes.reset(tmp_path)
    assert recipes.overrides(tmp_path) == {}


def test_saved_params_apply_to_every_run_and_survive_pipeline_saves(tmp_path, monkeypatch):
    work = pipeline.Work(tmp_path, "comet")                          # a job loads the target's state,
    recipes.set_field(tmp_path, "starless", "sat", "boost", 0.95)    # the user edits a parameter meanwhile,
    work.save()                                                       # the job saves its state when the stage ends
    assert recipes.overrides(tmp_path) == {"starless": {"sat": {"boost": 0.95}}}
    sent = {}

    def fake_run_job(job, **kw):
        sent.update(job)
        return {"steps": [], "saved": [], "previews": []}

    monkeypatch.setattr(pipeline.pi, "run_job", fake_run_job)
    rec = pipeline.run_stage(work, "starless", {"sat": {"passes": 3}})     # e.g. the agent's own override
    sat = next(s for s in sent["steps"] if s["id"] == "sat")
    assert sat["boost"] == 0.95 and sat["passes"] == 3
    assert rec["overrides"] == {"sat": {"boost": 0.95, "passes": 3}}
