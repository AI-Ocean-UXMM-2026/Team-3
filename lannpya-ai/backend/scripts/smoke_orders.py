"""Migrate and exercise isolated synthetic orders over real HTTP; never use the user's DB."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx2 as httpx
from sqlalchemy import func, select

from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    unique = uuid4().hex
    path = BACKEND_ROOT / "data" / "verification" / f"phase4_{unique}.sqlite3"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    database = Database(url)
    upgrade_database(database)
    actor_id, merchant_id = uuid4(), uuid4()
    with database.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=actor_id,
                    name="Verification dispatcher",
                    email="dispatcher@example.test",
                    role=UserRole.DISPATCHER,
                ),
                User(
                    id=merchant_id,
                    name="Verification merchant",
                    email="merchant@example.test",
                    role=UserRole.MERCHANT,
                ),
            ]
        )
    token = secrets.token_urlsafe(32)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {
        **os.environ,
        "LANNPYA_ENVIRONMENT": "test",
        "LANNPYA_ORDER_MANAGEMENT_ENABLED": "true",
        "LANNPYA_DATABASE_URL": url,
        "LANNPYA_DEV_ACCESS_TOKEN": token,
        "LANNPYA_DEV_ACTOR_ID": str(actor_id),
        "LANNPYA_PARSER_MODE": "hybrid",
        "LANNPYA_AI_PROVIDER": "mock",
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=BACKEND_ROOT,
        env=env,
    )
    cases = []
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Verification server exited")
                try:
                    assert client.get("/health").status_code == 200
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Verification server did not become ready") from None
                    time.sleep(0.1)
            unauthorized = client.get("/api/orders")
            assert unauthorized.status_code == 401
            cases.append(
                {"name": "unauthorized", "http_status": 401, "response": unauthorized.json()}
            )
            client.headers["X-Dev-Access-Token"] = token
            body = {
                "merchant_id": str(merchant_id),
                "raw_text": "၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀၊ address: behind red gate",
            }
            response = client.post("/api/orders", json=body)
            assert response.status_code == 201, response.text
            row = response.json()
            cases.append(
                {"name": "created_raw", "request": body, "http_status": 201, "response": row}
            )
            assert row["customer_phone"] == "09791234567" and row["cod_amount"] == "25000"
            assert row["ai_availability_status"] == "mock" and row["confidence_level"] == "AMBER"
            assert client.get(f"/api/orders/{row['id']}").json() == row
            assert (
                client.get("/api/orders", params={"q": "09791234567", "page_size": 1}).json()[
                    "total"
                ]
                == 1
            )
            correction = {
                "expected_version": row["version"],
                "landmark": "red gate",
                "floor": "4",
                "unit": "A3",
            }
            response = client.patch(f"/api/orders/{row['id']}", json=correction)
            assert response.status_code == 200, response.text
            row = response.json()
            cases.append(
                {"name": "corrected", "request": correction, "http_status": 200, "response": row}
            )
            stale = client.patch(f"/api/orders/{row['id']}", json=correction)
            assert stale.status_code == 409
            for target in (
                "NEEDS_REVIEW",
                "AWAITING_CONFIRMATION",
                "CONFIRMED",
                "READY_FOR_DISPATCH",
                "ASSIGNED",
                "OUT_FOR_DELIVERY",
                "DELIVERED",
            ):
                response = client.patch(
                    f"/api/orders/{row['id']}/status",
                    json={
                        "status": target,
                        "expected_version": row["version"],
                        "acknowledge_unverified_location": target == "READY_FOR_DISPATCH",
                        **({"cod_collected": True} if target == "DELIVERED" else {}),
                    },
                )
                assert response.status_code == 200, response.text
                row = response.json()
            assert row["status"] == "DELIVERED" and row["confidence_level"] == "AMBER"
            cases.append({"name": "delivered", "http_status": 200, "response": row})
            history = client.get(f"/api/orders/{row['id']}/events").json()
            assert history["total"] == 9
            assert "09791234567" not in json.dumps(history)
            cases.append({"name": "events", "http_status": 200, "response": history})
            structured = {
                "merchant_id": str(merchant_id),
                "structured": {
                    "customer_phone": "09951234567",
                    "township": "Bahan",
                    "cod_amount": "12000",
                },
            }
            response = client.post("/api/orders", json=structured)
            assert response.status_code == 201, response.text
            cases.append(
                {
                    "name": "created_structured",
                    "request": structured,
                    "http_status": 201,
                    "response": response.json(),
                }
            )
            assert (
                client.post(
                    "/api/orders", json={"merchant_id": str(merchant_id), "raw_text": ""}
                ).status_code
                == 422
            )
        output = BACKEND_ROOT.parent / "docs" / "PHASE4_SAMPLE_RESPONSES.json"
        output.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        database.dispose()
    # Re-open persisted storage after the HTTP server has stopped.
    reopened = Database(url)
    try:
        with reopened.sessions() as session:
            orders = session.scalar(select(func.count()).select_from(Order))
            events = session.scalar(select(func.count()).select_from(DeliveryEvent))
            assert orders == 2 and events == 10
        print(
            json.dumps(
                {
                    "migration": "0003_rider_copilot",
                    "isolated_database": path.name,
                    "persisted_orders": orders,
                    "persisted_events": events,
                    "unauthorized_status": 401,
                    "stale_version_status": 409,
                    "final_delivery_status": "DELIVERED",
                    "confidence": "AMBER",
                    "api_samples": output.name,
                    "secret_printed": False,
                },
                indent=2,
            )
        )
    finally:
        reopened.dispose()


if __name__ == "__main__":
    main()
