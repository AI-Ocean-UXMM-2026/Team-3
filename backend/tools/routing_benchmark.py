"""Bounded API/solver benchmark; owns a disposable database, never reads customer data."""

import argparse
import json
import platform
import secrets
import statistics
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import User
from app.db.routing_models import RoutingPlan
from app.db.session import Database
from app.domain.lifecycle import UserRole
from app.main import create_app
from app.routing.offline import OfflineProvider
from app.schemas.routing import MatrixQuery
from app.services.buyer_confirmation import YANGON


def checked(response, status=200):
    if response.status_code != status:
        raise RuntimeError(f"Benchmark API failed: HTTP {response.status_code}")
    return response.json()


def run():
    records = []
    actor, secret = uuid4(), secrets.token_urlsafe(40)
    day = (datetime.now(YANGON) + timedelta(days=1)).date().isoformat()
    with tempfile.TemporaryDirectory(prefix="lannpya-routing-bench-") as directory:
        url = f"sqlite+pysqlite:///{Path(directory) / 'routing.sqlite3'}"
        db = Database(url)
        upgrade_database(db)
        with db.sessions.begin() as session:
            session.add(
                User(
                    id=actor,
                    name="FICTIONAL Routing Benchmark",
                    role=UserRole.ADMIN,
                    email="routing-benchmark@example.test",
                )
            )
        settings = Settings(
            _env_file=None,
            environment="test",
            order_management_enabled=True,
            dev_actor_id=actor,
            dev_access_token=secret,
            routing_provider="offline",
            routing_max_stops=50,
            routing_requests_per_minute=60,
        )
        with TestClient(
            create_app(settings, database=db),
            client=("127.0.0.1", 50000),
            headers={"X-Dev-Access-Token": secret},
        ) as client:
            riders = [
                checked(
                    client.post(
                        "/api/riders",
                        json={"name": f"Synthetic Rider {i}", "operational_status": "AVAILABLE"},
                    ),
                    201,
                )["id"]
                for i in range(3)
            ]
            orders, points = [], [{"latitude": 16.8, "longitude": 96.1}]
            for i in range(50):
                point = {
                    "latitude": round(16.8 + 0.01 * (i // 7), 7),
                    "longitude": round(96.1 + 0.01 * (i % 7), 7),
                }
                points.append(point)
                saved = checked(
                    client.post(
                        "/api/orders",
                        json={
                            "structured": {
                                "customer_name": f"FICTIONAL Benchmark {i}",
                                "customer_phone": "09790000000",
                                "township": "Hlaing",
                                "street": "Synthetic test grid, not a customer home",
                                "latitude": str(point["latitude"]),
                                "longitude": str(point["longitude"]),
                                "cod_amount": "25000",
                                "delivery_time_window": "Any time",
                            },
                            "parcel": {
                                "item": "FICTIONAL benchmark",
                                "delivery_day": day,
                                "hub_received": True,
                            },
                        },
                    ),
                    201,
                )
                orders.append(saved["id"])
            for count in [5, 10, 20, 50]:
                matrix_times, api_times, solver_times, served = [], [], [], []
                for _ in range(3):
                    started = time.perf_counter()
                    OfflineProvider().get_route_matrix(
                        MatrixQuery(locations=points[: count + 1], allow_simulation=True)
                    )
                    matrix_times.append((time.perf_counter() - started) * 1000)
                    body = {
                        "origin": points[0],
                        "orders": [{"order_id": i} for i in orders[:count]],
                        "riders": [{"rider_id": i, "capacity": 20} for i in riders],
                        "operating_window": {
                            "start": day + "T08:00:00+06:30",
                            "end": day + "T23:00:00+06:30",
                        },
                        "allow_simulation": True,
                        "solver_seconds": 1,
                    }
                    started = time.perf_counter()
                    plan = checked(client.post("/api/routes/optimize", json=body), 201)
                    api_times.append((time.perf_counter() - started) * 1000)
                    solver_times.append(plan["result"]["elapsed_ms"])
                    vehicles = plan["result"]["vehicles"]
                    served.append(sum(len(v["stops"]) for v in vehicles))
                    assert all(sum(s["demand"] for s in v["stops"]) <= 20 for v in vehicles)
                    assert all(
                        datetime.fromisoformat(s["departure"])
                        <= datetime.fromisoformat(body["operating_window"]["end"])
                        for v in vehicles
                        for s in v["stops"]
                    )
                    assert plan["state"] == "PREVIEW" and plan["result"]["quality"] == "SIMULATED"
                records.append(
                    {
                        "stops": count,
                        "matrix_cells": (count + 1) ** 2,
                        "samples": 3,
                        "assigned_counts": served,
                        "capacity_and_horizon_compliant": True,
                        "matrix_median_ms": round(statistics.median(matrix_times), 3),
                        "solver_median_ms": round(statistics.median(solver_times), 3),
                        "api_median_ms": round(statistics.median(api_times), 3),
                        "api_p95_nearest_rank_ms": round(max(api_times), 3),
                    }
                )
        db.dispose()
        reopened = Database(url)
        with reopened.sessions() as session:
            persisted = session.scalar(select(func.count()).select_from(RoutingPlan))
        reopened.dispose()
        assert persisted == 12
    return {
        "label": "SIMULATED / TEST DATA; no measured Yangon road performance",
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "processor": platform.processor(),
            "database": "isolated SQLite",
            "transport": "in-process FastAPI TestClient",
            "ortools": "9.15.6755",
        },
        "method": (
            "3 samples/size, 1 second solver budget, 3 riders x 20 capacity; "
            "p95 nearest-rank of 3 is max; no live provider calls"
        ),
        "persisted_previews_after_reopen": persisted,
        "results": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
