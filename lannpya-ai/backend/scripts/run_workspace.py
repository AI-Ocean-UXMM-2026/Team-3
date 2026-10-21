"""Start the local workspace with three server-bound identities, no merchant."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from uuid import uuid4
from sqlalchemy import select
from app.db.migrations import upgrade_database
from app.db.models import User
from app.db.rider_models import RiderProfile
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole


def prepare():
    data = BACKEND_ROOT / "data"
    data.mkdir(exist_ok=True)
    database_url = "sqlite+pysqlite:///" + (data / "workspace.sqlite3").as_posix()
    db = Database(database_url)
    upgrade_database(db)
    actors = {}
    try:
        with db.sessions.begin() as session:
            for key, name, role, port in [
                ("admin", "Admin", UserRole.ADMIN, 8000),
                ("rider", "Ko Aung", UserRole.RIDER, 8001),
                ("rider2", "Ko Wai", UserRole.RIDER, 8002),
            ]:
                user = session.scalar(
                    select(User).where(User.email == f"{key}@workspace.local.invalid")
                )
                if user is None:
                    user = User(
                        id=uuid4(), name=name, email=f"{key}@workspace.local.invalid", role=role
                    )
                    session.add(user)
                    session.flush()
                if user.role != role:
                    raise RuntimeError(
                        "Existing workspace identity has an unexpected role; refusing to replace it."
                    )
                if role == UserRole.RIDER and session.get(RiderProfile, user.id) is None:
                    session.add(RiderProfile(id=user.id, operational_status="AVAILABLE"))
                actors[key] = {
                    "name": user.name,
                    "id": str(user.id),
                    "base_url": f"http://127.0.0.1:{port}",
                    "token": secrets.token_urlsafe(48),
                    "port": port,
                }
    finally:
        db.dispose()
    access = data / "workspace_access.json"
    access.write_text(json.dumps(actors, indent=2), encoding="utf-8")
    try:
        access.chmod(0o600)
    except OSError:
        pass
    return database_url, actors, access


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check real HTTP startup/role boundaries, then stop all servers without creating orders",
    )
    args = parser.parse_args()
    for port in (8000, 8001, 8002):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} is occupied. Stop that server first.")
    database_url, actors, access = prepare()
    processes = []
    try:
        for actor in actors.values():
            env = os.environ.copy()
            env.update(
                LANNPYA_ENVIRONMENT="local",
                LANNPYA_ORDER_MANAGEMENT_ENABLED="true",
                LANNPYA_SERVE_WORKSPACE="true",
                LANNPYA_DATABASE_URL=database_url,
                LANNPYA_DEV_ACTOR_ID=actor["id"],
                LANNPYA_DEV_ACCESS_TOKEN=actor["token"],
                LANNPYA_PARSER_MODE="hybrid",
                LANNPYA_AI_PROVIDER="mock",
                LANNPYA_CORS_ORIGINS=json.dumps(["http://127.0.0.1:8000", "http://localhost:8000"]),
                LANNPYA_BUYER_FRONTEND_BASE_URL="http://127.0.0.1:8000",
            )
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(actor["port"]),
                        "--no-access-log",
                        "--no-proxy-headers",
                    ],
                    cwd=BACKEND_ROOT,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            )
        print("Local workspace: http://127.0.0.1:8000/api.html", flush=True)
        print(f"Private connection details: {access} (do not share or serve)", flush=True)
        print(
            "Browser data and other databases are untouched. Ctrl+C stops all servers.", flush=True
        )
        if args.check:
            for actor in actors.values():
                ready = False
                for attempt in range(30):
                    if any(p.poll() is not None for p in processes):
                        raise RuntimeError("A backend exited before readiness.")
                    try:
                        with urlopen(
                            Request(
                                actor["base_url"] + "/api/session",
                                headers={"X-Dev-Access-Token": actor["token"]},
                            ),
                            timeout=2,
                        ) as result:
                            identity = json.load(result)
                        if identity["id"] != actor["id"]:
                            raise RuntimeError("Server identity mismatch.")
                        ready = True
                        break
                    except OSError:
                        time.sleep(0.25)
                if not ready:
                    raise RuntimeError("Backend failed the local readiness check.")
                with urlopen(actor["base_url"] + "/api.html", timeout=2) as result:
                    if result.status != 200 or result.headers.get("Cache-Control") != "no-store":
                        raise RuntimeError("Frontend did not load with private cache policy.")
            print(
                "HTTP checks passed: three isolated actors and the allowlisted UI; no orders created.",
                flush=True,
            )
            return
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
        raise RuntimeError("A workspace API stopped; shutting down the remaining instances.")
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
