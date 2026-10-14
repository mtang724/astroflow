"""Local API: security guard, settings (keys never returned), targets and parameters, files, jobs, events, agent."""
import json
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from PIL import Image

from astroflow import pi, settings
from astroflow.agent import session as session_mod
from astroflow.api.app import Services, create_app

TOKEN = "test-token"
H = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def env(tmp_settings):
    tmp_path, store = tmp_settings
    root = tmp_path / "Astro"
    target = root / "In Processing" / "2026Oct09" / "NGC 7293"
    (target / "Light").mkdir(parents=True)
    (target / "Light" / "Light_NGC7293_300.0s.fit").write_bytes(b"")
    (target / "Post" / "previews").mkdir(parents=True)
    Image.new("RGB", (64, 48), (10, 20, 30)).save(target / "Post" / "previews" / "50_final.jpg")
    (target / "Post" / "state.json").write_text(json.dumps({"recipe": "osc_multiband_nebula", "stages": {}}))
    s = settings.get()
    s.astro_root = root.as_posix()
    settings.save(s)
    services = Services()
    client = TestClient(create_app(TOKEN, services=services), base_url="http://127.0.0.1:8765")
    yield SimpleNamespace(client=client, root=root, target=target, store=store, services=services, tmp=tmp_path)


def test_guard(env):
    c = env.client
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/targets").status_code == 401
    assert c.get("/api/targets", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.get("/api/targets", params={"t": "令牌"}).status_code == 401          # non-ASCII: refused, not a crash
    assert c.get("/api/targets", headers={**H, "Host": "evil.example:8000"}).status_code == 403
    assert c.get("/api/targets", headers={**H, "Origin": "http://evil.example"}).status_code == 403
    r = c.get(f"/api/health?t={TOKEN}")                       # first page load with ?t= sets the cookie
    assert "astroflow_token" in r.cookies or c.cookies.get("astroflow_token")
    assert c.get("/api/targets").status_code == 200           # now authorised by the cookie


def test_settings_never_return_keys(env):
    c = env.client
    s = c.get("/api/settings", headers=H).json()
    assert s["astro_root"] == env.root.as_posix() and s["checks"]["astro_root"]
    assert c.put("/api/settings/keys/DeepSeek", json={"key": "sk-secret"}, headers=H).json()["ok"]
    s = c.get("/api/settings", headers=H).json()
    deepseek = next(p for p in s["llm_providers"] if p["name"] == "DeepSeek")
    assert deepseek["has_key"] and "sk-secret" not in json.dumps(s)
    assert env.store["DeepSeek"] == "sk-secret"
    r = c.patch("/api/settings", json={"llm_active": "Nope"}, headers=H)
    assert r.status_code == 400
    r = c.patch("/api/settings", json={"preferences": {"language": "en"}}, headers=H)
    assert r.json()["preferences"] == {"language": "en"}


def test_provider_keys_follow_renames_and_deletes(env):
    c = env.client
    c.put("/api/settings/keys/OpenAI", json={"key": "sk-o"}, headers=H)
    r = c.post("/api/settings/providers/rename", json={"old": "OpenAI", "new": "OpenAI (work)"}, headers=H)
    assert r.status_code == 200 and env.store == {"OpenAI (work)": "sk-o"}
    assert {"OpenAI (work)"} <= {p["name"] for p in r.json()["llm_providers"]}
    r2 = c.post("/api/settings/providers/rename", json={"old": "DeepSeek", "new": "OpenAI (work)"}, headers=H)
    assert r2.status_code == 400
    keep = [p for p in r.json()["llm_providers"] if p["name"] != "OpenAI (work)"]
    assert c.patch("/api/settings", json={"llm_providers": keep}, headers=H).status_code == 200
    assert env.store == {}                                   # a deleted provider takes its key along


def test_import_plan(env):
    c = env.client
    missing = (env.tmp / "no such card").as_posix()
    assert c.post("/api/organize/plan", json={"sources": [missing]}, headers=H).status_code == 404
    card = env.tmp / "card" / "Light"
    card.mkdir(parents=True)
    hdu = fits.PrimaryHDU(np.zeros((4, 6), dtype=np.uint16))
    hdu.header.update({"IMAGETYP": "Light", "OBJECT": "M51", "EXPTIME": 300.0, "ISO": "3200", "INSTRUME": "Nikon"})
    hdu.writeto(card / "Light_M51_300.0s_20250427-223309_0001.fit")
    plan = c.post("/api/organize/plan", json={"sources": [card.parent.as_posix()]}, headers=H).json()
    (row,) = plan["rows"]
    assert (row["kind"], row["target"], row["lights"]["count"], row["darks"]["count"]) == ("target", "M51", 1, 0)
    assert plan["imported"]["lights"] == 1 and any(w.startswith("缺少暗场") for w in row["warnings"])


def test_shutdown_kills_pixinsight_left_running(env):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    pi._started.add(proc.pid)                                # as if a PixInsight job had not stopped in time
    try:
        env.services.shutdown(wait=0.1)
        assert proc.wait(timeout=10) is not None
    finally:
        pi._started.discard(proc.pid)
        if proc.poll() is None:
            proc.kill()


def test_targets_and_params(env):
    c = env.client
    ts = c.get("/api/targets", headers=H).json()
    assert [t["name"] for t in ts] == ["NGC 7293"] and ts[0]["night"] == "2026Oct09"
    path = env.target.as_posix()
    d = c.get("/api/targets/detail", params={"path": path}, headers=H).json()
    assert d["recipe"] == "osc_multiband_nebula" and d["lights"] == 1
    stages = c.get("/api/params", params={"path": path}, headers=H).json()
    assert stages[0]["stage"] == "linear"
    r = c.put("/api/params", json={"path": path, "stage": "starless", "step_id": "sat", "key": "boost", "value": 0.9},
              headers=H).json()
    sat = next(st for s in r if s["stage"] == "starless" for st in s["steps"] if st["id"] == "sat")
    boost = next(f for f in sat["fields"] if f["key"] == "boost")
    assert boost["value"] == 0.9 and boost["edited"]
    r = c.delete("/api/params", params={"path": path}, headers=H).json()
    sat = next(st for s in r if s["stage"] == "starless" for st in s["steps"] if st["id"] == "sat")
    assert not next(f for f in sat["fields"] if f["key"] == "boost")["edited"]
    r = c.post("/api/targets/session", json={"path": path, "filter": "Antlia Quad", "filter_class": "osc_multiband"},
               headers=H).json()
    assert r["filter_class"] == "osc_multiband"


def test_comet_target_steps(env):
    """A comet is stacked in two steps: WBPP registers the frames, then astroflow.comet stacks on the nucleus; only
    that stack is the comet recipe's start image (WBPP's star-aligned master would smear the comet)."""
    c = env.client
    comet = env.root / "In Processing" / "2025Sep20" / "C2025-R3"
    (comet / "Light").mkdir(parents=True)

    def state():
        return c.get("/api/targets/detail", params={"path": comet.as_posix()}, headers=H).json()

    d = state()
    assert (d["type"], d["registered"], d["master"]) == ("comet", False, False)
    registered = comet / "Output" / "registered" / "Light_BIN-1"
    registered.mkdir(parents=True)
    (registered / "Light_0001_r.xisf").write_bytes(b"")
    (comet / "Output" / "master").mkdir(parents=True)
    (comet / "Output" / "master" / "masterLight_BIN-1_autocrop.xisf").write_bytes(b"")
    assert (state()["registered"], state()["master"]) == (True, False)
    (comet / "Post").mkdir(exist_ok=True)
    (comet / "Post" / "comet_stack.fits").write_bytes(b"")
    assert state()["master"] is True


def test_unknown_target_gets_a_chosen_recipe(env):
    c = env.client
    cave = env.root / "In Processing" / "2026Oct09" / "Sh2-155"
    (cave / "Light").mkdir(parents=True)
    path = cave.as_posix()
    d = c.get("/api/targets/detail", params={"path": path}, headers=H).json()
    assert (d["type"], d["recipe"]) == ("unknown", None)
    assert c.get("/api/params", params={"path": path}, headers=H).status_code == 400
    assert c.post("/api/targets/recipe", json={"path": path, "recipe": "nope"}, headers=H).status_code == 400
    r = c.post("/api/targets/recipe", json={"path": path, "recipe": "osc_broadband_nebula"}, headers=H).json()
    assert r["recipe"] == "osc_broadband_nebula"
    stages = c.get("/api/params", params={"path": path}, headers=H).json()
    assert [s["stage"] for s in stages][:2] == ["linear", "stretch"]


def test_files_are_confined(env):
    c = env.client
    img = (env.target / "Post" / "previews" / "50_final.jpg").as_posix()
    r = c.get("/api/files", params={"path": img}, headers=H)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    r = c.get("/api/files", params={"path": img, "max": 32}, headers=H)
    assert r.status_code == 200 and Image.open(__import__("io").BytesIO(r.content)).size[0] == 32
    outside = env.tmp / "secret.jpg"
    Image.new("RGB", (4, 4)).save(outside)
    assert c.get("/api/files", params={"path": outside.as_posix()}, headers=H).status_code == 403
    assert c.get("/api/files", params={"path": (env.target / "Post" / "state.json").as_posix()},
                 headers=H).status_code == 400


def test_jobs_and_event_stream(env):
    c = env.client
    with c.websocket_connect(f"ws://127.0.0.1:8765/api/events?t={TOKEN}") as ws:
        first = json.loads(ws.receive_text())
        assert first["type"] == "jobs.snapshot"
        job = env.services.jobs.submit("test", "dummy", lambda: 7)
        kinds = set()
        for _ in range(10):
            msg = json.loads(ws.receive_text())
            kinds.add(msg["type"])
            if msg["type"] == "job.finished":
                break
        assert {"job.queued", "job.started", "job.finished"} <= kinds
    r = c.get(f"/api/jobs/{job.id}", headers=H).json()
    assert r["state"] == "done" and r["result"] == 7


class _FakeLLM:
    def __init__(self, provider=None):
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}
        self.provider = SimpleNamespace(name="Fake", tools=True)
        self.planner, self.vision = "fake-model", ""

    def chat(self, messages, tools=None, max_tokens=16000):
        return SimpleNamespace(content="你好，我是 astroflow。", tool_calls=None)


