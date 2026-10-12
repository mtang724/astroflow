"""Command-line front end of the processing agent (the desktop app uses AgentSession directly).

    python -m astroflow.agent.run "M8"                      # process one target end to end
    python -m astroflow.agent.run "M8" --task "只重做 starless 阶段，饱和度再高一点"
    python -m astroflow.agent.run --task "看看哪些目标可以处理，逐个处理"   # let it choose

The LLM provider (DeepSeek, OpenAI, a local Ollama / LM Studio ...) comes from the user settings. Every message and
tool call is logged to Post/agent_log.jsonl (or <runs>/agent-*.jsonl); the final summary goes to Post/report.md.
"""
import argparse
import json

from .session import AgentSession, user_message


def _print(kind, data):
    if kind == "job" and data.get("kind") not in ("pi.job", "stage.started", "stage.finished"):
        return
    s = data.get("text") if isinstance(data, dict) and "text" in data else json.dumps(data, ensure_ascii=False, default=str)
    print(f"[{kind}] {s[:600]}", flush=True)


def run(task, target=None, max_turns=80, max_pi_jobs=30, verbose=True):
    session = AgentSession(target, on_event=_print if verbose else None, max_turns=max_turns, max_pi_jobs=max_pi_jobs)
    return session.send(user_message(task, target))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="target name, e.g. 'M8' (omit to let the agent choose)")
    ap.add_argument("--task", default="", help="what to do (Chinese is fine)")
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--max-pi-jobs", type=int, default=30)
    a = ap.parse_args()
    print(run(a.task, a.target, a.max_turns, a.max_pi_jobs))
