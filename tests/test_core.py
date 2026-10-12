"""Settings, config, job context, skills, organise, catalogue and the agent session loop (no network, no PixInsight)."""
import json
import sys
import threading
import time
from types import SimpleNamespace

import httpx
import openai
import pytest

from astroflow import config, jobctx, objects, organize, settings
from astroflow.agent import llm as llm_mod
from astroflow.agent import session as session_mod
from astroflow.agent import skills, tools


def test_settings_roundtrip_and_config_follows(tmp_settings):
    tmp, _ = tmp_settings
    s = settings.load()
    assert s.provider().name == "DeepSeek"
    s.astro_root = str(tmp / "Astro")
    settings.save(s)
    assert config.IN_PROCESSING == tmp / "Astro" / "In Processing"
    again = settings.load()
    assert again.astro_root == str(tmp / "Astro")


def test_custom_provider_and_keys(tmp_settings):
    _, store = tmp_settings
    s = settings.get()
    s.upsert_provider(settings.LLMProvider("Ollama (local)", "http://localhost:11434/v1", "qwen3:32b", "", needs_key=False))
    settings.save(s)
    assert settings.get().provider("Ollama (local)").vision_model == ""
    assert not settings.has_api_key("OpenAI")
    settings.set_api_key("OpenAI", "sk-test")
    assert store["OpenAI"] == "sk-test" and settings.get_api_key("OpenAI") == "sk-test"
    settings.set_api_key("OpenAI", "")
    assert not settings.has_api_key("OpenAI")


def test_renaming_a_provider_moves_its_key(tmp_settings):
    _, store = tmp_settings
    settings.set_api_key("DeepSeek", "sk-1")
    s = settings.rename_provider("DeepSeek", "DeepSeek (work)")
    assert s.llm_active == "DeepSeek (work)" and settings.get().provider().name == "DeepSeek (work)"
    assert store == {"DeepSeek (work)": "sk-1"}
    with pytest.raises(ValueError):
        settings.rename_provider("OpenAI", "DeepSeek (work)")


def test_damaged_settings_file_falls_back_to_defaults(tmp_settings):
    tmp, _ = tmp_settings
    (tmp / "settings.json").write_text('{"astro_root": "F:/x", ', encoding="utf-8")   # cut off mid-write
    s = settings.reload()
    assert s.provider().name == "DeepSeek"
    assert (tmp / "settings.json.broken").exists() and not (tmp / "settings.json").exists()


@pytest.mark.skipif(sys.platform not in ("win32", "darwin"), reason="shared fallback folders: Windows and macOS")
def test_default_runs_folder_is_one_pixinsight_accepts(tmp_path, monkeypatch):
    home = tmp_path / "Ming Tang"                      # a user name with a space
    monkeypatch.setattr(config, "FROZEN", True)
    monkeypatch.setattr("platformdirs.user_cache_dir", lambda *a, **k: str(home / "AppData" / "astroflow"))
    monkeypatch.setattr(config.Path, "home", lambda: home)
    runs = config._default_runs()
    assert config.pixinsight_path_ok(runs) and not runs.is_relative_to(home)


def test_jobctx_events_and_cancel():
    seen = []
    ctx = jobctx.JobContext(emit=lambda kind, data: seen.append((kind, data)))
    with jobctx.use(ctx):
        jobctx.emit("stage.started", stage="linear")
        jobctx.check_cancelled()
        ctx.cancel()
        with pytest.raises(jobctx.Cancelled):
            jobctx.check_cancelled()
    assert seen == [("stage.started", {"stage": "linear"})]
    jobctx.check_cancelled()                                   # outside the job: idle context, never cancelled


def test_jobctx_is_per_thread():
    ctx = jobctx.JobContext()
    ctx.cancel()
    errors = []
    with jobctx.use(ctx):
        t = threading.Thread(target=lambda: errors.append(jobctx.current().cancelled))
        t.start()
        t.join()
    assert errors == [False]


def test_jobctx_child_follows_its_job():
    seen = []
    job = jobctx.JobContext(emit=lambda kind, data: seen.append(("job", kind)))
    part = jobctx.JobContext(emit=lambda kind, data: seen.append(("part", kind)), parent=job)
    part.emit("pi.started")
    assert seen == [("part", "pi.started"), ("job", "pi.started")]
    part.cancel()                                   # cancelling the part leaves the job alone
    assert part.cancelled and not job.cancelled
    other = jobctx.JobContext(parent=job)
    job.cancel()                                    # cancelling the job reaches every part
    assert other.cancelled
    t0 = time.monotonic()
    with pytest.raises(jobctx.Cancelled):
        other.sleep(30)
    assert time.monotonic() - t0 < 1