def test_agent_session_over_api(env, monkeypatch):
    monkeypatch.setattr(session_mod, "LLM", _FakeLLM)
    c = env.client
    s = c.post("/api/agent/sessions", json={}, headers=H).json()
    job = c.post(f"/api/agent/sessions/{s['sid']}/messages", json={"text": "你好"}, headers=H).json()
    t0 = time.time()
    while c.get(f"/api/jobs/{job['id']}", headers=H).json()["state"] != "done":
        assert time.time() - t0 < 10
        time.sleep(0.05)
    events = c.get(f"/api/agent/sessions/{s['sid']}", headers=H).json()["events"]
    assert [e["kind"] for e in events] == ["user", "assistant", "done"]
    assert c.post("/api/agent/sessions/nope/messages", json={"text": "x"}, headers=H).status_code == 404


def _done(c, job, timeout=20):
    t0 = time.time()
    while (state := c.get(f"/api/jobs/{job['id']}", headers=H).json())["state"] in ("queued", "running"):
        assert time.time() - t0 < timeout
        time.sleep(0.05)
    return state


def test_frame_check_over_api(env):
    c = env.client
    from tests.test_frames import star_field
    light = env.target / "Light"
    for p in light.iterdir():
        p.unlink()
    for i in range(3):
        star_field(light / f"L{i}.fits", seed=i, shape=(300, 400), stars=80)
    job = c.post("/api/actions/frames", json={"path": env.target.as_posix()}, headers=H).json()
    assert _done(c, job)["result"] == {"total": 3, "measured": 3, "suspicious": 0}
    r = c.get("/api/frames", params={"path": env.target.as_posix()}, headers=H).json()
    assert [f["name"] for f in r["frames"]] == ["L0.fits", "L1.fits", "L2.fits"] and r["fwhm_unit"] == "px"
    assert c.get("/api/files", params={"path": r["frames"][0]["thumb"]}, headers=H).status_code == 200
    r = c.post("/api/frames/exclude", json={"path": env.target.as_posix(), "names": ["L1.fits"]}, headers=H).json()
    assert r["summary"]["excluded"] == 1
    r = c.post("/api/frames/restore", json={"path": env.target.as_posix(), "names": ["L1.fits"]}, headers=H).json()
    assert r["summary"]["excluded"] == 0
    assert c.get("/api/frames", params={"path": (env.tmp / "nowhere").as_posix()}, headers=H).status_code == 404


