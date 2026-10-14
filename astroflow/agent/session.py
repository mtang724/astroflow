"""One conversation with the processing agent, usable from the command line and the desktop app.

    s = AgentSession(target="M8", on_event=lambda kind, data: ...)
    s.send("按流程完整处理这个目标")     # runs tool calls until the model answers; returns the answer
    s.send("饱和度再高一点")             # the same conversation continues
    s.cancel()                           # from another thread: stops between steps and inside PixInsight jobs

A message runs as part of the caller's job (jobctx.current(), e.g. the app's job queue): cancelling that job cancels
the message, and the PixInsight progress of its tool calls reaches the job's listener as well.

Events (kind, data) - every one is also appended to the JSONL log:
    user, assistant {text}, tool_call {tool, args}, tool_result {tool, ok, text}, job {kind, ...} (progress of
    PixInsight / pipeline work started by a tool), done {usage, pi_jobs}, cancelled, error {message}
"""
import json
import re
import time
import traceback
import uuid
from types import SimpleNamespace

from .. import config, jobctx, settings
from ..i18n import language, tr
from . import skills, tools
from .llm import LLM

ROLE = """你是 astroflow 的天文摄影后期处理 agent：把用户拍摄的深空目标和彗星处理成成品图，并能按用户的要求调整。
你通过工具做事：整理文件、WBPP 叠加、无界面 PixInsight 的配方阶段、彗星叠加、指标与参考作品对比、看图（视觉模型）。"""

PRINCIPLES = """## 原则
- 开始任何处理任务前先 load_skill('astro-workflow')，再按目标类型加载对应技能；技能里引用的资料用 read_skill_file / read_knowledge 读。
- 脚本能确定的交给工具（数值、执行）；需要审美和判断的由你和视觉模型决定，但判断要有依据（指标或看图结论）。
- 每次只改一两个参数并说明理由；同一阶段最多重跑 3 次。
- 不要编造结果；工具报错要读错误信息再调整，连续失败两次就停下并说明。
- 移动/覆盖用户文件的操作（organize apply）只在用户明确要求时做。"""


def target_section(target):
    """When the conversation belongs to one target (the app's per-target chat), say so: "这个目标" means it."""
    if not target:
        return ""
    name = target
    try:
        name = tools.resolve(target).name
    except FileNotFoundError:
        pass
    return (f"## 当前目标\n这次对话针对 **{name}**（{target}）。用户说“这个目标”“它”时指的就是它；"
            "工具的 target 参数直接用这个路径。")


def system_prompt(target=None):
    s = settings.get()
    e = s.equipment
    p = s.preferences
    lo, hi = p.get("subject_chroma_ratio", [0.8, 1.2])
    lang = "English" if language() == "en" else "中文"
    gear = (f"## 用户器材\n相机 {e.get('camera')}（{e.get('sensor')}，像元 {e.get('pixel_um')} µm），"
            f"{e.get('telescope')}，焦距约 {e.get('focal_mm')} mm。数据根目录：{config.ASTRO_ROOT}。")
    taste = (f"## 用户偏好\n- 颜色要明显：主体色度对比同类参考作品（compare_with_references 的 subject_chroma.ratio）"
             f"目标 {lo}–{hi}，但不能有荧光感或彩色斑块。\n"
             f"- 成品导出 {', '.join(p.get('export_formats', ['png']))}；小目标可以额外 export_crop。\n"
             f"- 用{lang}和用户沟通，回答简洁。")
    index = skills.index_text(skills.discover())
    parts = [ROLE, gear, taste, target_section(target), "## 技能（按需加载）\n" + index, PRINCIPLES]
    return "\n\n".join(p for p in parts if p)


def user_message(task, target=None):
    if not target:
        return task or "列出可以处理的目标并逐个处理。"
    return f"目标：{target}。{task or '按流程完整处理这个目标并给出成品。'}"


