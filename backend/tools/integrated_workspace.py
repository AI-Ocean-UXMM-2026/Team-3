"""Persistent, loopback-only integration of the selected frontend and authoritative backend."""

import argparse
import os
import re
import socket

import uvicorn

from app.db.session import BACKEND_ROOT
from tools.backend_test_dashboard.runtime import Sandbox
from tools.backend_test_dashboard.server import create_dashboard


class WorkspaceSandbox(Sandbox):
    def __init__(self, state_name="local"):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", state_name):
            raise ValueError("Use a simple workspace state name")
        self.state_name = state_name
        super().__init__()

    def storage_directory(self):
        base = (BACKEND_ROOT / "data" / "integrated-workspaces").resolve()
        target = (base / self.state_name).resolve()
        if not target.is_relative_to(base):
            raise ValueError("Workspace path is outside its isolated storage root")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def bootstrap(self):
        return {
            **super().bootstrap(),
            "database": "persistent local integration SQLite; separate from normal development DB",
        }


def application(origin="http://127.0.0.1:8780", state_name="local", temporary=False):
    if os.environ.get("LANNPYA_ENVIRONMENT", "local") not in {"local", "test"}:
        raise ValueError("Local workspace is disabled in production")
    frontend = BACKEND_ROOT.parent / "frontend"
    return create_dashboard(
        origin,
        sandbox_factory=(Sandbox if temporary else lambda: WorkspaceSandbox(state_name)),
        frontend=frontend,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--state", default="local")
    parser.add_argument("--temporary", action="store_true")
    args = parser.parse_args()
    if os.environ.get("LANNPYA_ENVIRONMENT", "local") not in {"local", "test"}:
        parser.error("Local integration is disabled in production")
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a valid local port")
    listener = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
    except OSError:
        listener.close()
        parser.error("Port unavailable; choose another --port")
    origin = f"http://127.0.0.1:{args.port}"
    app = application(origin, args.state, args.temporary)
    server = uvicorn.Server(
        uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="warning")
    )
    app.state.server = server
    print(
        f"LOCAL TEST INTEGRATION: {origin} — AI MOCK; not public production authentication",
        flush=True,
    )
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
