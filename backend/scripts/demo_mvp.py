"""Private loopback demo and HTTP integration verification; never reuse the normal DB."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx2 as httpx
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.buyer_models import BuyerOtpChallenge, BuyerRequest, ConfirmationLink
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User
from app.db.rider_models import DeliveryAssignment, RiderActionReceipt
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole
from app.schemas.management import EditableOrderFields

PHONE = "09960000000"  # Constructed test digits, not imported subscriber/customer data.
UNICODE_PHONE = PHONE.translate(str.maketrans("0123456789", "၀၁၂၃၄၅၆၇၈၉"))
DEFAULT_ORIGIN = "http://localhost:5173"


def fixtures():
    """Actual extraction inputs; no GREEN label, AI output or trusted coordinates seeded."""
    return {
        "green_candidate_unverified": f"{UNICODE_PHONE}၊ လှိုင်မြို့နယ်၊ စမ်းသပ်လမ်း၊ သရုပ်ပြဆိုင်အနီး၊ COD ၀",
        "amber_needs_buyer": f"{UNICODE_PHONE}၊ လှိုင်မြို့နယ်၊ COD ၁၂၀၀၀",
        "red_missing_contact": "သရုပ်ပြမှာစာ၊ ဖုန်းမပါ၊ မြို့နယ်မသိ",
        "cod_delivery": (
            f"{UNICODE_PHONE}၊ လှိုင်မြို့နယ်၊ စမ်းသပ်လမ်း၊ COD ၂၅၀၀၀၊ address: behind demo red gate"
        ),
        "rescheduling_and_failure": f"{UNICODE_PHONE}၊ လှိုင်မြို့နယ်၊ စမ်းသပ်လမ်း၊ COD ၀",
    }


def approved_origin(value):
    settings = Settings(_env_file=None, cors_origins=[value])
    from urllib.parse import urlsplit

    if urlsplit(value).hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Demo frontend origin must be localhost or 127.0.0.1")
    return settings.cors_origins[0]


def private_json(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")
    os.chmod(path, 0o600)  # Windows ACL remains OS-managed; storage is Git-ignored.


class LocalDemo:
    def __init__(self, origin=DEFAULT_ORIGIN):
        if Settings().environment not in {"local", "test"}:
            raise RuntimeError("Demo is disabled in production configuration")
        self.origin = approved_origin(origin)
        self.directory = BACKEND_ROOT / "data" / "demo" / uuid4().hex
        self.directory.mkdir(parents=True, exist_ok=False)
        self.url = f"sqlite+pysqlite:///{(self.directory / 'demo.sqlite3').as_posix()}"
        self.database = Database(self.url)
        upgrade_database(self.database)
        self.servers, self.clients, self.cases, self.private, self.orders = [], [], [], {}, {}
        self.redactions = [PHONE, UNICODE_PHONE]
        self.live_buyer = None
        self.closed = False

    def close(self):
        if self.closed:
            return
        self.closed = True
        for client in self.clients:
            client.close()
        for server in self.servers:
            server.terminate()
        for server in self.servers:
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        self.database.dispose()

    def start(self, role, actor_id):
        token = secrets.token_urlsafe(32)
        self.redactions.append(token)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        environment = {
            **os.environ,
            "LANNPYA_ENVIRONMENT": "test",
            "LANNPYA_ORDER_MANAGEMENT_ENABLED": "true",
            "LANNPYA_DATABASE_URL": self.url,
            "LANNPYA_DEV_ACTOR_ID": str(actor_id),
            "LANNPYA_DEV_ACCESS_TOKEN": token,
            "LANNPYA_CORS_ORIGINS": json.dumps([self.origin]),
            "LANNPYA_PARSER_MODE": "hybrid",
            "LANNPYA_AI_PROVIDER": "mock",
            "LANNPYA_BUYER_RESCHEDULING_ENABLED": "false",
            "LANNPYA_BUYER_LEAVE_WITH_SECURITY_ENABLED": "false",
            "LANNPYA_BUYER_FRONTEND_BASE_URL": self.origin,
            "LANNPYA_RIDER_REQUIRE_COD_CONFIRMATION": "true",
            "LANNPYA_RIDER_MAX_ACTIVE_ASSIGNMENTS": "100",
            "LANNPYA_BUYER_REQUEST_LIMIT_PER_MINUTE": "60",
            "LANNPYA_BUYER_VERIFY_LIMIT_PER_MINUTE": "10",
            "LANNPYA_BUYER_LINK_HOURS": "72",
            "LANNPYA_BUYER_SESSION_MINUTES": "15",
            "LANNPYA_BUYER_MIN_NOTICE_MINUTES": "120",
            "LANNPYA_BUYER_MAX_SCHEDULE_DAYS": "7",
            "LANNPYA_BUYER_CUTOFF_HOUR": "15",
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
                "--no-proxy-headers",
            ],
            cwd=BACKEND_ROOT,
            env=environment,
        )
        self.servers.append(process)
        client = httpx.Client(
            base_url=base, headers={"X-Dev-Access-Token": token, "Origin": self.origin}, timeout=10
        )
        self.clients.append(client)
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError("Demo server exited during startup")
            try:
                assert client.get("/health").status_code == 200
                break
            except httpx.ConnectError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Demo server did not start") from None
                time.sleep(0.1)
        self.private[role] = {
            "base_url": base,
            "actor_id": str(actor_id),
            "development_token": token,
        }
        return client

    def expect(self, name, response, status=200):
        if response.status_code != status:
            raise RuntimeError(
                f"Demo check {name} expected HTTP {status}, got {response.status_code}"
            )
        if response.headers.get("access-control-allow-origin") != self.origin:
            raise RuntimeError(f"Demo check {name} missing approved CORS response")
        payload = response.json()
        self.cases.append({"name": name, "http_status": status, "response": payload})
        return payload

    def order(self, client, identifier):
        return self.expect("order_refresh", client.get(f"/api/orders/{identifier}"))

    def status(self, client, identifier, target):
        current = self.order(client, identifier)
        return self.expect(
            "status_" + target,
            client.patch(
                f"/api/orders/{identifier}/status",
                json={
                    "status": target,
                    "expected_version": current["version"],
                    "acknowledge_unverified_location": True,
                },
            ),
        )

    def buyer(self, client, identifier):
        link = self.expect(
            "confirmation_link", client.post(f"/api/orders/{identifier}/confirmation-link"), 201
        )
        token = link["confirmation_url"].rsplit("/", 1)[1]
        self.redactions.append(token)
        public = httpx.Client(
            base_url=str(client.base_url), headers={"Origin": self.origin}, timeout=10
        )
        self.clients.append(public)
        path = "/api/confirm/" + token
        card = self.expect("minimal_card", public.get(path))
        assert set(card) == {
            "order_reference",
            "shop_display_name",
            "delivery_status",
            "state",
            "expires_at",
        }
        challenge = self.expect("buyer_otp_request", public.post(path + "/otp", json={}))
        with self.database.sessions() as session:
            code = session.get(BuyerOtpChallenge, UUID(challenge["challenge_id"])).demo_code
        if not code:
            raise RuntimeError("Isolated demo OTP fixture did not create a test code")
        result = self.expect("buyer_verification", public.post(path + "/verify", json={"code": code}))
        self.redactions.append(result["access_token"])
        public.headers["Authorization"] = "Bearer " + result["access_token"]
        return public, path

    def setup_and_verify(self):
        assert EditableOrderFields.valid_mobile(PHONE)
        dispatcher_id, merchant_id = uuid4(), uuid4()
        with self.database.sessions.begin() as session:
            session.add_all(
                [
                    User(
                        id=dispatcher_id,
                        name="သရုပ်ပြ စီစဉ်သူ (အတု)",
                        email="dispatcher@example.invalid",
                        role=UserRole.DISPATCHER,
                    ),
                    User(
                        id=merchant_id,
                        name="သရုပ်ပြ ရွှေလမ်းဆိုင် (အတု)",
                        email="merchant@example.invalid",
                        role=UserRole.MERCHANT,
                    ),
                ]
            )
        dispatcher, merchant = (
            self.start("dispatcher", dispatcher_id),
            self.start("merchant", merchant_id),
        )
        self.expect("health", dispatcher.get("/health"))
        for client in (dispatcher, merchant):
            preflight = client.options(
                "/api/orders",
                headers={
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": (
                        "content-type,x-dev-access-token,authorization"
                    ),
                },
            )
            assert (
                preflight.status_code == 200
                and preflight.headers["access-control-allow-origin"] == self.origin
            )
            assert "access-control-allow-credentials" not in preflight.headers
            rejected = client.options(
                "/api/orders",
                headers={
                    "Origin": "https://unapproved.example.invalid",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert (
                rejected.status_code == 400
                and "access-control-allow-origin" not in rejected.headers
            )
        self.cases.append(
            {"name": "cors_preflights", "allowed_status": 200, "disallowed_status": 400}
        )
        for name, raw in fixtures().items():
            parsed = self.expect(
                "parse_" + name, merchant.post("/api/orders/parse", json={"raw_text": raw})
            )
            assert parsed["confidence"] == ("RED" if name.startswith("red_") else "AMBER")
            assert parsed["ai"]["status"] in {"mock", "not_requested", "privacy_blocked"}
            assert not parsed["is_mock"]
            row = self.expect(
                "create_" + name,
                merchant.post(
                    "/api/orders", json={"merchant_id": str(merchant_id), "raw_text": raw}
                ),
                201,
            )
            self.orders[name] = row["id"]
        candidate = self.order(dispatcher, self.orders["green_candidate_unverified"])
        assert candidate["confidence_level"] == "AMBER" and candidate["latitude"] is None
        current = self.order(dispatcher, self.orders["amber_needs_buyer"])
        self.expect(
            "manual_correction",
            dispatcher.patch(
                f"/api/orders/{current['id']}",
                json={
                    "expected_version": current["version"],
                    "floor": "၂",
                    "delivery_instructions": "သရုပ်ပြ ညွှန်ကြားချက် (အတု)",
                },
            ),
        )
        rider = self.expect(
            "rider_created",
            dispatcher.post(
                "/api/riders", json={"name": "သရုပ်ပြ ပို့ဆောင်သူ (အတု)", "operational_status": "AVAILABLE"}
            ),
            201,
        )
        rider_client = self.start("rider", rider["id"])
        delivered = self.orders["cod_delivery"]
        self.status(merchant, delivered, "NEEDS_REVIEW")
        buyer, path = self.buyer(merchant, delivered)
        self.expect("buyer_details", buyer.get(path + "/details"))
        # Deliberately synthetic Null Island pin: never advertised as a Myanmar location.
        self.expect(
            "initial_pin_review",
            buyer.patch(
                path + "/location",
                json={
                    "request_id": str(uuid4()),
                    "latitude": "0",
                    "longitude": "0",
                    "initial_pin_acknowledged": True,
                },
            ),
        )
        requests = self.expect(
            "buyer_history", dispatcher.get(f"/api/orders/{delivered}/buyer-requests")
        )["items"]
        current = self.order(dispatcher, delivered)
        self.expect(
            "dispatcher_approval",
            dispatcher.patch(
                f"/api/orders/{delivered}/buyer-requests/{requests[0]['id']}",
                json={
                    "expected_version": current["version"],
                    "decision": "APPROVE",
                    "reason": "Demo-only fictional pin reviewed; not geospatial verification",
                },
            ),
        )
        self.expect(
            "buyer_available",
            buyer.patch(
                path + "/response",
                json={
                    "request_id": str(uuid4()),
                    "action": "AVAILABLE",
                    "instructions": "သရုပ်ပြ တံခါးခေါက်ပါ (အတု)",
                },
            ),
        )
        ready = self.status(dispatcher, delivered, "READY_FOR_DISPATCH")
        assignment = self.expect(
            "rider_assignment",
            dispatcher.post(
                f"/api/orders/{delivered}/assign",
                json={
                    "expected_version": ready["version"],
                    "rider_id": rider["id"],
                    "stop_sequence": 1,
                },
            ),
            201,
        )
        queue_path = f"/api/riders/{rider['id']}/queue"
        queue = self.expect("rider_queue", rider_client.get(queue_path))
        assert (
            queue["items"][0]["coordinate_status"] == "BUYER_CONFIRMED"
            and queue["items"][0]["confidence_level"] == "AMBER"
        )
        unchanged = self.expect(
            "poll_unchanged", rider_client.get(queue_path, params={"cursor": queue["cursor"]})
        )
        assert unchanged["unchanged"] and unchanged["items"] == []
        action_path = f"/api/riders/{rider['id']}/deliveries/{delivered}/status"
        started = self.expect(
            "delivery_started",
            rider_client.patch(
                action_path,
                json={
                    "request_id": str(uuid4()),
                    "expected_version": assignment["order_version"],
                    "action": "START",
                },
            ),
        )
        self.expect(
            "cod_rejected_without_confirmation",
            rider_client.patch(
                action_path,
                json={
                    "request_id": str(uuid4()),
                    "expected_version": started["order_version"],
                    "action": "DELIVERED",
                },
            ),
            409,
        )
        body = {
            "request_id": str(uuid4()),
            "expected_version": started["order_version"],
            "action": "DELIVERED",
            "cod_collected": True,
        }
        self.expect("delivery_completed", rider_client.patch(action_path, json=body))
        self.expect("completion_retry", rider_client.patch(action_path, json=body))
        removed = self.expect(
            "poll_removed", rider_client.get(queue_path, params={"cursor": queue["cursor"]})
        )
        assert not removed["unchanged"] and removed["total"] == 0
        self.expect("rider_dispatcher_api_forbidden", rider_client.get("/api/orders"), 403)
        self.expect("buyer_cannot_read_rider_queue", buyer.get(queue_path), 401)
        self.expect("delivered_card", buyer.get(path))
        self.expect("delivery_history", dispatcher.get(f"/api/orders/{delivered}/events"))
        # A separate order demonstrates unsupported rescheduling, explicit rejection, then failure.
        identifier = self.orders["rescheduling_and_failure"]
        self.status(merchant, identifier, "NEEDS_REVIEW")
        other_buyer, other_path = self.buyer(merchant, identifier)
        start = (datetime.now(UTC) + timedelta(days=2)).replace(
            hour=3, minute=0, second=0, microsecond=0
        )
        requested = self.expect(
            "reschedule_review",
            other_buyer.patch(
                other_path + "/response",
                json={
                    "request_id": str(uuid4()),
                    "action": "RESCHEDULE",
                    "time_window": {
                        "start": start.isoformat(),
                        "end": (start + timedelta(hours=2)).isoformat(),
                    },
                },
            ),
        )
        assert requested["decision"] == "REVIEW_REQUIRED"
        current = self.order(dispatcher, identifier)
        assert current["delivery_time_window"] is None
        request = self.expect(
            "reschedule_history", dispatcher.get(f"/api/orders/{identifier}/buyer-requests")
        )["items"][0]
        self.expect(
            "dispatcher_rejection",
            dispatcher.patch(
                f"/api/orders/{identifier}/buyer-requests/{request['id']}",
                json={
                    "expected_version": current["version"],
                    "decision": "REJECT",
                    "reason": "Demo courier does not support the proposed window",
                },
            ),
        )
        self.status(dispatcher, identifier, "CONFIRMED")
        ready = self.status(dispatcher, identifier, "READY_FOR_DISPATCH")
        assignment = self.expect(
            "second_assignment",
            dispatcher.post(
                f"/api/orders/{identifier}/assign",
                json={"expected_version": ready["version"], "rider_id": rider["id"]},
            ),
            201,
        )
        action_path = f"/api/riders/{rider['id']}/deliveries/{identifier}/status"
        started = self.expect(
            "second_started",
            rider_client.patch(
                action_path,
                json={
                    "request_id": str(uuid4()),
                    "expected_version": assignment["order_version"],
                    "action": "START",
                },
            ),
        )
        self.expect(
            "delivery_failed",
            rider_client.patch(
                action_path,
                json={
                    "request_id": str(uuid4()),
                    "expected_version": started["order_version"],
                    "action": "FAILED",
                    "failure_reason": "CUSTOMER_UNAVAILABLE",
                    "failure_note": "Fictional demo failure; no contact was attempted",
                },
            ),
        )
        # Leave one genuine assigned stop for optional live frontend polling.
        live = self.orders["amber_needs_buyer"]
        self.status(dispatcher, live, "NEEDS_REVIEW")
        self.status(dispatcher, live, "CONFIRMED")
        ready = self.status(dispatcher, live, "READY_FOR_DISPATCH")
        self.expect(
            "live_demo_assignment",
            dispatcher.post(
                f"/api/orders/{live}/assign",
                json={
                    "expected_version": ready["version"],
                    "rider_id": rider["id"],
                    "stop_sequence": 2,
                },
            ),
            201,
        )
        self.expect("live_demo_queue", rider_client.get(queue_path))
        candidate_id = self.orders["green_candidate_unverified"]
        self.status(merchant, candidate_id, "NEEDS_REVIEW")
        link = self.expect(
            "live_buyer_link", merchant.post(f"/api/orders/{candidate_id}/confirmation-link"), 201
        )
        self.redactions.append(link["confirmation_url"].rsplit("/", 1)[1])
        self.live_buyer = {
            "backend_base_url": str(merchant.base_url).rstrip("/"),
            "confirmation_url": link["confirmation_url"],
            "frontend_url": link["absolute_url"],
        }
        with self.database.sessions() as session:
            assert session.scalar(select(func.count()).select_from(Order)) == 5
            assert session.get(Order, UUID(delivered)).status.value == "DELIVERED"
        return self.verify_persistence(delivered)

    def verify_persistence(self, delivered):
        reopened = Database(self.url)
        try:
            with reopened.sessions() as session:
                order = session.get(Order, UUID(str(delivered)))
                assert order.status.value == "DELIVERED" and order.confidence_level.value == "AMBER"
                assert order.latitude == 0 and order.longitude == 0
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(DeliveryEvent)
                        .where(DeliveryEvent.event_type == "DELIVERY_COMPLETED")
                    )
                    == 1
                )
                counts = {
                    model.__tablename__: session.scalar(select(func.count()).select_from(model))
                    for model in (
                        Order,
                        BuyerRequest,
                        DeliveryAssignment,
                        RiderActionReceipt,
                        DeliveryEvent,
                        ConfirmationLink,
                    )
                }
        finally:
            reopened.dispose()
        return {
            "demo_only": True,
            "migration": "0003_rider_copilot",
            "ai": "mock",
            "green_enabled": False,
            "counts": counts,
            "http_cases": len(self.cases),
            "cors_origin": self.origin,
            "delivered": True,
            "failed": True,
            "rescheduling_requires_review": True,
            "original_environment_preserved": True,
        }

    def write_outputs(self, summary):
        private_json(
            self.directory / "private_access.json",
            {
                "demo_only": True,
                "roles": self.private,
                "orders": self.orders,
                "buyer_link": self.live_buyer,
                "warning": (
                    "Local runtime credentials. Do not serve, commit, publish or bundle this file."
                ),
            },
        )
        payload = json.dumps(
            {"summary": summary, "samples": self.cases}, ensure_ascii=False, indent=2
        )
        for secret in self.redactions:
            payload = payload.replace(secret, "[REDACTED_DEMO_VALUE]")
        assert all(secret not in payload for secret in self.redactions)
        (self.directory / "verification.json").write_text(payload + "\n", encoding="utf-8")
        (BACKEND_ROOT.parent / "docs" / "PHASE7_SAMPLE_RESPONSES.json").write_text(
            payload + "\n", encoding="utf-8"
        )
        private_json(self.directory / "summary.json", summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Keep isolated loopback role instances running until Ctrl+C",
    )
    parser.add_argument("--frontend-origin", default=DEFAULT_ORIGIN)
    args = parser.parse_args()
    demo = LocalDemo(args.frontend_origin)
    try:
        summary = demo.setup_and_verify()
        if not args.serve:
            demo.close()
            summary = demo.verify_persistence(demo.orders["cod_delivery"])
            summary["persisted_after_servers_stopped"] = True
        demo.write_outputs(summary)
        print(
            json.dumps(
                {
                    **summary,
                    "private_run_directory": str(demo.directory),
                    "servers_kept_running": args.serve,
                },
                indent=2,
            )
        )
        if args.serve:
            print(
                "Local demo ready; private access details are in the ignored run directory. "
                "Ctrl+C stops servers."
            )
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Local demo stopped.")
    finally:
        demo.close()


if __name__ == "__main__":
    main()
