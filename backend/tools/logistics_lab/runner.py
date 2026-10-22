import hashlib
import platform
import secrets
import tempfile
import time
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.buyer_models import BuyerOtpChallenge, BuyerRequest
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User
from app.db.rider_models import DeliveryAssignment
from app.db.session import Database
from app.domain.lifecycle import UserRole
from app.main import create_app
from tools.logistics_lab.analytics import aggregate, latency_summary
from tools.logistics_lab.comparison import compare, sensitivity
from tools.logistics_lab.config import ComparisonConfig, SimulationConfig
from tools.logistics_lab.dataset import generate_plan


class SimulationError(RuntimeError):
    pass


class Experiment:
    def __init__(self, config, database, stack):
        self.config, self.database, self.stack = config, database, stack
        self.samples, self.codes, self.trace = defaultdict(list), Counter(), []
        self.calls, self.omitted, self.queue_checks = 0, 0, 0
        self.clients = {}
        self.ids = {}
        self.initial = []
        self.workflow_count = 0
        self.confirmed_window_observations = 0

    def app(self, actor):
        settings = Settings(
            _env_file=None,
            environment="test",
            order_management_enabled=True,
            ai_provider="mock",
            parser_mode="hybrid",
            ai_timeout_seconds=3.0,
            ai_max_input_chars=2000,
            buyer_rescheduling_enabled=False,
            buyer_leave_with_security_enabled=False,
            buyer_cutoff_hour=15,
            buyer_min_notice_minutes=120,
            buyer_max_schedule_days=7,
            buyer_request_limit_per_minute=60,
            buyer_verify_limit_per_minute=10,
            buyer_link_hours=72,
            buyer_session_minutes=15,
            rider_require_cod_confirmation=True,
            rider_max_active_assignments=100,
            dev_actor_id=actor,
            dev_access_token=secrets.token_urlsafe(32),
        )
        return create_app(settings, database=self.database)

    def client(self, actor):
        if actor not in self.clients:
            app = self.app(actor)
            self.clients[actor] = self.stack.enter_context(
                TestClient(
                    app,
                    client=("127.0.0.1", 54001),
                    headers={
                        "X-Dev-Access-Token": app.state.settings.dev_access_token.get_secret_value()
                    },
                )
            )
        return self.clients[actor]

    def call(
        self,
        client,
        method,
        path,
        stage,
        reference=None,
        body=None,
        headers=None,
        expected=(200,),
        capture=True,
    ):
        started = time.perf_counter()
        response = client.request(method, path, json=body, headers=headers)
        elapsed = (time.perf_counter() - started) * 1000
        self.samples[stage].append(elapsed)
        self.calls += 1
        self.codes[str(response.status_code)] += 1
        if response.status_code not in expected:
            # Never include response body, headers, raw text, token URL or private values.
            raise SimulationError(f"{stage} returned unexpected HTTP {response.status_code}")
        data = response.json()
        if capture:
            # Route names, not secret paths, are shareable. Only safe result fields are retained.
            summary = {
                key: data[key]
                for key in (
                    "status",
                    "confidence",
                    "confidence_level",
                    "decision",
                    "resolution",
                    "version",
                    "order_version",
                    "order_status",
                    "unchanged",
                    "total",
                    "reason_codes",
                )
                if key in data
            }
            self.trace.append(
                {
                    "reference": reference,
                    "method": method,
                    "operation": stage,
                    "http_status": response.status_code,
                    "response": summary,
                }
            )
        else:
            self.omitted += 1
        return data

    def refresh(self, order_id):
        return self.call(self.dispatcher, "GET", f"/api/orders/{order_id}", "order_detail")

    def transition(self, order_id, target):
        row = self.refresh(order_id)
        return self.call(
            self.dispatcher,
            "PATCH",
            f"/api/orders/{order_id}/status",
            "status_update",
            body={
                "expected_version": row["version"],
                "status": target,
                "acknowledge_unverified_location": True,
            },
        )

    def review(self, order_id):
        history = self.call(
            self.dispatcher,
            "GET",
            f"/api/orders/{order_id}/buyer-requests",
            "buyer_request_history",
        )
        for request in history["items"]:
            if request["decision"] == "REVIEW_REQUIRED" and request["resolution"] is None:
                row = self.refresh(order_id)
                self.call(
                    self.dispatcher,
                    "PATCH",
                    f"/api/orders/{order_id}/buyer-requests/{request['id']}",
                    "dispatcher_review",
                    body={
                        "expected_version": row["version"],
                        "decision": "APPROVE",
                        "reason": "Synthetic lab operator review, not geospatial proof",
                    },
                )

    def buyer_flow(self, planned, order_id, index):
        link = self.call(
            self.dispatcher,
            "POST",
            f"/api/orders/{order_id}/confirmation-link",
            "link_create",
            planned.reference,
            expected=(201,),
        )
        path = "/api" + link["confirmation_url"]
        # Reserved benchmarking peer addresses exist only in TestClient, not on the network.
        public = TestClient(
            self.dispatcher.app, client=(f"198.18.{index // 250}.{index % 250 + 1}", 54002)
        )
        # No persistent portal thread per buyer; role clients remain bounded by role count.
        self.stack.callback(public.close)
        if index == 0:
            replacement = self.call(
                self.dispatcher,
                "POST",
                f"/api/orders/{order_id}/confirmation-link",
                "link_replace",
                expected=(201,),
            )
            self.call(public, "GET", path, "revoked_link_rejection", expected=(404,))
            path = "/api" + replacement["confirmation_url"]
        self.call(public, "GET", path, "buyer_card", planned.reference)
        challenge = self.call(
            public,
            "POST",
            path + "/otp",
            "buyer_otp_request",
            planned.reference,
            body={},
        )
        with self.database.sessions() as session:
            otp_code = session.get(BuyerOtpChallenge, UUID(challenge["challenge_id"])).demo_code
        if not otp_code:
            raise SimulationError("Demo OTP fixture did not produce a local test code.")
        authorization = self.call(
            public,
            "POST",
            path + "/verify",
            "buyer_verify",
            planned.reference,
            body={"code": otp_code},
        )
        auth = {"Authorization": "Bearer " + authorization["access_token"]}
        self.call(
            public, "GET", path + "/details", "buyer_details", planned.reference, headers=auth
        )
        if planned.kind == "reschedule":
            # Real backend clock is used; tomorrow UTC 04:00/06:00 falls on one Yangon day.
            start = (datetime.now(UTC) + timedelta(days=1)).replace(
                hour=4, minute=0, second=0, microsecond=0
            )
            for offset in (0, 2):
                begin = start + timedelta(hours=offset)
                self.call(
                    public,
                    "PATCH",
                    path + "/response",
                    "buyer_reschedule",
                    planned.reference,
                    headers=auth,
                    body={
                        "request_id": str(uuid4()),
                        "action": "RESCHEDULE",
                        "time_window": {
                            "start": begin.isoformat(),
                            "end": (begin + timedelta(hours=1)).isoformat(),
                        },
                    },
                )
            self.review(order_id)
        elif planned.kind == "pin_confirmation" or index == 0:
            self.call(
                public,
                "PATCH",
                path + "/location",
                "buyer_pin_proposal",
                planned.reference,
                headers=auth,
                body={
                    "request_id": str(uuid4()),
                    "latitude": "0",
                    "longitude": "0",
                    "initial_pin_acknowledged": True,
                },
            )
            self.review(order_id)
        self.call(
            public,
            "PATCH",
            path + "/response",
            "buyer_available",
            planned.reference,
            headers=auth,
            body={
                "request_id": str(uuid4()),
                "action": "AVAILABLE",
                "instructions": "Synthetic lab delivery note",
            },
        )

    def check_queue(self, who, client):
        data = self.call(client, "GET", f"/api/riders/{who['id']}/queue", "rider_queue")
        with self.database.sessions() as session:
            expected = set(
                session.scalars(
                    select(DeliveryAssignment.order_id)
                    .join(Order, DeliveryAssignment.order_id == Order.id)
                    .where(
                        DeliveryAssignment.rider_id == UUID(who["id"]),
                        DeliveryAssignment.status == "ACTIVE",
                        Order.status.in_(["ASSIGNED", "OUT_FOR_DELIVERY"]),
                    )
                )
            )
        assert {UUID(item["order_id"]) for item in data["items"]} == expected
        self.confirmed_window_observations += sum(
            item["confirmed_window_start"] is not None for item in data["items"]
        )
        unchanged = self.call(
            client,
            "GET",
            f"/api/riders/{who['id']}/queue?cursor={data['cursor']}",
            "rider_queue_poll",
        )
        assert unchanged["unchanged"] and unchanged["items"] == []
        self.queue_checks += 2
        return data

    def workflow(self, planned, order_id, index):
        self.transition(order_id, "NEEDS_REVIEW")
        if planned.confirm:
            self.buyer_flow(planned, order_id, index)
        if self.refresh(order_id)["status"] != "CONFIRMED":
            self.transition(order_id, "CONFIRMED")
        row = self.transition(order_id, "READY_FOR_DISPATCH")
        who = self.riders[index % len(self.riders)]
        assigned = self.call(
            self.dispatcher,
            "POST",
            f"/api/orders/{order_id}/assign",
            "rider_assign",
            planned.reference,
            body={
                "expected_version": row["version"],
                "rider_id": who["id"],
                "stop_sequence": index + 1,
            },
            expected=(201,),
        )
        rider_client = self.client(UUID(who["id"]))
        if self.config.demo and index == 0:
            self.call(
                self.dispatcher,
                "POST",
                f"/api/orders/{order_id}/assign",
                "duplicate_assignment_rejection",
                planned.reference,
                body={"expected_version": row["version"], "rider_id": who["id"]},
                expected=(409,),
            )
        self.check_queue(who, rider_client)
        # One live stop remains for queue/backlog evaluation; no invented completion.
        if self.config.demo and planned.reference == "LAB-00004":
            return
        started = self.call(
            rider_client,
            "PATCH",
            f"/api/riders/{who['id']}/deliveries/{order_id}/status",
            "delivery_start",
            planned.reference,
            body={
                "request_id": str(uuid4()),
                "expected_version": assigned["order_version"],
                "action": "START",
            },
        )
        action = {
            "request_id": str(uuid4()),
            "expected_version": started["order_version"],
            "action": "FAILED" if planned.fail else "DELIVERED",
        }
        if planned.fail:
            action["failure_reason"] = "CUSTOMER_UNAVAILABLE"
        else:
            action["cod_collected"] = True
        if self.config.demo and index == 0 and Decimal(row["cod_amount"] or "0") > 0:
            self.call(
                rider_client,
                "PATCH",
                f"/api/riders/{who['id']}/deliveries/{order_id}/status",
                "missing_cod_confirmation_rejection",
                planned.reference,
                body={
                    "request_id": str(uuid4()),
                    "expected_version": started["order_version"],
                    "action": "DELIVERED",
                },
                expected=(409,),
            )
        self.call(
            rider_client,
            "PATCH",
            f"/api/riders/{who['id']}/deliveries/{order_id}/status",
            "delivery_finish",
            planned.reference,
            body=action,
        )
        self.check_queue(who, rider_client)

    def execute(self):
        actor, merchants = uuid4(), [uuid4() for _ in range(self.config.merchants)]
        with self.database.sessions.begin() as session:
            session.add(
                User(
                    id=actor,
                    name="Synthetic lab dispatcher",
                    email="dispatch@lab.invalid",
                    role=UserRole.DISPATCHER,
                )
            )
            for i, merchant in enumerate(merchants):
                session.add(
                    User(
                        id=merchant,
                        name=f"သရုပ်ပြ အွန်လိုင်းအထည်ဆိုင် {i + 1} (အတု)",
                        email=f"merchant{i}@lab.invalid",
                        role=UserRole.MERCHANT,
                    )
                )
        self.dispatcher = self.client(actor)
        self.riders = [
            self.call(
                self.dispatcher,
                "POST",
                "/api/riders",
                "rider_create",
                body={"name": f"Synthetic rider {i + 1}", "operational_status": "AVAILABLE"},
                expected=(201,),
            )
            for i in range(self.config.riders)
        ]
        plan = generate_plan(self.config)
        public_rows, eligible = [], []
        for start in range(0, len(plan), self.config.batch_size):
            for index, planned in enumerate(plan[start : start + self.config.batch_size], start):
                parsed = self.call(
                    self.dispatcher,
                    "POST",
                    "/api/orders/parse",
                    "parse",
                    planned.reference,
                    body={"raw_text": planned.raw_text},
                    capture=index < 5,
                )
                created = self.call(
                    self.client(merchants[planned.merchant]),
                    "POST",
                    "/api/orders",
                    "order_create",
                    planned.reference,
                    body={
                        "merchant_id": str(merchants[planned.merchant]),
                        "raw_text": planned.raw_text,
                    },
                    expected=(201,),
                    capture=index < 5,
                )
                self.initial.append(parsed["confidence"])
                assert parsed["confidence"] == created["confidence_level"]
                self.ids[planned.reference] = created["id"]
                public_rows.append({**planned.public(), "initial_confidence": parsed["confidence"]})
                if (
                    created["confidence_level"] != "RED"
                    and len(eligible) < self.config.workflow_limit
                ):
                    eligible.append(planned)
        for i, planned in enumerate(eligible):
            self.workflow(planned, self.ids[planned.reference], i)
            self.workflow_count += 1
        for _ in range(self.config.read_samples):
            self.call(
                self.dispatcher, "GET", "/api/orders?page_size=20", "paginated_list", capture=False
            )
            self.call(
                self.dispatcher,
                "GET",
                "/api/orders?confidence=AMBER&status=DRAFT&page_size=20",
                "filtered_list",
                capture=False,
            )
        with self.database.sessions() as session:
            orders = list(session.scalars(select(Order)))
            events = list(session.scalars(select(DeliveryEvent)))
            assignments = list(session.scalars(select(DeliveryAssignment)))
            requests = list(session.scalars(select(BuyerRequest)))
            metrics = aggregate(
                orders, events, assignments, requests, self.initial, self.queue_checks
            )
            by_id = {str(o.id): o for o in orders}
            for row in public_rows:
                stored = by_id[self.ids[row["reference"]]]
                row.update(
                    status=str(stored.status),
                    cod_amount=str(stored.cod_amount) if stored.cod_amount is not None else None,
                )
        ingest = self.samples["parse"] + self.samples["order_create"]
        metrics.update(
            workflow_orders_exercised=self.workflow_count,
            http_calls=self.calls,
            unexpected_http_errors=0,
            expected_rejection_calls=sum(n for code, n in self.codes.items() if int(code) >= 400),
            duplicate_input_orders=sum(p.duplicate_of is not None for p in plan),
            confirmed_window_queue_observations=self.confirmed_window_observations,
            average_ingestion_api_ms=sum(ingest) / len(plan) if plan else 0,
        )
        return {
            "synthetic_only": True,
            "configuration": self.config.model_dump(),
            "metrics": metrics,
            "latency": latency_summary(self.samples),
            "rows": public_rows,
            "trace": self.trace,
            "trace_omitted_http_calls": self.omitted,
            "http_status_counts": dict(self.codes),
            "hubs": [
                {
                    "reference": f"HUB-{i + 1}",
                    "name": f"Synthetic Yangon hub {i + 1}",
                    "rider_numbers": [
                        j + 1 for j in range(self.config.riders) if j % self.config.hubs == i
                    ],
                }
                for i in range(self.config.hubs)
            ],
            "comparison": compare(len(plan), ComparisonConfig()),
            "sensitivity": sensitivity(len(plan)),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "database": "temporary SQLite",
                "transport": "TestClient",
            },
        }


def simulate(config: SimulationConfig):
    with tempfile.TemporaryDirectory(prefix="lannpya-logistics-lab-") as directory:
        url = f"sqlite+pysqlite:///{Path(directory).as_posix()}/lab.sqlite3"
        database = Database(url)
        try:
            upgrade_database(database)
            with ExitStack() as stack:
                result = Experiment(config, database, stack).execute()
        finally:
            database.dispose()
        reopened = Database(url)
        try:
            with reopened.sessions() as session:
                rows = list(session.scalars(select(Order)))
                events = list(session.scalars(select(DeliveryEvent)))
                assert len(rows) == config.orders
                assert len(events) == result["metrics"]["total_events"]
                fingerprint = hashlib.sha256(
                    "|".join(sorted(str(o.status) for o in rows)).encode()
                ).hexdigest()
                result["isolation"] = {
                    "database_reopened": True,
                    "persisted_orders": len(rows),
                    "persisted_events": len(events),
                    "status_fingerprint": fingerprint,
                    "cleanup": "temporary database removed on function return",
                }
        finally:
            reopened.dispose()
    return result
