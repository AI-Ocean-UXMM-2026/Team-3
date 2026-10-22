"""Mapping release acceptance: isolated SQLite, synthetic matrices, no external calls."""

import json
from datetime import timedelta
from uuid import uuid4

import httpx2 as httpx
import pytest
from test_routing import commit, preview, query
from test_three_role_workflow import save
from test_three_role_workflow import workspace as source_workspace

from app.core.config import Settings
from app.db.models import utcnow
from app.routing.http import HTTPProvider
from app.routing.offline import OfflineProvider
from app.routing.optimizer import optimize
from app.schemas.routing import Coordinate, MatrixQuery, PlannedVehicle, PlanQuery


@pytest.fixture
def workspace(tmp_path):
    yield from source_workspace.__wrapped__(tmp_path)


def case(capacity=1):
    start = utcnow() + timedelta(days=1)
    q = PlanQuery.model_validate(
        {
            "origin": {"latitude": 16.8, "longitude": 96.1},
            "orders": [{"order_id": str(uuid4()), "priority": p} for p in (0, 5)],
            "riders": [{"rider_id": str(uuid4()), "capacity": capacity}],
            "operating_window": {"start": start, "end": start + timedelta(hours=8)},
            "allow_simulation": True,
            "solver_seconds": 1,
        }
    )
    stops = [
        {
            "order_id": str(o.order_id),
            "coordinate": Coordinate(latitude=16.81, longitude=96.11),
            "service_seconds": 180,
            "demand": 1,
            "priority": o.priority,
            "rider_id": None,
            "window": None,
        }
        for o in q.orders
    ]
    matrix = OfflineProvider().get_route_matrix(
        MatrixQuery(
            locations=[q.origin] + [s["coordinate"] for s in stops],
            allow_simulation=True,
        )
    )
    return q, stops, matrix


def test_priority_prefers_urgent_parcel_without_breaking_capacity():
    q, stops, matrix = case()
    result = optimize(q, matrix, stops, q.riders)
    assert result.quality == "SIMULATED" and not result.globally_optimal
    vehicle = result.vehicles[0]
    assert vehicle.capacity == vehicle.load == 1
    assert vehicle.stops[0].priority == 5
    assert str(vehicle.stops[0].order_id) == stops[1]["order_id"]


def test_high_priority_never_overrides_hard_capacity():
    q, stops, matrix = case()
    stops[1]["demand"] = 2
    result = optimize(q, matrix, stops, q.riders)
    assert str(result.vehicles[0].stops[0].order_id) == stops[0]["order_id"]
    assert result.unassigned[0]["reason"] == "PARCEL_DEMAND_EXCEEDS_ALL_CAPACITIES"


def test_normalized_ors_road_matrix_reaches_solver_using_mock_transport_only():
    q, stops, _ = case(capacity=2)
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://api.openrouteservice.org/v2/matrix/driving-car"
        body = json.loads(request.content)
        assert body["metrics"] == ["distance", "duration"] and body["units"] == "m"
        assert body["locations"][0] == [96.1, 16.8]
        return httpx.Response(
            200,
            json={
                "distances": [[0, 1000, 1200], [1500, 0, 500], [1300, 600, 0]],
                "durations": [[0, 100, 120], [150, 0, 50], [130, 60, 0]],
            },
        )

    provider = HTTPProvider(
        Settings(
            _env_file=None,
            routing_provider="ors",
            routing_external_requests_enabled=True,
            ors_api_key="dummy-matrix-test-key",
        ),
        transport=httpx.MockTransport(handle),
    )
    matrix = provider.get_route_matrix(
        MatrixQuery(locations=[q.origin] + [s["coordinate"] for s in stops])
    )
    result = optimize(q, matrix, stops, q.riders)
    assert len(calls) == 1 and result.provider == "ors" and result.quality == "ROAD_STATIC"
    assert sum(len(v.stops) for v in result.vehicles) == 2
    assert result.vehicles[0].travel_seconds > 0
    # ROAD_STATIC is the normalized provider class; this test is not evidence of live road data.


def test_cancelled_parcel_invalidates_preview_and_replan_preserves_other_stop(workspace):
    c, ids, _ = workspace
    plan, orders, _ = preview(workspace)
    save(
        c["admin"].patch(
            "/api/orders/" + orders[0]["id"] + "/status",
            json={
                "expected_version": orders[0]["version"],
                "status": "CANCELLED",
            },
        )
    )
    assert commit(c, plan, 409)["error"]["code"] == "ROUTE_PLAN_STALE"
    next_plan = save(
        c["admin"].post("/api/routes/optimize", json=query(orders, [ids["rider"]])), 201
    )
    assert next_plan["result"]["unassigned"][0]["reason"] == "TERMINAL_ORDER_EXCLUDED"
    committed = commit(c, next_plan)
    assert [s["order_id"] for v in committed["result"]["vehicles"] for s in v["stops"]] == [
        orders[1]["id"]
    ]


def test_preview_exposes_capacity_priority_and_window_without_assigning(workspace):
    c, ids, _ = workspace
    _, orders, _ = preview(workspace, count=1)
    body = query(orders, [ids["rider"]])
    body["orders"][0]["priority"] = 4
    plan = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    vehicle = plan["result"]["vehicles"][0]
    assert vehicle["load"] == 1 and vehicle["capacity"] == 20
    assert vehicle["stops"][0]["priority"] == 4
    assert "delivery_window" in vehicle["stops"][0]
    assert save(c["admin"].get("/api/orders/" + orders[0]["id"]))["status"] == "DRAFT"


def test_historical_vehicle_without_new_fields_remains_readable():
    v = PlannedVehicle.model_validate(
        {
            "rider_id": uuid4(),
            "stops": [],
            "distance_meters": 0,
            "duration_seconds": 0,
            "travel_seconds": 0,
        }
    )
    assert v.capacity is None and v.load is None