class AgentSession:
    def __init__(self, target=None, provider=None, on_event=None, max_turns=80, max_pi_jobs=30, log_path=None):
        self.llm = LLM(provider)
        self.target = target
        self.on_event = on_event
        self.max_turns = max_turns
        self.tool_ctx = tools.ToolContext(self.llm, max_pi_jobs)
        self.job = None                           # the context of the message being worked on (None when idle)
        self.native = self.llm.provider.tools     # False: tools described in the prompt, calls parsed from JSON
        prompt = system_prompt(target)
        if not self.native:
            prompt += "\n\n" + prompted_tools_text()
        self.messages = [{"role": "system", "content": prompt}]
        self.log_path = log_path or _default_log(target)

    # ------------------------------------------------------------------ public
    def send(self, text):
        """Add a user message and run until the model stops calling tools. Returns its final answer."""
        self.job = jobctx.JobContext(emit=lambda kind, data: self._event("job", {"kind": kind, **data}),
                                     parent=jobctx.current())
        self.messages.append({"role": "user", "content": text})
        self._event("user", {"text": text})
        try:
            with tools.bound(self.tool_ctx), jobctx.use(self.job):
                return self._loop()
        except jobctx.Cancelled:
            self._event("cancelled", {})
            return tr("已取消。")
        except Exception as e:
            self._event("error", {"message": f"{type(e).__name__}: {e}"})
            raise
        finally:                               # a cancel applies to this message only; the next one starts clean
            self.job = None

    def cancel(self):
        """Stop the message being worked on (from another thread); nothing to stop when idle."""
        job = self.job
        if job is not None:
            job.cancel()

    # ------------------------------------------------------------------ internals
    def _loop(self):
        for _ in range(self.max_turns):
            self.job.check()
            msg = self.llm.chat(self.messages, tools=tools.schemas() if self.native else None)
            self.job.check()
            calls = list(msg.tool_calls or []) if self.native else prompted_calls(msg.content)
            entry = {"role": "assistant", "content": msg.content or ""}
            if self.native and calls:
                entry["tool_calls"] = [{"id": c.id, "type": "function",
                                        "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                       for c in calls]
            rc = getattr(msg, "reasoning_content", None) or (getattr(msg, "model_extra", None) or {}).get("reasoning_content")
            if rc:
                entry["reasoning_content"] = rc        # some reasoning models require it to be passed back
            self.messages.append(entry)
            if msg.content and (self.native or not calls):  # a prompted JSON call is not an answer for the user
                self._event("assistant", {"text": msg.content})
            if not calls:
                self._event("done", {"usage": self.llm.usage, "pi_jobs": self.tool_ctx.pi_jobs})
                return msg.content or ""
            for i, call in enumerate(calls):
                try:
                    result = self._run_tool(call)
                except jobctx.Cancelled:       # every call needs an answer, or the API rejects the next message
                    for unanswered in calls[i:]:
                        self._answer(unanswered, json.dumps({"error": "cancelled by the user"}))
                    raise
                self._answer(call, result)
        self._event("error", {"message": f"stopped after {self.max_turns} turns"})
        return tr("达到最大轮数，已停止。请查看日志。")

    def _answer(self, call, text):
        if self.native:
            self.messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
        else:
            self.messages.append({"role": "user", "content": f"TOOL RESULT {call.function.name}:\n{text}"})

    def _run_tool(self, call):
        name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        self._event("tool_call", {"tool": name, "args": args})
        ok = True
        try:
            result = tools.call(name, args)
        except jobctx.Cancelled:
            raise
        except Exception as e:
            ok = False
            result = {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > 24000:
            text = text[:24000] + "...(trimmed)"
        self._event("tool_result", {"tool": name, "ok": ok, "text": text[:3000]})
        return text

    def _event(self, kind, data):
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "kind": kind, "data": data},
                                   ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
        if self.on_event is not None:
            self.on_event(kind, data)


def prompted_tools_text():
    """Tool catalogue + calling protocol for models without native function calling (small local models)."""
    lines = ["## 调用工具的方式（当前模型不支持原生工具调用）",
             '需要用工具时，只回复一个 JSON 对象，不要别的文字：{"tool": "<工具名>", "args": {...}}。'
             "工具结果会以“TOOL RESULT <工具名>:”开头的消息返回。任务完成后正常用文字回答（不要 JSON）。", "可用工具："]
    for sch in tools.schemas():
        f = sch["function"]
        req = set(f["parameters"].get("required", []))
        params = ", ".join(f"{k}{'' if k in req else '?'}: {v['type']}" for k, v in f["parameters"]["properties"].items())
        lines.append(f"- {f['name']}({params}): {f['description'][:220]}")
    return "\n".join(lines)


def prompted_calls(text):
    """A {"tool": ..., "args": {...}} object in the reply (bare or in a code fence) -> one tool call, else []."""
    if not text:
        return []
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        return []
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    if not isinstance(obj, dict) or not isinstance(obj.get("tool"), str):
        return []
    args = json.dumps(obj.get("args") or {}, ensure_ascii=False)
    return [SimpleNamespace(id=f"p{uuid.uuid4().hex[:8]}", function=SimpleNamespace(name=obj["tool"], arguments=args))]


def _default_log(target):
    if target:
        try:
            return tools.resolve(target) / "Post" / "agent_log.jsonl"
        except FileNotFoundError:
            pass
    return config.RUNS / f"agent-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
