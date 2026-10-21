"""Two OS clients submit the same order version to an isolated loopback API."""

import json
import os
import subprocess
import sys
from uuid import UUID, uuid4

from demo_mvp import LocalDemo
from sqlalchemy import func, select

from app.db.models import DeliveryEvent, Order, User
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole

CHILD = """
import json, sys
import httpx2 as httpx
job = json.load(sys.stdin)
with httpx.Client(timeout=10) as client:
    response = client.patch(job['url'], headers=job['headers'], json=job['body'])
    print(response.status_code)
"""


def main():
    demo, children = LocalDemo(), []
    try:
        actor, merchant = uuid4(), uuid4()
        with demo.database.sessions.begin() as session:
            session.add_all(
                [
                    User(
                        id=actor,
                        name="Process fixture dispatcher",
                        email="d@race.invalid",
                        role=UserRole.DISPATCHER,
                    ),
                    User(
                        id=merchant,
                        name="Process fixture merchant",
                        email="m@race.invalid",
                        role=UserRole.MERCHANT,
                    ),
                ]
            )
        client = demo.start("dispatcher", actor)
        created = client.post(
            "/api/orders",
            json={
                "merchant_id": str(merchant),
                "structured": {"township": "Hlaing", "cod_amount": "0"},
            },
        )
        assert created.status_code == 201
        row = created.json()
        for _ in range(2):
            children.append(
                subprocess.Popen(
                    [sys.executable, "-c", CHILD],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            )
        for i, child in enumerate(children):
            child.stdin.write(
                json.dumps(
                    {
                        "url": demo.private["dispatcher"]["base_url"] + f"/api/orders/{row['id']}",
                        "headers": {
                            "X-Dev-Access-Token": demo.private["dispatcher"]["development_token"]
                        },
                        "body": {
                            "expected_version": row["version"],
                            "delivery_instructions": f"Synthetic competing note {i}",
                        },
                    }
                )
            )
            child.stdin.close()
        statuses = []
        for child in children:
            child.wait(timeout=15)
            if child.returncode:
                raise RuntimeError("Isolated HTTP client process failed")
            statuses.append(int(child.stdout.read().strip()))
        assert sorted(statuses) == [200, 409]
        demo.close()
        reopened = Database(demo.url)
        try:
            with reopened.sessions() as session:
                stored = session.get(Order, UUID(row["id"]))
                assert stored.version == 2
                assert session.scalar(select(func.count()).select_from(DeliveryEvent)) == 2
        finally:
            reopened.dispose()
        result = {
            "passed": True,
            "client_processes": 2,
            "http_statuses": sorted(statuses),
            "persisted_order_version": 2,
            "persisted_events": 2,
            "limitations": "One API worker; two independent OS HTTP clients; SQLite.",
        }
        target = BACKEND_ROOT.parent / "docs/overnight_audit/process_race.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream and not stream.closed:
                    stream.close()
        demo.close()


if __name__ == "__main__":
    main()
