"""Real HTTP buyer flow on a new isolated SQLite DB; never print/store live capabilities."""

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

from app.db.buyer_models import BuyerRequest, BuyerSession, ConfirmationLink
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole


def main():
    path = BACKEND_ROOT / "data" / "verification" / f"phase5_{uuid4().hex}.sqlite3"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    db = Database(url)
    upgrade_database(db)
    actor_id, merchant_id = uuid4(), uuid4()
    with db.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=actor_id,
                    name="Synthetic dispatcher",
                    email="dispatch@example.test",
                    role=UserRole.DISPATCHER,
                ),
                User(
                    id=merchant_id,
                    name="Synthetic merchant",
                    email="merchant@example.test",
                    role=UserRole.MERCHANT,
                ),
            ]
        )
    dev_secret = secrets.token_urlsafe(32)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {
        **os.environ,
        "LANNPYA_ENVIRONMENT": "test",
        "LANNPYA_ORDER_MANAGEMENT_ENABLED": "true",
        "LANNPYA_DATABASE_URL": url,
        "LANNPYA_DEV_ACCESS_TOKEN": dev_secret,
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
        env=environment,
    )
    samples = []
    capabilities = [dev_secret]

    def record(name, response):
        result = json.dumps(response.json(), ensure_ascii=False)
        for capability in capabilities:
            result = result.replace(capability, "[REDACTED_CAPABILITY]")
        samples.append(
            {"name": name, "http_status": response.status_code, "response": json.loads(result)}
        )

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Buyer verification server exited")
                try:
                    assert client.get("/health").status_code == 200
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Buyer verification server did not start") from None
                    time.sleep(0.1)
            admin = {"X-Dev-Access-Token": dev_secret}
            created = client.post(
                "/api/orders",
                headers=admin,
                json={
                    "merchant_id": str(merchant_id),
                    "raw_text": "၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀",
                },
            )
            assert created.status_code == 201
            order = created.json()
            status = client.patch(
                f"/api/orders/{order['id']}/status",
                headers=admin,
                json={"status": "NEEDS_REVIEW", "expected_version": order["version"]},
            )
            assert status.status_code == 200
            link = client.post(f"/api/orders/{order['id']}/confirmation-link", headers=admin)
            assert link.status_code == 201
            token = link.json()["confirmation_url"].rsplit("/", 1)[1]
            capabilities.append(token)
            record("generated_link", link)
            buyer_path = "/api/confirm/" + token
            card = client.get(buyer_path)
            assert card.status_code == 200 and "customer_phone" not in card.json()
            record("minimal_public_card", card)
            body = {
                "request_id": str(uuid4()),
                "latitude": "16.8000000",
                "longitude": "96.1000000",
                "initial_pin_acknowledged": True,
            }
            denied = client.patch(buyer_path + "/location", json=body)
            assert denied.status_code == 401
            record("unauthorized_pin", denied)
            wrong = client.post(buyer_path + "/verify", json={"last_four": "0000"})
            assert wrong.status_code == 403
            record("failed_verification", wrong)
            verify = client.post(buyer_path + "/verify", json={"last_four": "4567"})
            assert verify.status_code == 200
            credential = verify.json()["access_token"]
            capabilities.append(credential)
            record("verified_authorization", verify)
            auth = {"Authorization": "Bearer " + credential}
            details = client.get(buyer_path + "/details", headers=auth)
            assert details.status_code == 200
            record("verified_details", details)
            requested = client.patch(buyer_path + "/location", headers=auth, json=body)
            assert (
                requested.status_code == 200 and requested.json()["decision"] == "REVIEW_REQUIRED"
            )
            record("initial_pin_review", requested)
            duplicate = client.patch(buyer_path + "/location", headers=auth, json=body)
            assert duplicate.status_code == 200
            history = client.get(f"/api/orders/{order['id']}/buyer-requests", headers=admin)
            assert history.json()["total"] == 1
            row = history.json()["items"][0]
            current = client.get(f"/api/orders/{order['id']}", headers=admin).json()
            approved = client.patch(
                f"/api/orders/{order['id']}/buyer-requests/{row['id']}",
                headers=admin,
                json={
                    "expected_version": current["version"],
                    "decision": "APPROVE",
                    "reason": "Synthetic dispatcher reviewed initial buyer pin",
                },
            )
            assert approved.status_code == 200
            record("dispatcher_approval", approved)
            available = client.patch(
                buyer_path + "/response",
                headers=auth,
                json={
                    "request_id": str(uuid4()),
                    "action": "AVAILABLE",
                    "instructions": "Ring the gate bell",
                },
            )
            assert available.status_code == 200 and available.json()["order_status"] == "CONFIRMED"
            record("buyer_availability", available)
            current = client.get(f"/api/orders/{order['id']}", headers=admin)
            assert current.json()["confidence_level"] == "AMBER"
            assert current.json()["field_sources"]["latitude"]["method"] == "buyer_confirmation"
            record("protected_saved_order", current)
            assert (
                client.post(
                    f"/api/orders/{order['id']}/confirmation-link/revoke", headers=admin
                ).status_code
                == 200
            )
            rejected = client.patch(buyer_path + "/location", headers=auth, json=body)
            assert rejected.status_code == 404
            record("revoked_link_rejected", rejected)
        output = BACKEND_ROOT.parent / "docs" / "PHASE5_SAMPLE_RESPONSES.json"
        output.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        assert all(
            capability not in output.read_text(encoding="utf-8") for capability in capabilities
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        db.dispose()
    reopened = Database(url)
    try:
        with reopened.sessions() as session:
            order = session.scalar(select(Order))
            assert str(order.latitude) == "16.8000000"
            assert order.delivery_instructions == "Ring the gate bell"
            counts = {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (Order, ConfirmationLink, BuyerSession, BuyerRequest, DeliveryEvent)
            }
            assert counts["buyer_requests"] == 2
            assert counts["delivery_events"] == 9
        print(
            json.dumps(
                {
                    "migration": "0003_rider_copilot",
                    "persisted": counts,
                    "unauthorized": 401,
                    "revoked": 404,
                    "confidence": "AMBER",
                    "samples": output.name,
                    "all_capabilities_redacted": True,
                },
                indent=2,
            )
        )
    finally:
        reopened.dispose()


if __name__ == "__main__":
    main()
