import argparse
import os
import socket

import uvicorn

from tools.backend_test_dashboard.server import create_dashboard


def main():
    parser = argparse.ArgumentParser(description="Local fictional-data backend testing dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535")
    if os.environ.get("LANNPYA_ENVIRONMENT", "local") not in {"local", "test"}:
        parser.error("Dashboard is disabled in a production environment")
    origin = f"http://127.0.0.1:{args.port}"
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
    except OSError:
        listener.close()
        parser.error("Loopback port unavailable. Choose another --port; no process was stopped.")
    print(f"TEST MODE — fictional data only. Open {origin}", flush=True)
    print(
        "Ctrl+C stops dashboard and backend contexts and removes the temporary database.",
        flush=True,
    )
    application = create_dashboard(origin)
    config = uvicorn.Config(application, access_log=False, proxy_headers=False, log_level="warning")
    server = uvicorn.Server(config)
    application.state.server = server
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
