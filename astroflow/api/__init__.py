"""Local HTTP + WebSocket API for the desktop app (Electron + React).

A thin adapter over astroflow.services / astroflow.agent: no processing logic lives here. The server only listens on
127.0.0.1, requires the per-launch token (Authorization header, `t` query parameter once, then an HttpOnly cookie),
rejects foreign Host / Origin headers (DNS-rebinding defence) and also serves the built React app, so the renderer
and the API share one origin.

    python -m astroflow.api --port 0 --token <secret> [--static <built renderer dir>] [--watch-stdin]
"""