def _write_skill(root, name, description, body="Do things.", extra=None):
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8")
    for rel, text in (extra or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")


def test_skills_discover_load_and_guard(tmp_path):
    _write_skill(tmp_path, "comet", "Comets: stack on stars and nucleus.", extra={"references/a.md": "detail"})
    _write_skill(tmp_path, "galaxy", "Galaxies.")
    found = skills.discover(tmp_path)
    assert [s.name for s in found] == ["comet", "galaxy"]
    assert "- comet: Comets: stack on stars and nucleus." in skills.index_text(found)
    s = skills.find("comet", tmp_path)
    assert s.body.strip() == "Do things." and s.files() == ["references/a.md"]
    assert skills.read_file("comet", "references/a.md", tmp_path) == "detail"
    with pytest.raises(ValueError):
        skills.read_file("comet", "../galaxy/SKILL.md", tmp_path)


def test_project_skills_are_well_formed():
    found = skills.discover()
    assert {"astro-workflow", "comet", "judge-and-tune"} <= {s.name for s in found}
    for s in found:
        assert s.description and len(s.description) < 400 and s.body.strip()


def test_import_copies_whole_files_only(tmp_path):
    src = tmp_path / "card" / "Light_M42_300.0s.fit"
    src.parent.mkdir()
    src.write_bytes(b"x" * 1000)
    dest = tmp_path / "night" / "M42" / "Light"
    dest.mkdir(parents=True)
    (dest / "Light_M42_300.0s.partial").write_bytes(b"xx")         # left by an import that was cut short
    organize.copy_or_move(src, dest, move=False)
    assert [p.name for p in dest.iterdir()] == [src.name] and src.exists()
    assert (dest / src.name).read_bytes() == src.read_bytes()
    organize.copy_or_move(src, dest, move=True)                    # already there, same size: the original goes
    assert not src.exists()
    with jobctx.use(jobctx.JobContext()) as ctx:
        ctx.cancel()
        with pytest.raises(jobctx.Cancelled):                         # Cancel stops an import between files
            organize.copy_or_move(dest / src.name, tmp_path / "elsewhere", move=False)


def test_catalogue_follows_the_scripts_folder(tmp_settings):
    tmp, _ = tmp_settings
    adp = tmp / "scripts" / "AdP"
    adp.mkdir(parents=True)
    (adp / "Messier.csv").write_text("id,alpha,delta,NGC/IC\nM 42,83.82,-5.39,NGC 1976\n", encoding="utf-8")
    s = settings.get()
    s.pixinsight_scripts = (tmp / "wrong").as_posix()
    settings.save(s)
    assert objects.lookup("M42") is None
    s.pixinsight_scripts = (tmp / "scripts").as_posix()            # fixed in Settings: no restart needed
    settings.save(s)
    assert objects.lookup("NGC 1976")["ra"] == 83.82


def test_read_knowledge_stays_in_the_knowledge_base():
    assert "error" in tools.read_knowledge("../.env")
    assert "error" in tools.read_knowledge("../README.md")
    assert "error" in tools.read_knowledge(str(config.PROJECT / "README.md"))
    doc = tools.read_knowledge("comets")
    assert doc["document"] == "comets.md" and doc["text"]


def _api_error(cls, status):
    response = httpx.Response(status, request=httpx.Request("POST", "http://llm.test/v1/chat/completions"))
    return cls("simulated", response=response, body=None)


def _bare_llm(create):
    """An LLM whose client calls `create` (no key or network needed)."""
    llm = llm_mod.LLM.__new__(llm_mod.LLM)
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm.usage = {"prompt": 0, "completion": 0, "calls": 0}
    return llm


def test_llm_retries_only_what_can_succeed_later(monkeypatch):
    monkeypatch.setattr(jobctx, "sleep", lambda seconds: None)
    calls = []

    def bad_request(**kw):
        calls.append(1)
        raise _api_error(openai.BadRequestError, 400)

    with pytest.raises(openai.BadRequestError):
        _bare_llm(bad_request)._call(model="m", messages=[])
    assert len(calls) == 1                                          # a 400 is final: no 30 s of retries

    replies = [_api_error(openai.RateLimitError, 429), SimpleNamespace(usage=None, choices=[])]

    def rate_limited_once(**kw):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    llm = _bare_llm(rate_limited_once)
    llm._call(model="m", messages=[])
    assert not replies and llm.usage["calls"] == 1


def test_llm_request_stops_waiting_on_cancel():
    release = threading.Event()
    llm = _bare_llm(lambda **kw: release.wait(10))
    with jobctx.use(jobctx.JobContext()) as ctx:
        threading.Timer(0.2, ctx.cancel).start()
        t0 = time.monotonic()
        with pytest.raises(jobctx.Cancelled):
            llm._call(model="m", messages=[])
    assert time.monotonic() - t0 < 2
    release.set()


class _FakeLLM:
    """Scripted model: first asks for load_skill, then answers."""

    def __init__(self, provider=None):
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}
        self.turn = 0
        self.provider = SimpleNamespace(tools=True)

    def chat(self, messages, tools=None, max_tokens=16000):
        self.turn += 1
        if self.turn == 1:
            call = SimpleNamespace(id="c1", function=SimpleNamespace(name="load_skill",
                                                                     arguments=json.dumps({"name": "comet"})))
            return SimpleNamespace(content="", tool_calls=[call])
        assert messages[-1]["role"] == "tool" and "comet_stack" in messages[-1]["content"]
        return SimpleNamespace(content="好的。", tool_calls=None)