def test_disk_space_cleanup_and_archive_over_api(env):
    c = env.client
    reg = env.target / "Output" / "registered" / "L_r.xisf"
    reg.parent.mkdir(parents=True)
    reg.write_bytes(b"x" * 2000)
    (env.target / "Post" / "10_linear.xisf").write_bytes(b"x" * 500)
    (row,) = c.get("/api/storage", headers=H).json()
    assert row["name"] == "NGC 7293" and row["removable"] == 2500
    job = c.post("/api/actions/cleanup", json={"paths": [env.target.as_posix()]}, headers=H).json()
    assert _done(c, job)["result"]["freed"] == 2500 and not reg.exists()
    job = c.post("/api/actions/archive", json={"path": env.target.as_posix(), "clean": True}, headers=H).json()
    dest = env.root / "Processed" / "2026Oct09" / "NGC 7293"
    assert _done(c, job)["result"]["path"] == dest.as_posix() and dest.is_dir()
    assert c.get("/api/targets", headers=H).json() == []
    outside = env.tmp / "elsewhere" / "M1"
    (outside / "Light").mkdir(parents=True)
    for url, body in (("/api/actions/archive", {"path": outside.as_posix()}),
                      ("/api/actions/cleanup", {"paths": [outside.as_posix()]}),
                      ("/api/frames/exclude", {"path": outside.as_posix(), "names": ["x.fit"]}),
                      ("/api/actions/frames", {"path": outside.as_posix()})):
        assert c.post(url, json=body, headers=H).status_code == 403, url      # only the folders astroflow works in
    sneaky = (env.root / "In Processing" / ".." / ".." / "elsewhere" / "M1").as_posix()
    assert c.post("/api/actions/cleanup", json={"paths": [sneaky]}, headers=H).status_code == 403


