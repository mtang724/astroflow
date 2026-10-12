"""Agent conversations for the app: each message runs as a job in the shared queue (its tool calls start PixInsight
jobs, which must not overlap with other jobs; cancelling the job stops the message), streams its events to the event
hub and keeps a history for page reloads."""
import time
import uuid
from collections import deque

from .. import jobctx
from ..agent.session import AgentSession


class AgentBusy(RuntimeError):
    pass


class AgentService:
    def __init__(self, jobs, hub):
        self.jobs = jobs
        self.hub = hub
        self._sessions = {}

    def create(self, target=None, provider=None):
        sid = uuid.uuid4().hex[:8]
        entry = {"sid": sid, "target": target, "events": deque(maxlen=3000), "job_id": None, "created": time.time()}

        def on_event(kind, data):
            item = {"kind": kind, "data": data, "t": time.time()}
            entry["events"].append(item)
            self.hub.publish("agent.event", {"sid": sid, **item})

        entry["session"] = AgentSession(target, provider=provider, on_event=on_event)
        self._sessions[sid] = entry
        return self.public(sid)

    def public(self, sid):
        e = self._entry(sid)
        s = e["session"]
        return {"sid": sid, "target": e["target"], "provider": s.llm.provider.name, "model": s.llm.planner,
                "vision": bool(s.llm.vision), "native_tools": s.native, "job_id": e["job_id"],
                "events": list(e["events"])}

    def send(self, sid, text):
        e = self._entry(sid)
        job = self.jobs.get(e["job_id"]) if e["job_id"] else None
        if job and job.state in ("queued", "running"):
            raise AgentBusy("the agent is still working on the previous message")

        def work():
            answer = e["session"].send(text)
            jobctx.check_cancelled()          # a cancelled message ends its job as cancelled, not done
            return answer

        job = self.jobs.submit("agent", f"Agent: {text[:60]}", work, target=e["target"])
        e["job_id"] = job.id
        return job

    def cancel(self, sid):
        """Queued: the message is dropped. Running: the message stops (it runs inside the job's context)."""
        e = self._entry(sid)
        if e["job_id"]:
            self.jobs.cancel(e["job_id"])

    def list(self):
        return [{"sid": sid, "target": e["target"], "created": e["created"], "messages": len(e["events"])}
                for sid, e in self._sessions.items()]

    def _entry(self, sid):
        if sid not in self._sessions:
            raise KeyError(f"no agent session {sid}")
        return self._sessions[sid]