def test_agent_session_runs_tools_and_reports_events(tmp_settings, monkeypatch):
    tmp, _ = tmp_settings
    monkeypatch.setattr(session_mod, "LLM", _FakeLLM)
    events = []
    s = session_mod.AgentSession(on_event=lambda kind, data: events.append(kind), log_path=tmp / "log.jsonl")
    assert s.send("处理彗星") == "好的。"
    assert events == ["user", "tool_call", "tool_result", "assistant", "done"]
    assert (tmp / "log.jsonl").read_text(encoding="utf-8").count("\n") == 5


def test_agent_stop_while_idle_does_not_cancel_the_next_message(tmp_settings, monkeypatch):
    tmp, _ = tmp_settings
    monkeypatch.setattr(session_mod, "LLM", _FakeLLM)
    s = session_mod.AgentSession(log_path=tmp / "log.jsonl")
    s.cancel()
    assert s.send("处理彗星") == "好的。"


def test_agent_message_stops_when_its_job_is_cancelled(tmp_settings, monkeypatch):
    tmp, _ = tmp_settings
    monkeypatch.setattr(session_mod, "LLM", _FakeLLM)
    s = session_mod.AgentSession(log_path=tmp / "log.jsonl")
    job = jobctx.JobContext()
    job.cancel()
    with jobctx.use(job):
        assert s.send("x") == "已取消。"


class _TwoCallsLLM(_FakeLLM):
    """Asks for two tools at once; the first one is cancelled while it runs. Afterwards checks that the conversation
    sent to the API answers every tool call (OpenAI-compatible APIs reject it otherwise)."""

    def chat(self, messages, tools=None, max_tokens=16000):
        self.turn += 1
        if self.turn == 1:
            calls = [SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name="slow", arguments="{}")) for i in (1, 2)]
            return SimpleNamespace(content="", tool_calls=calls)
        asked = [c["id"] for m in messages if m.get("tool_calls") for c in m["tool_calls"]]
        answered = [m["tool_call_id"] for m in messages if m["role"] == "tool"]
        assert asked == answered == ["c1", "c2"]
        return SimpleNamespace(content="继续。", tool_calls=None)


def test_cancel_during_a_tool_call_keeps_the_conversation_valid(tmp_settings, monkeypatch):
    tmp, _ = tmp_settings
    monkeypatch.setattr(session_mod, "LLM", _TwoCallsLLM)

    def slow():
        jobctx.current().cancel()          # the user presses Stop while the tool (PixInsight) runs
        jobctx.check_cancelled()

    monkeypatch.setitem(tools.REGISTRY, "slow", {"fn": slow, "schema": {}})
    s = session_mod.AgentSession(log_path=tmp / "log.jsonl")
    assert s.send("处理") == "已取消。"
    assert s.send("继续") == "继续。"


class _PromptedLLM(_FakeLLM):
    """A local model without native tool calling: answers with a JSON call in a code fence."""

    def __init__(self, provider=None):
        super().__init__(provider)
        self.provider = SimpleNamespace(tools=False)

    def chat(self, messages, tools=None, max_tokens=16000):
        assert tools is None
        self.turn += 1
        if self.turn == 1:
            assert "load_skill(" in messages[0]["content"]
            fence = "`" * 3
            reply = f'先加载技能。{fence}json {{"tool": "load_skill", "args": {{"name": "comet"}}}} {fence}'
            return SimpleNamespace(content=reply, tool_calls=None)
        assert messages[-1]["role"] == "user" and messages[-1]["content"].startswith("TOOL RESULT load_skill")
        return SimpleNamespace(content="完成。", tool_calls=None)


def test_agent_session_prompted_tool_mode(tmp_settings, monkeypatch):
    tmp, _ = tmp_settings
    monkeypatch.setattr(session_mod, "LLM", _PromptedLLM)
    events = []
    s = session_mod.AgentSession(on_event=lambda kind, data: events.append(kind), log_path=tmp / "log.jsonl")
    assert s.send("处理彗星") == "完成。"
    assert events == ["user", "tool_call", "tool_result", "assistant", "done"]


def test_prompted_calls_parsing():
    assert session_mod.prompted_calls("没有工具调用") == []
    assert session_mod.prompted_calls('{"answer": 1}') == []
    (call,) = session_mod.prompted_calls('{"tool": "list_targets"}')
    assert call.function.name == "list_targets" and json.loads(call.function.arguments) == {}
