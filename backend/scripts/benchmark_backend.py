"""Bounded in-process API latency benchmark. Only temporary, synthetic SQLite data."""

import argparse
import json
import math
import platform
import statistics
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import Order, User
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole
from app.main import create_app


def benchmark(size, samples):
    with tempfile.TemporaryDirectory(prefix="lannpya-bench-") as folder:
        database = Database(f"sqlite+pysqlite:///{Path(folder).as_posix()}/bench.sqlite3")
        upgrade_database(database)
        dispatcher, merchant = uuid4(), uuid4()
        with database.sessions.begin() as session:
            session.add_all(
                [
                    User(
                        id=dispatcher,
                        name="Benchmark dispatcher",
                        email="d@bench.invalid",
                        role=UserRole.DISPATCHER,
                    ),
                    User(
                        id=merchant,
                        name="Benchmark merchant",
                        email="m@bench.invalid",
                        role=UserRole.MERCHANT,
                    ),
                ]
            )
        app = create_app(
            Settings(
                _env_file=None,
                environment="test",
                order_management_enabled=True,
                parser_mode="rules",
                dev_actor_id=dispatcher,
                dev_access_token="benchmark-only-" + "x" * 40,
                buyer_verify_limit_per_minute=60,
                buyer_request_limit_per_minute=600,
            ),
            database=database,
        )
        metrics = {}
        parse_text = json.loads(
            (BACKEND_ROOT / "tests/fixtures/delivery_corpus.json").read_text("utf-8")
        )["records"][10]["raw_text"]
        try:
            with TestClient(
                app,
                client=("127.0.0.1", 50000),
                headers={"X-Dev-Access-Token": "benchmark-only-" + "x" * 40},
            ) as client:
                body = {
                    "merchant_id": str(merchant),
                    "structured": {
                        "customer_phone": "09790000000",
                        "township": "Hlaing",
                        "street": "Benchmark synthetic lane",
                        "cod_amount": "25000",
                    },
                }
                response = client.post("/api/orders", json=body)
                assert response.status_code == 201
                row = response.json()
                # Bulk fixture setup is explicitly not API-create throughput. It permits
                # controlled table-size measurements without 5,000 redundant mutations.
                with database.sessions() as session:
                    original = session.get(Order, UUID(row["id"]))
                    template = {
                        column.name: getattr(original, column.name)
                        for column in Order.__table__.columns
                        if column.name != "id"
                    }
                with database.sessions.begin() as session:
                    session.execute(
                        insert(Order), [{**template, "id": uuid4()} for _ in range(size - 1)]
                    )

                def measure(name, call, expected=200):
                    durations, errors = [], 0
                    for i in range(samples):
                        started = time.perf_counter()
                        reply = call(i)
                        durations.append((time.perf_counter() - started) * 1000)
                        errors += reply.status_code != expected
                    ordered = sorted(durations)
                    metrics[name] = {
                        "requests": samples,
                        "median_ms": round(statistics.median(durations), 3),
                        "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
                        "serial_requests_per_second": round(1000 / statistics.mean(durations), 2),
                        "error_count": errors,
                    }

                measure("health", lambda _: client.get("/health"))
                measure(
                    "parse_rules",
                    lambda _: client.post(
                        "/api/orders/parse",
                        json={"raw_text": parse_text},
                    ),
                )
                measure("create_order", lambda _: client.post("/api/orders", json=body), 201)
                measure("list_page", lambda _: client.get("/api/orders?page=1&page_size=20"))
                measure(
                    "filter_search",
                    lambda _: client.get(
                        "/api/orders?status=DRAFT&confidence=AMBER&q=Benchmark&page_size=20"
                    ),
                )
                version = row["version"]

                def correction(i):
                    nonlocal version
                    reply = client.patch(
                        f"/api/orders/{row['id']}",
                        json={
                            "expected_version": version,
                            "delivery_instructions": f"Benchmark note {i}",
                        },
                    )
                    if reply.status_code == 200:
                        version = reply.json()["version"]
                    return reply

                measure("correction_with_event", correction)
                reviewed = client.patch(
                    f"/api/orders/{row['id']}/status",
                    json={"status": "NEEDS_REVIEW", "expected_version": version},
                )
                assert reviewed.status_code == 200
                link = client.post(f"/api/orders/{row['id']}/confirmation-link")
                assert link.status_code == 201
                buyer_path = "/api" + link.json()["confirmation_url"]
                measure(
                    "buyer_verify",
                    lambda _: client.post(buyer_path + "/verify", json={"last_four": "0000"}),
                )
                who = client.post(
                    "/api/riders",
                    json={"name": "Benchmark synthetic rider", "operational_status": "AVAILABLE"},
                ).json()
                current = reviewed.json()
                for status in ("CONFIRMED", "READY_FOR_DISPATCH"):
                    reply = client.patch(
                        f"/api/orders/{row['id']}/status",
                        json={
                            "expected_version": current["version"],
                            "status": status,
                            "acknowledge_unverified_location": True,
                        },
                    )
                    assert reply.status_code == 200
                    current = reply.json()
                assigned = client.post(
                    f"/api/orders/{row['id']}/assign",
                    json={"expected_version": current["version"], "rider_id": who["id"]},
                )
                assert assigned.status_code == 201
                measure(
                    "rider_queue_one_active_stop",
                    lambda _: client.get(f"/api/riders/{who['id']}/queue"),
                )
                with database.sessions() as session:
                    actual = session.scalar(select(func.count()).select_from(Order))
        finally:
            database.dispose()
        return {"fixture_order_count": size, "final_order_count": actual, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=15, choices=range(5, 51))
    args = parser.parse_args()
    result = {
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "database": "temporary SQLite",
            "transport": "TestClient in-process",
        },
        "limitations": (
            "Serial latency microbenchmark, not network/load capacity. One active queue stop."
        ),
        "runs": [benchmark(size, args.samples) for size in (100, 1000, 5000)],
    }
    output = BACKEND_ROOT.parent / "docs/overnight_audit/performance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if any(metric["error_count"] for run in result["runs"] for metric in run["metrics"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