def test_nights_presets_and_process_everything_over_api(env, monkeypatch):
    c = env.client
    other = env.root / "In Processing" / "2026Oct12" / "NGC 7293"
    (other / "Light").mkdir(parents=True)
    (other / "Light" / "Light_NGC7293_2.fit").write_bytes(b"")
    r = c.get("/api/targets/nights", params={"path": env.target.as_posix()}, headers=H).json()
    assert [n["night"] for n in r["nights"]] == ["2026Oct09", "2026Oct12"] and r["combined"] is None
    job = c.post("/api/actions/combine", json={"nights": [env.target.as_posix(), other.as_posix()]}, headers=H).json()
    combined = env.root / "In Processing" / "Multi-night" / "NGC 7293"
    assert _done(c, job)["result"]["path"] == combined.as_posix()
    r = c.get("/api/targets/nights", params={"path": other.as_posix()}, headers=H).json()
    assert r["combined"] == combined.as_posix() and r["included"] == ["2026Oct09", "2026Oct12"]
    assert c.post("/api/actions/combine", json={"nights": [env.target.as_posix()]}, headers=H).status_code == 400

    path = env.target.as_posix()
    assert c.post("/api/presets", json={"path": path, "name": "柔和"}, headers=H).status_code == 400   # no edits yet
    c.put("/api/params", json={"path": path, "stage": "starless", "step_id": "sat", "key": "boost", "value": 0.5},
          headers=H)
    assert c.post("/api/presets", json={"path": path, "name": "柔和"}, headers=H).json()["edits"] == 1
    assert [p["name"] for p in c.get("/api/presets", params={"recipe": "osc_multiband_nebula"}, headers=H).json()] == ["柔和"]
    c.post("/api/targets/session", json={"path": other.as_posix(), "filter_class": "osc_multiband"}, headers=H)
    assert c.post("/api/presets/apply", json={"path": other.as_posix(), "name": "柔和"}, headers=H).json()["ok"]
    assert c.post("/api/presets/apply", json={"path": other.as_posix(), "name": "没有"}, headers=H).status_code == 404
    assert c.delete("/api/presets", params={"name": "柔和"}, headers=H).json()["ok"]

    from astroflow.services import actions
    ran = []
    monkeypatch.setattr(actions, "run_all", lambda d: ran.append(d.name) or {"stages": []})
    plan = {r["name"] + "@" + (r["night"] or "multi"): r for r in c.get("/api/batch/plan", headers=H).json()}
    assert plan["NGC 7293@multi"]["steps"] == ["stack", "process"] and plan["NGC 7293@multi"]["nights"] == [
        "2026Oct09", "2026Oct12"]
    assert plan["NGC 7293@2026Oct09"]["skip"].startswith("已合并")         # the merged target stacks its nights
    out = c.post("/api/actions/batch", json={"paths": [r["path"] for r in plan.values()]}, headers=H).json()
    for job in out["jobs"]:
        _done(c, job)
    assert ran == ["NGC 7293"] and len(out["skipped"]) == 2


def test_share_over_api(env):
    c = env.client
    path = env.target.as_posix()
    assert c.get("/api/share/info", params={"path": path}, headers=H).json()["source"] is None
    assert c.post("/api/share/preview", json={"path": path}, headers=H).status_code == 400
    Image.new("RGB", (300, 200), (30, 30, 60)).save(env.target / "Post" / "NGC 7293_20261012.png")
    info = c.get("/api/share/info", params={"path": path}, headers=H).json()
    assert (info["width"], info["height"]) == (300, 200) and info["caption"][0] == "NGC 7293 螺旋星云"
    assert set(info["crops"]) == {"3:4", "4:5", "1:1", "16:9", "original"}
    r = c.post("/api/share/preview", json={"path": path, "aspect": "16:9", "caption": info["caption"]}, headers=H)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    out = c.post("/api/share/export", json={"path": path, "aspect": "1:1", "signature": "© Ming"}, headers=H).json()
    assert (out["width"], out["height"]) == (200, 200) and out["file"].endswith(".jpg")
    assert c.get("/api/share/info", params={"path": path}, headers=H).json()["signature"] == "© Ming"
    bad = c.post("/api/share/preview", json={"path": path, "crop": [0, 1]}, headers=H)
    assert bad.status_code == 422
