"""Start the local API server (the desktop app's backend).

    python -m astroflow.api [--port 0] [--static <built renderer dir>] [--watch-stdin] [--dev-origin http://localhost:5173]

The token comes from the ASTROFLOW_TOKEN environment variable (the Electron main process generates one per launch;
command-line arguments are visible to other processes). When it is ready the server prints one line:
    ASTROFLOW_READY {"port": 51234}
With --watch-stdin it shuts down (cancelling the running job and its PixInsight) when stdin closes, i.e. when the
Electron app exits or crashes.
"""
import argparse
import json
import os
import secrets
import socket
import sys
import threading

import uvicorn

from .app import Services, create_app


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=0, help="0 = any free port")
    ap.add_argument("--static", help="built renderer (index.html) to serve at /")
    ap.add_argument("--watch-stdin", action="store_true", help="exit when stdin closes (parent process gone)")
    ap.add_argument("--dev-origin", action="append", default=[], help="extra allowed Origin (Vite dev server)")
    a = ap.parse_args()

    token = os.environ.get("ASTROFLOW_TOKEN") or secrets.token_urlsafe(32)
    if "ASTROFLOW_TOKEN" not in os.environ:
        print(f"ASTROFLOW_TOKEN not set; generated {token}", file=sys.stderr, flush=True)
    services = Services()
    app = create_app(token, static_dir=a.static, dev_origins=tuple(a.dev_origin), services=services)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == "win32":     # Windows' SO_REUSEADDR would let another process bind the same port: forbid that
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:                           # quick restarts on a fixed (development) port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", a.port))
    port = sock.getsockname()[1]

    if a.watch_stdin:
        def watch():
            for _ in sys.stdin:
                pass
            services.shutdown()
            os._exit(0)
        threading.Thread(target=watch, name="stdin-watch", daemon=True).start()

    print("ASTROFLOW_READY " + json.dumps({"port": port}), flush=True)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


if __name__ == "__main__":
    main()
