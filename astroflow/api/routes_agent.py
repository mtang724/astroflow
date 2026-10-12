"""Agent chat: sessions, messages (each runs as a job), cancel."""
from fastapi import APIRouter, HTTPException, Request

from ..agent.llm import LLMError
from .agents import AgentBusy
from .models import AgentCreateIn, AgentMessageIn, AgentSessionOut, Job, Ok

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _agents(request):
    return request.app.state.services.agents


@router.post("/sessions", response_model=AgentSessionOut)
def create_session(body: AgentCreateIn, request: Request):
    try:
        return _agents(request).create(body.target, provider=None if not body.provider else _provider(body.provider))
    except (LLMError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


def _provider(name):
    from .. import settings
    return settings.get().provider(name)


@router.get("/sessions/{sid}", response_model=AgentSessionOut)
def get_session(sid: str, request: Request):
    try:
        return _agents(request).public(sid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/sessions/{sid}/messages", response_model=Job)
def send(sid: str, body: AgentMessageIn, request: Request):
    try:
        return _agents(request).send(sid, body.text).public()
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except AgentBusy as e:
        raise HTTPException(409, str(e)) from e


@router.post("/sessions/{sid}/cancel", response_model=Ok)
def cancel(sid: str, request: Request):
    try:
        _agents(request).cancel(sid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return Ok()
