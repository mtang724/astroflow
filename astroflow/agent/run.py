"""DeepSeek-driven post-processing agent.

    python -m astroflow.agent.run "M8"                      # process one target end to end
    python -m astroflow.agent.run "M8" --task "只重做 starless 阶段，饱和度再高一点"
    python -m astroflow.agent.run --task "看看哪些目标可以处理，逐个处理"   # let it choose

The planner (deepseek-v4-pro) reads the knowledge base and references, runs pipeline stages through tools, looks at
every result with the vision model (deepseek-flash) and adjusts parameters until the image is acceptable, then
writes Post/report.md. Every message and tool call is logged to Post/agent_log.jsonl (or .runs/agent-*.jsonl).
"""
import argparse
import json
import time
import traceback

from .. import config
from . import tools
from .llm import LLM

SYSTEM = """你是一个天文摄影后期处理 agent，负责把用户在 F:\\AstroPhotograph\\In Processing 里的深空目标处理成成品图。
用户器材：ZWO ASI2600MC Air（彩色 OSC，IMX571，无滤镜=宽带 RGB），72mm ED 折射镜（约 563mm，1.38″/px，视场约 2.4°×1.6°）。
后期工具：无界面 PixInsight（通过工具调用），RC 三件套（BXT/NXT/SXT），SPCC + 本地 Gaia DR3/SP。

## 工作方式
1. 先 inspect_target，再 read_knowledge('ep1' 或 'ep2'，按目标类型)、read_knowledge('checklists')，再 get_references 看同目标高赞作品与指纹。
   - 目标类型由 inspect_target 给出；若为 unknown，你根据天体知识判断（星系→osc_galaxy；星云/行星状星云/超新星遗迹→osc_broadband_nebula），在第一次 run_stage 时用 recipe 参数指定。彗星等不适用的目标：不要处理，finish 并说明原因。
2. 按配方阶段顺序 run_stage：linear → stretch → stars → starless → stars_color → combine。
3. 每个阶段跑完都要检查：先看返回的数字指标，再用 look 让视觉模型看预览图（可以带参考图 ref:peer_00 等一起比较）。
   - linear：look 背景模型('10_gc_model'，若用 GC)是否只是平滑梯度、不含天体形状；看 '10a_after_cc' 背景是否中性灰、星点是否以白为主、星云/星系颜色是否合理；
     metrics.background_cast 的 R/G、B/G 应接近 1（±0.05）。若 color_calibration 退回了 bncc（info.method），说明 SPCC 失败，要在总结中写明。
   - stretch：中值亮度是否合适、核心是否过曝、暗部是否被切掉。
   - stars：去星是否干净（'30_starless' 不应有明显星点残留），'31_stars' 是否正常。
   - starless：结构是否增强但不生硬、饱和度/对比度/背景亮度与 peer 参考相比如何、噪声与涂抹感。
   - combine：整体观感，与 best/peer 参考对比；compare_with_references 给出数值差。
4. 不满意就带 overrides（按步骤 id）重跑该阶段；一次只改一两个参数，说明理由。每个阶段最多重跑 3 次，避免无限调参。
   需要配方以外的操作时用 extra_steps / replace_steps（步骤与参数见 read_knowledge('steps')）。
5. 满意后 finish（中文总结：做了什么、关键参数、和参考相比的差距、需要用户确认或下次拍摄改进的地方），并用 remember 记下对这个目标有用的经验。

## 处理新拍的数据（任务没有指定目标时）
organize（先预览；用户任务要求时 apply=true）→ list_targets → 对每个有暗场、无 master 的目标 stack → 逐个按上面的流程处理 → 最后汇总。

## 用户偏好（2026-10-10 反馈）
- 第一版成品“大部分饱和度太低”。颜色要明显、对标 peer 参考的主体色度（compare_with_references 的 subject_chroma.ratio 0.8–1.2），但不能出现荧光感或彩色斑块。
- 每个成品都要导出 PNG（流水线自动完成）。小目标可以额外 export_crop 出裁切版。

## 原则
- 脚本能确定的交给工具（数值、执行）；需要审美与判断的由你和视觉模型决定，但判断要有依据（指标或看图结论）。
- 优先遵循资料库里视频教程的流程与参数，参考作品用来校准“应该长什么样”，宽带彩机不要模仿窄带 SHO/HOO 配色。
- 不要编造结果；工具报错要读错误信息并调整，连续失败两次就停止该目标并在 finish 里说明。
- 缺暗场（calibration_warnings 含 NO DARKS）的目标不要叠加，直接 finish 说明需要补拍暗场。
- 只用中文和用户沟通；最终回复简洁列出每个目标的结果与报告路径。
"""


def log_path(target):
    if target:
        try:
            d = tools.resolve(target)
            return d / "Post" / "agent_log.jsonl"
        except FileNotFoundError:
            pass
    p = config.PROJECT / ".runs" / f"agent-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def run(task, target=None, max_turns=80, max_pi_jobs=30, verbose=True):
    llm = LLM()
    tools.LLM_REF["llm"] = llm
    tools.BUDGET.__init__(max_pi_jobs)
    lp = log_path(target)
    lp.parent.mkdir(parents=True, exist_ok=True)

    def log(kind, data):
        with open(lp, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "kind": kind, "data": data}, ensure_ascii=False,
                               default=str) + "\n")
        if verbose:
            s = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
            print(f"[{kind}] {s[:600]}", flush=True)

    user = task if not target else f"目标：{target}。{task or '按流程完整处理这个目标并给出成品。'}"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    log("task", user)
    for _ in range(max_turns):
        msg = llm.chat(messages, tools=tools.schemas())
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function",
                                    "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                   for c in msg.tool_calls]
        rc = getattr(msg, "reasoning_content", None) or (getattr(msg, "model_extra", None) or {}).get("reasoning_content")
        if rc:
            entry["reasoning_content"] = rc   # some reasoning models require it to be passed back
        messages.append(entry)
        if msg.content:
            log("assistant", msg.content)
        if not msg.tool_calls:
            log("done", {"usage": llm.usage, "pi_jobs": tools.BUDGET.pi_jobs})
            return msg.content
        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            log("call", {"tool": name, "args": args})
            try:
                if name not in tools.REGISTRY:
                    raise KeyError(f"unknown tool {name}")
                result = tools.REGISTRY[name]["fn"](**args)
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}
            text = json.dumps(result, ensure_ascii=False, default=str)
            if len(text) > 24000:
                text = text[:24000] + "...(trimmed)"
            log("result", {"tool": name, "result": text[:3000]})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
    log("stopped", f"max_turns {max_turns} reached")
    return "达到最大轮数，已停止。请查看日志。"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="target name, e.g. 'M8' (omit to let the agent choose)")
    ap.add_argument("--task", default="", help="what to do (Chinese is fine)")
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--max-pi-jobs", type=int, default=30)
    a = ap.parse_args()
    print(run(a.task or ("按流程完整处理这个目标并给出成品。" if a.target else "列出可以处理的目标并逐个处理。"),
              a.target, a.max_turns, a.max_pi_jobs))
