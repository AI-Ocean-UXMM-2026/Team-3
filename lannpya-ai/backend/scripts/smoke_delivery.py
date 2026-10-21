"""Isolated real HTTP merchant -> buyer -> dispatcher -> rider delivery demo."""

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

from app.db.buyer_models import BuyerRequest, ConfirmationLink
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User
from app.db.rider_models import DeliveryAssignment, RiderActionReceipt, RiderProfile
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole


def main():
    path = BACKEND_ROOT / "data" / "verification" / f"phase6_{uuid4().hex}.sqlite3"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    database = Database(url)
    upgrade_database(database)
    dispatcher_id, merchant_id = uuid4(), uuid4()
    with database.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=dispatcher_id,
                    name="Demo dispatcher",
                    email="dispatch@example.test",
                    role=UserRole.DISPATCHER,
                ),
                User(
                    id=merchant_id,
                    name="Demo merchant",
                    email="merchant@example.test",
                    role=UserRole.MERCHANT,
                ),
            ]
        )
    servers, clients, samples, capabilities = [], [], [], []

    def start(actor_id):
        secret = secrets.token_urlsafe(32)
        capabilities.append(secret)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = {
            **os.environ,
            "LANNPYA_ENVIRONMENT": "test",
            "LANNPYA_ORDER_MANAGEMENT_ENABLED": "true",
            "LANNPYA_DATABASE_URL": url,
            "LANNPYA_DEV_ACCESS_TOKEN": secret,
            "LANNPYA_DEV_ACTOR_ID": str(actor_id),
            "LANNPYA_PARSER_MODE": "hybrid",
            "LANNPYA_AI_PROVIDER": "mock",
        }
        process = subprocess.Popen(
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
        servers.append(process)
        client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}", headers={"X-Dev-Access-Token": secret}, timeout=5
        )
        clients.append(client)
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError("Delivery demo server exited")
            try:
                assert client.get("/health").status_code == 200
                return client
            except httpx.ConnectError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Delivery demo server did not start") from None
                time.sleep(0.1)

    def expect(name, response, status=200):
        assert response.status_code == status, (
            f"Unexpected status for {name}: {response.status_code}"
        )
        payload = json.dumps(response.json(), ensure_ascii=False)
        for capability in capabilities:
            payload = payload.replace(capability, "[REDACTED_CAPABILITY]")
        samples.append({"name": name, "http_status": status, "response": json.loads(payload)})
        return response.json()

    try:
        dispatcher, merchant = start(dispatcher_id), start(merchant_id)
        rider = expect(
            "rider_created",
            dispatcher.post(
                "/api/riders", json={"name": "Demo rider", "operational_status": "AVAILABLE"}
            ),
            201,
        )
        rider_client = start(rider["id"])
        created = expect(
            "merchant_order_created",
            merchant.post(
                "/api/orders",
                json={
                    "merchant_id": str(merchant_id),
                    "raw_text": "၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀",
                },
            ),
            201,
        )
        order_id = created["id"]
        expect(
            "merchant_requested_review",
            merchant.patch(
                f"/api/orders/{order_id}/status",
                json={"status": "NEEDS_REVIEW", "expected_version": created["version"]},
            ),
        )
        link_response = merchant.post(f"/api/orders/{order_id}/confirmation-link")
        assert link_response.status_code == 201
        link = link_response.json()
        token = link["confirmation_url"].rsplit("/", 1)[1]
        capabilities.append(token)
        expect("merchant_generated_link", link_response, 201)
        buyer = httpx.Client(base_url=str(dispatcher.base_url), timeout=5)
        clients.append(buyer)
        buyer_path = "/api/confirm/" + token
        expect("public_card", buyer.get(buyer_path))
        verification = buyer.post(buyer_path + "/verify", json={"last_four": "4567"})
        assert verification.status_code == 200
        capabilities.append(verification.json()["access_token"])
        expect("buyer_verified", verification)
        auth = {"Authorization": "Bearer " + verification.json()["access_token"]}
        expect(
            "initial_pin_pending",
            buyer.patch(
                buyer_path + "/location",
                headers=auth,
                json={
                    "request_id": str(uuid4()),
                    "latitude": "16.8",
                    "longitude": "96.1",
                    "initial_pin_acknowledged": True,
                },
            ),
        )
        requests = dispatcher.get(f"/api/orders/{order_id}/buyer-requests").json()["items"]
        current = dispatcher.get(f"/api/orders/{order_id}").json()
        expect(
            "dispatcher_approved_pin",
            dispatcher.patch(
                f"/api/orders/{order_id}/buyer-requests/{requests[0]['id']}",
                json={
                    "expected_version": current["version"],
                    "decision": "APPROVE",
                    "reason": "Demo dispatcher reviewed buyer submitted pin",
                },
            ),
        )
        expect(
            "buyer_available",
            buyer.patch(
                buyer_path + "/response",
                headers=auth,
                json={
                    "request_id": str(uuid4()),
                    "action": "AVAILABLE",
                    "instructions": "ဘေးတံခါးမှဝင်ပါ",
                },
            ),
        )
        current = dispatcher.get(f"/api/orders/{order_id}").json()
        ready = expect(
            "dispatcher_ready",
            dispatcher.patch(
                f"/api/orders/{order_id}/status",
                json={
                    "status": "READY_FOR_DISPATCH",
                    "expected_version": current["version"],
                    "acknowledge_unverified_location": True,
                },
            ),
        )
        assigned = expect(
            "rider_assigned",
            dispatcher.post(
                f"/api/orders/{order_id}/assign",
                json={
                    "expected_version": ready["version"],
                    "rider_id": rider["id"],
                    "stop_sequence": 1,
                },
            ),
            201,
        )
        queue_path = f"/api/riders/{rider['id']}/queue"
        queue = expect("rider_queue", rider_client.get(queue_path))
        assert (
            queue["items"][0]["navigation_ready"]
            and queue["items"][0]["delivery_instructions"] == "ဘေးတံခါးမှဝင်ပါ"
        )
        expect("queue_unchanged", rider_client.get(queue_path, params={"cursor": queue["cursor"]}))
        expect("rider_cannot_read_dispatcher_orders", rider_client.get("/api/orders"), 403)
        delivery_path = f"/api/riders/{rider['id']}/deliveries/{order_id}/status"
        started = expect(
            "delivery_started",
            rider_client.patch(
                delivery_path,
                json={
                    "expected_version": assigned["order_version"],
                    "request_id": str(uuid4()),
                    "action": "START",
                },
            ),
        )
        expect(
            "cod_confirmation_required",
            rider_client.patch(
                delivery_path,
                json={
                    "expected_version": started["order_version"],
                    "request_id": str(uuid4()),
                    "action": "DELIVERED",
                },
            ),
            409,
        )
        completion = {
            "expected_version": started["order_version"],
            "request_id": str(uuid4()),
            "action": "DELIVERED",
            "cod_collected": True,
        }
        expect("delivery_completed", rider_client.patch(delivery_path, json=completion))
        expect("completion_retry", rider_client.patch(delivery_path, json=completion))
        removed = expect(
            "queue_removed_delivery",
            rider_client.get(queue_path, params={"cursor": queue["cursor"]}),
        )
        assert not removed["unchanged"] and removed["total"] == 0
        expect("delivered_card_view_only", buyer.get(buyer_path))
        events = expect("dispatcher_history", dispatcher.get(f"/api/orders/{order_id}/events"))
        complete = [item for item in events["items"] if item["event_type"] == "DELIVERY_COMPLETED"]
        assert len(complete) == 1 and complete[0]["metadata"]["actor_id"] == rider["id"]
        expect("anonymous_queue_rejected", buyer.get(queue_path), 401)
        output = BACKEND_ROOT.parent / "docs" / "PHASE6_SAMPLE_RESPONSES.json"
        output.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        assert all(
            capability not in output.read_text(encoding="utf-8") for capability in capabilities
        )
    finally:
        for client in clients:
            client.close()
        for process in servers:
            process.terminate()
        for process in servers:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        database.dispose()
    reopened = Database(url)
    try:
        with reopened.sessions() as session:
            row = session.scalar(select(Order))
            assignment = session.scalar(select(DeliveryAssignment))
            assert (
                row.status.value == "DELIVERED"
                and assignment.status == "COMPLETED"
                and assignment.cod_collected is True
            )
            assert str(row.latitude) == "16.8000000" and row.confidence_level.value == "AMBER"
            counts = {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (
                    Order,
                    RiderProfile,
                    DeliveryAssignment,
                    RiderActionReceipt,
                    BuyerRequest,
                    DeliveryEvent,
                )
            }
            assert counts["delivery_events"] == 11 and counts["rider_action_receipts"] == 2
            assert session.scalar(select(ConfirmationLink)).delivered_view_until is not None
        print(
            json.dumps(
                {
                    "migration": "0003_rider_copilot",
                    "persisted": counts,
                    "status": "DELIVERED",
                    "cod_collected": True,
                    "confidence": "AMBER",
                    "samples": output.name,
                    "capabilities_redacted": True,
                    "servers_stopped": True,
                },
                indent=2,
            )
        )
    finally:
        reopened.dispose()


if __name__ == "__main__":
    main()
