"""FastAPI application: security guard, shared services, routers, event WebSocket, and the built React app."""
import asyncio
import hmac
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import pi
from ..services.jobs import JobManager
from . import (routes_agent, routes_files, routes_frames, routes_jobs, routes_presets, routes_settings, routes_setup,
               routes_share, routes_targets)
from .agents import AgentService
from .hub import EventHub

COOKIE = "astroflow_token"
LOCAL_HOSTS = ("127.0.0.1", "localhost")


class Services:
    """What the routes share: the job queue, agent sessions and the event hub."""

    def __init__(self):
        self.hub = EventHub()
        self.jobs = JobManager()
        self.jobs.subscribe(self.hub.publish)
        self.agents = AgentService(self.jobs, self.hub)

    def shutdown(self, wait=10.0):
        """Before the process exits: cancel the jobs, give the running one `wait` seconds to stop (cancelling kills
        its PixInsight), then kill any PixInsight still running - a headless one left behind would block the next
        launch's jobs."""
        for job in self.jobs.jobs():
            if job.state in ("queued", "running"):
                self.jobs.cancel(job.id)
        t0 = time.time()
        while self.jobs.busy() and time.time() - t0 < wait:
            time.sleep(0.2)
        pi.kill_started()


def create_app(token, static_dir=None, dev_origins=(), services=None):
    services = services or Services()

    @asynccontextmanager
    async def lifespan(app):
        services.hub.bind(asyncio.get_running_loop())
        yield

    app = FastAPI(title="astroflow", version="0.2.1", lifespan=lifespan)
    app.state.services = services
    app.state.token = token

    def token_ok(candidate):
        return bool(candidate) and hmac.compare_digest(candidate.encode(), token.encode())

    def presented_token(headers, query, cookies):
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return query.get("t") or cookies.get(COOKIE) or ""

    def origin_ok(headers):
        host = headers.get("host", "")
        if host.rsplit(":", 1)[0].strip("[]") not in LOCAL_HOSTS:
            return False                                       # DNS rebinding: a foreign name pointing at 127.0.0.1
        origin = headers.get("origin")
        return origin is None or origin == f"http://{host}" or origin in dev_origins

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if not origin_ok(request.headers):
            return JSONResponse({"detail": "forbidden origin"}, status_code=403)
        path = request.url.path
        given = presented_token(request.headers, request.query_params, request.cookies)
        if path.startswith("/api/") and path != "/api/health" and not token_ok(given):
            return JSONResponse({"detail": "missing or wrong token"}, status_code=401)
        response = await call_next(request)
        if token_ok(request.query_params.get("t", "")):      # first page load: remember the token in a cookie
            response.set_cookie(COOKIE, token, httponly=True, samesite="strict")
        return response

    @app.get("/api/health")
    def health():
        return {"ok": True, "busy": services.jobs.busy()}

    @app.post("/api/auth")
    def auth():
        """Called once by the renderer with the token header: sets the cookie that <img> and WebSocket requests use."""
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict")
        return response

    @app.websocket("/api/events")
    async def events(ws: WebSocket):
        if not origin_ok(ws.headers) or not token_ok(presented_token(ws.headers, ws.query_params, ws.cookies)):
            await ws.close(code=4401)
            return
        await ws.accept()
        services.hub.bind(asyncio.get_running_loop())    # idempotent; also covers servers started without lifespan
        q = services.hub.subscribe()

        async def pump():
            await ws.send_text(json.dumps({"type": "jobs.snapshot",
                                           "data": [j.public() for j in services.jobs.jobs()]}, default=str))
            while True:
                await ws.send_text(await q.get())

        async def until_disconnect():                 # notice a closed client even when no events are flowing
            while (await ws.receive())["type"] != "websocket.disconnect":
                pass

        tasks = [asyncio.create_task(pump()), asyncio.create_task(until_disconnect())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            for t in tasks:
                t.cancel()
            services.hub.unsubscribe(q)

    for module in (routes_settings, routes_setup, routes_targets, routes_frames, routes_presets, routes_share, routes_jobs,
                   routes_agent, routes_files):
        app.include_router(module.router)

    if static_dir and Path(static_dir, "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="renderer")
    return app
