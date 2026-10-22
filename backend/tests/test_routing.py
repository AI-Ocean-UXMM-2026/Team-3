import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import httpx2 as httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_three_role_workflow import day, manual, save, verify_customer
from test_three_role_workflow import workspace as source_workspace

from app.core.config import Settings
from app.db.models import DeliveryEvent
from app.db.rider_models import DeliveryAssignment
from app.db.routing_models import RoutingPlan
from app.routing.base import RoutingFailure
from app.routing.factory import provider_for
from app.routing.http import HTTPProvider
from app.routing.offline import OfflineProvider
from app.routing.optimizer import optimize
from app.schemas.routing import Coordinate, MatrixQuery, PlanQuery, RouteQuery, TimeWindow


@pytest.fixture
def workspace(tmp_path):
    yield from source_workspace.__wrapped__(tmp_path)


def query(orders, riders, **extra):
    start = datetime.fromisoformat(day() + "T00:00:00+06:30")
    return {
        "origin": {"latitude": 16.8, "longitude": 96.1},
        "orders": [{"order_id": o["id"]} for o in orders],
        "riders": [{"rider_id": str(r)} for r in riders],
        "operating_window": {
            "start": start.isoformat(),
            "end": (start + timedelta(hours=23, minutes=59)).isoformat(),
        },
        "allow_simulation": True,
        "solver_seconds": 1,
        **extra,
    }


def preview(workspace, count=2, **extra):
    c, ids, db = workspace
    orders = [manual(workspace) for _ in range(count)]
    body = query(orders, [ids["rider"]], **extra)
    return save(c["admin"].post("/api/routes/optimize", json=body), 201), orders, body


def commit(c, plan, status=200):
    return save(
        c["admin"].post(
            f"/api/routes/plans/{plan['id']}/commit",
            json={
                "expected_version": plan["version"],
                "allow_simulation": True,
                "acknowledge_unverified_location": True,
            },
        ),
        status,
    )


@pytest.mark.parametrize(
    "point",
    [
        dict(latitude=91, longitude=96),
        dict(latitude=16, longitude=-181),
        dict(latitude="16", longitude=96),
        dict(latitude=True, longitude=96),
        dict(latitude=float("nan"), longitude=96),
    ],
)
def test_coordinate_validation(point):
    with pytest.raises(ValidationError):
        Coordinate(**point)


def test_offline_is_explicit_and_graph_cost_is_not_straight_line():
    a, b = Coordinate(latitude=16.8, longitude=96.1), Coordinate(latitude=16.82, longitude=96.12)
    provider = OfflineProvider()
    with pytest.raises(RoutingFailure, match="ACKNOWLEDGEMENT"):
        provider.get_route(RouteQuery(origin=a, destination=b))
    r = provider.get_route(RouteQuery(origin=a, destination=b, allow_simulation=True))
    assert r.quality == "SIMULATED" and not r.traffic_aware
    assert r.distance_meters == 2 * 1112 + 2 * 1064
    assert len(r.geometry.coordinates) >= 5
    assert (
        provider.get_route(
            RouteQuery(origin=a, destination=a, allow_simulation=True)
        ).distance_meters
        == 0
    )
    with pytest.raises(RoutingFailure, match="FIXTURE"):
        provider.get_route(
            RouteQuery(
                origin=a, destination=Coordinate(latitude=0, longitude=0), allow_simulation=True
            )
        )


def test_missing_credentials_external_gate_and_no_silent_fallback():
    for provider in ("google", "ors"):
        s = Settings(_env_file=None, routing_provider=provider)
        with pytest.raises(RoutingFailure, match="DISABLED"):
            HTTPProvider(s).ready("DRIVE")
        s.routing_external_requests_enabled = True
        with pytest.raises(RoutingFailure, match="KEY_MISSING"):
            HTTPProvider(s).ready("DRIVE")
    with pytest.raises(RoutingFailure, match="FORBIDDEN"):
        provider_for(Settings(
            _env_file=None, environment="production", buyer_otp_mode="twilio",
            buyer_otp_external_sends_enabled=True, buyer_twilio_account_sid="ACtest",
            buyer_twilio_auth_token="test-token", buyer_twilio_verify_service_sid="VAtest",
        ), True)
    with pytest.raises(RoutingFailure, match="DISABLED"):
        provider_for(Settings(_env_file=None, routing_provider="disabled"), True)


def http_provider(name, handler):
    return HTTPProvider(
        Settings(
            _env_file=None,
            routing_provider=name,
            routing_external_requests_enabled=True,
            google_routes_api_key="synthetic-routing-key",
            ors_api_key="synthetic-ors-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def test_google_route_request_mask_privacy_and_normalization():
    def handle(r):
        body = json.loads(r.content)
        assert body["routingPreference"] == "TRAFFIC_UNAWARE"
        assert body["polylineEncoding"] == "GEO_JSON_LINESTRING"
        assert "routes.duration" in r.headers["X-Goog-FieldMask"]
        assert "synthetic-routing-key" not in str(r.url)
        assert "phone" not in r.content.decode() and "customer" not in r.content.decode()
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "distanceMeters": 1800,
                        "duration": "240.1s",
                        "polyline": {
                            "geoJsonLinestring": {
                                "type": "LineString",
                                "coordinates": [[96.1, 16.8], [96.12, 16.82]],
                            }
                        },
                    }
                ]
            },
        )

    p = http_provider("google", handle)
    r = p.get_route(
        RouteQuery(
            origin=Coordinate(latitude=16.8, longitude=96.1),
            destination=Coordinate(latitude=16.82, longitude=96.12),
        )
    )
    assert r.duration_seconds == 241 and r.distance_meters == 1800 and r.quality == "ROAD_STATIC"
    with pytest.raises(RoutingFailure, match="UNSUPPORTED"):
        p.ready("TWO_WHEELER")


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "CREDENTIAL"),
        (403, "QUOTA"),
        (429, "RATE_LIMITED"),
        (500, "UNAVAILABLE"),
        (400, "UNSUPPORTED"),
    ],
)
def test_provider_http_failures_do_not_expose_response(status, expected):
    p = http_provider(
        "google", lambda r: httpx.Response(status, text="PRIVATE synthetic-routing-key")
    )
    with pytest.raises(RoutingFailure, match=expected) as e:
        p.get_route(
            RouteQuery(
                origin=Coordinate(latitude=16.8, longitude=96.1),
                destination=Coordinate(latitude=16.82, longitude=96.12),
            )
        )
    assert "PRIVATE" not in str(e.value) and "key" not in str(e.value)


def test_provider_timeout_invalid_json_and_geometry():
    def timeout(r):
        raise httpx.ReadTimeout("private details")

    for handle, code in [
        (timeout, "TIMEOUT"),
        (lambda r: httpx.Response(200, text="not json"), "INVALID_RESPONSE"),
        (
            lambda r: httpx.Response(200, json={"routes": [{"distanceMeters": -1}]}),
            "INVALID_RESPONSE",
        ),
    ]:
        p = http_provider("google", handle)
        with pytest.raises(RoutingFailure, match=code):
            p.get_route(
                RouteQuery(
                    origin=Coordinate(latitude=16.8, longitude=96.1),
                    destination=Coordinate(latitude=16.82, longitude=96.12),
                )
            )


def test_ors_geojson_matrix_unreachable_and_two_wheeler_rejection():
    points = [
        Coordinate(latitude=16.8, longitude=96.1),
        Coordinate(latitude=16.82, longitude=96.12),
    ]

    def handle(r):
        assert json.loads(r.content).get("locations", json.loads(r.content).get("coordinates"))[
            0
        ] == [96.1, 16.8]
        if "/matrix/" in str(r.url):
            return httpx.Response(
                200, json={"distances": [[0, None], [900, 0]], "durations": [[0, None], [200, 0]]}
            )
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[96.1, 16.8], [96.12, 16.82]],
                        },
                        "properties": {"summary": {"distance": 1800.4, "duration": 240.2}},
                    }
                ]
            },
        )

    p = http_provider("ors", handle)
    assert p.get_route(RouteQuery(origin=points[0], destination=points[1])).distance_meters == 1801
    assert p.get_route_matrix(MatrixQuery(locations=points)).durations[0][1] is None
    with pytest.raises(RoutingFailure, match="UNSUPPORTED"):
        p.ready("TWO_WHEELER")


def test_google_matrix_indexes_element_errors_and_missing_cells():
    pts = [Coordinate(latitude=16.8, longitude=96.1), Coordinate(latitude=16.81, longitude=96.11)]
    cells = [
        {
            "originIndex": i,
            "destinationIndex": j,
            "status": {},
            "condition": "ROUTE_EXISTS",
            "distanceMeters": 0 if i == j else 1000,
            "duration": "0s" if i == j else "120s",
        }
        for i in range(2)
        for j in range(2)
    ]
    p = http_provider("google", lambda r: httpx.Response(200, json=cells))
    assert p.get_route_matrix(MatrixQuery(locations=pts)).distances[1][0] == 1000
    cells[0]["status"] = {"code": 7}
    with pytest.raises(RoutingFailure, match="ELEMENT_ERROR"):
        p.get_route_matrix(MatrixQuery(locations=pts))
    cells.pop(0)
    with pytest.raises(RoutingFailure, match="INVALID_RESPONSE"):
        p.get_route_matrix(MatrixQuery(locations=pts))


@pytest.mark.parametrize(
    "count,capacities", [(5, [5]), (20, [20]), (20, [10, 7, 3]), (20, [2, 3]), (10, [1, 2, 3])]
)
def test_solver_multiple_riders_capacities_and_windows(count, capacities):
    ids = [uuid4() for _ in capacities]
    body = query([{"id": str(uuid4())} for _ in range(count)], ids)
    for rider, capacity in zip(body["riders"], capacities):
        rider["capacity"] = capacity
    q = PlanQuery.model_validate(body)
    stops = [
        {
            "order_id": str(o.order_id),
            "coordinate": Coordinate(
                latitude=16.8 + 0.01 * (i // 5), longitude=96.1 + 0.01 * (i % 5)
            ),
            "service_seconds": 180,
            "demand": 1,
            "rider_id": None,
            "window": None,
        }
        for i, o in enumerate(q.orders)
    ]
    m = OfflineProvider().get_route_matrix(
        MatrixQuery(locations=[q.origin] + [s["coordinate"] for s in stops], allow_simulation=True)
    )
    result = optimize(q, m, stops, q.riders)
    assert sum(len(v.stops) for v in result.vehicles) == min(count, sum(capacities))
    for vehicle in result.vehicles:
        capacity = next(r.capacity for r in q.riders if r.rider_id == vehicle.rider_id)
        assert sum(s.demand for s in vehicle.stops) <= capacity
        assert all(
            q.operating_window.start <= s.arrival < s.departure <= q.operating_window.end
            for s in vehicle.stops
        )
    assert not result.globally_optimal and result.elapsed_ms < 5000


def test_solver_respects_unreachable_and_impossible_time_window():
    q = PlanQuery.model_validate(query([{"id": str(uuid4())}], [uuid4()]))
    p = Coordinate(latitude=16.81, longitude=96.11)
    m = OfflineProvider().get_route_matrix(
        MatrixQuery(locations=[q.origin, p], allow_simulation=True)
    )
    stop = {
        "order_id": str(q.orders[0].order_id),
        "coordinate": p,
        "service_seconds": 180,
        "demand": 1,
        "rider_id": None,
        "window": TimeWindow(
            start=q.operating_window.start, end=q.operating_window.start + timedelta(seconds=60)
        ),
    }
    assert (
        optimize(q, m, [stop], q.riders).unassigned[0]["reason"]
        == "TIME_WINDOW_OUTSIDE_HORIZON_OR_SERVICE_TOO_LONG"
    )
    stop["window"] = None
    m.distances[0][1] = m.durations[0][1] = None
    assert optimize(q, m, [stop], q.riders).solver_status == "INFEASIBLE"


def test_preview_does_not_assign_commit_atomic_and_idempotent(workspace):
    c, ids, db = workspace
    plan, orders, _ = preview(workspace, count=3)
    assert plan["result"]["quality"] == "SIMULATED" and plan["state"] == "PREVIEW"
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment)) == 0
    committed = commit(c, plan)
    assert committed["state"] == "COMMITTED" and not committed["stale"]
    again = commit(c, plan)
    assert again["version"] == committed["version"]
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment)) == 3
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(DeliveryEvent.event_type == "RIDER_SEQUENCE_CHANGED")
            )
            == 3
        )
    queue = save(c["rider"].get(f"/api/riders/{ids['rider']}/queue"))
    assert len(queue["items"]) == 3
    assert [o["stop_sequence"] for o in queue["items"]] == [1, 2, 3]
    own = save(c["rider"].get(f"/api/riders/{ids['rider']}/route-plans"))
    assert own["items"][0]["result"]["vehicles"][0]["rider_id"] == str(ids["rider"])
    assert c["other"].get(f"/api/riders/{ids['rider']}/route-plans").status_code == 403
    assert (
        c["rider"].post("/api/routes/optimize", json=query(orders, [ids["rider"]])).status_code
        == 403
    )


def test_stale_preview_rejects_without_any_assignment(workspace):
    c, _, db = workspace
    plan, orders, _ = preview(workspace)
    save(
        c["admin"].patch(
            "/api/orders/" + orders[0]["id"],
            json={"expected_version": orders[0]["version"], "landmark": "Fictional changed gate"},
        )
    )
    assert commit(c, plan, 409)["error"]["code"] == "ROUTE_PLAN_STALE"
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment)) == 0


def test_missing_gps_unavailable_riders_duplicates_and_authorization(workspace):
    c, ids, _ = workspace
    o = manual(workspace, coordinates=False)
    body = query([o], [ids["rider"]])
    result = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    assert result["result"]["unassigned"][0]["reason"] == "MISSING_DELIVERY_PIN"
    body["orders"] *= 2
    assert c["admin"].post("/api/routes/optimize", json=body).status_code == 422
    assert c["rider"].get("/api/routes/provider-status").status_code == 403
    assert (
        c["admin"]
        .post(
            "/api/routes/calculate",
            json={
                "origin": {"latitude": 91, "longitude": 96},
                "destination": {"latitude": 16.8, "longitude": 96.1},
            },
        )
        .status_code
        == 422
    )


def test_commit_rolls_back_when_one_ready_step_fails(workspace, monkeypatch):
    c, _, db = workspace
    plan, _, _ = preview(workspace)
    from app.services import route_planning

    original = route_planning.prepare_assignment
    calls = []

    def fail_second(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            from app.core.order_errors import OrderAPIError

            raise OrderAPIError(409, "SYNTHETIC_CONFLICT", "Synthetic transaction failure")
        return original(*a, **k)

    monkeypatch.setattr(route_planning, "prepare_assignment", fail_second)
    assert commit(c, plan, 409)["error"]["code"] == "SYNTHETIC_CONFLICT"
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment)) == 0
        assert session.get(RoutingPlan, UUID(plan["id"])).state == "PREVIEW"


def test_google_missing_costs_are_not_fabricated_as_zero():
    pts = [Coordinate(latitude=16.8, longitude=96.1), Coordinate(latitude=16.81, longitude=96.11)]
    cells = [
        {"originIndex": i, "destinationIndex": j, "condition": "ROUTE_EXISTS"}
        for i in range(2)
        for j in range(2)
    ]
    p = http_provider("google", lambda r: httpx.Response(200, json=cells))
    with pytest.raises(RoutingFailure, match="INVALID_RESPONSE"):
        p.get_route_matrix(MatrixQuery(locations=pts))
    for cell in cells:
        if cell["originIndex"] != cell["destinationIndex"]:
            cell.update(distanceMeters=1000, duration="120s")
    assert p.get_route_matrix(MatrixQuery(locations=pts)).durations[0][0] == 0


def test_plan_expiry_and_rider_availability_make_preview_stale(workspace):
    c, ids, db = workspace
    plan, _, _ = preview(workspace)
    with db.sessions.begin() as s:
        p = s.get(RoutingPlan, UUID(plan["id"]))
        p.created_at -= timedelta(hours=1)
    plan = save(c["admin"].get("/api/routes/plans/" + plan["id"]))
    assert commit(c, plan, 409)["error"]["code"] == "ROUTE_PLAN_STALE"
    plan, _, _ = preview(workspace, count=1)
    rider = save(c["admin"].get(f"/api/riders/{ids['rider']}"))
    save(
        c["admin"].patch(
            f"/api/riders/{ids['rider']}",
            json={"expected_version": rider["version"], "operational_status": "OFFLINE"},
        )
    )
    assert commit(c, plan, 409)["error"]["code"] == "ROUTE_PLAN_STALE"


def test_native_clock_window_is_a_hard_constraint(workspace):
    c, ids, _ = workspace
    order = manual(workspace)
    save(
        c["admin"].patch(
            "/api/orders/" + order["id"],
            json={"expected_version": order["version"], "delivery_time_window": "10:00–12:00"},
        )
    )
    result = save(c["admin"].post("/api/routes/optimize", json=query([order], [ids["rider"]])), 201)
    stop = result["result"]["vehicles"][0]["stops"][0]
    assert (
        datetime.fromisoformat(stop["arrival"])
        .astimezone(datetime.fromisoformat(day() + "T00:00:00+06:30").tzinfo)
        .hour
        == 10
    )
    assert datetime.fromisoformat(stop["departure"]).hour <= 12


def test_competing_previews_cannot_duplicate_assignments(workspace):
    from concurrent.futures import ThreadPoolExecutor

    c, ids, db = workspace
    plan, orders, body = preview(workspace)
    other = save(c["admin"].post("/api/routes/optimize", json=body), 201)

    def attempt(p):
        return (
            c["admin"]
            .post(
                f"/api/routes/plans/{p['id']}/commit",
                json={
                    "expected_version": p["version"],
                    "allow_simulation": True,
                    "acknowledge_unverified_location": True,
                },
            )
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt, [plan, other]))
    assert sorted(statuses) == [200, 409]
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(DeliveryAssignment)) == len(orders)


def test_active_stops_cannot_be_silently_dropped_from_commit(workspace):
    c, ids, _ = workspace
    plan, orders, _ = preview(workspace, count=2)
    commit(c, plan)
    body = query(orders[:1], [ids["rider"]])
    new = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    assert commit(c, new, 409)["error"]["code"] == "INCLUDE_ALL_ACTIVE_STOPS"


def test_unavailable_rider_requires_explicit_unassignment_before_reallocation(workspace):
    c, ids, _ = workspace
    plan, orders, body = preview(workspace, count=1)
    commit(c, plan)
    rider = save(c["admin"].get(f"/api/riders/{ids['rider']}"))
    save(
        c["admin"].patch(
            f"/api/riders/{ids['rider']}",
            json={"expected_version": rider["version"], "operational_status": "OFFLINE"},
        )
    )
    body["riders"] = [{"rider_id": str(ids["other"])}]
    blocked = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    assert not blocked["result"]["vehicles"]
    order = save(c["admin"].get("/api/orders/" + orders[0]["id"]))
    save(
        c["admin"].post(
            "/api/orders/" + order["id"] + "/unassign", json={"expected_version": order["version"]}
        )
    )
    replacement = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    assert replacement["result"]["vehicles"][0]["rider_id"] == str(ids["other"])
    commit(c, replacement)


def test_replanning_preserves_completed_stops_and_hides_former_coordinates(workspace):
    from test_three_role_workflow import action, deliver

    c, ids, db = workspace
    plan, orders, body = preview(workspace, count=2)
    saved = commit(c, plan)
    route_id = saved["routes"][str(ids["rider"])]
    route = next(r for r in save(c["admin"].get("/api/routes"))["items"] if r["id"] == route_id)
    save(action(c["admin"], route, "DISPATCH"))
    queue = save(c["rider"].get(f"/api/riders/{ids['rider']}/queue"))
    completed = queue["items"][0]["order_id"]
    save(deliver(workspace, queue["items"][0]))
    new = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    assert any(
        o["order_id"] == completed and o["reason"] == "TERMINAL_ORDER_EXCLUDED"
        for o in new["result"]["unassigned"]
    )
    commit(c, new)
    own = save(c["rider"].get(f"/api/riders/{ids['rider']}/route-plans"))
    for p in own["items"]:
        assert all(s["order_id"] != completed for v in p["result"]["vehicles"] for s in v["stops"])
    route = next(r for r in save(c["admin"].get("/api/routes"))["items"] if r["id"] == route_id)
    assert completed in route["order_ids"]
    with db.sessions() as s:
        assert s.get(RoutingPlan, UUID(new["id"])).state == "COMMITTED"


def test_expensive_operations_have_a_persistent_actor_budget(workspace):
    c, _, _ = workspace
    body = {
        "origin": {"latitude": 16.8, "longitude": 96.1},
        "destination": {"latitude": 16.81, "longitude": 96.11},
        "allow_simulation": True,
    }
    for _ in range(10):
        save(c["admin"].post("/api/routes/calculate", json=body))
    assert c["admin"].post("/api/routes/calculate", json=body).status_code == 429
    assert c["admin"].get("/api/routes/provider-status").status_code == 200


def test_approved_buyer_reschedule_invalidates_plan_and_moves_hard_window(workspace):
    c, ids, db = workspace
    plan, orders, body = preview(workspace, count=1)
    identifier = orders[0]["id"]
    save(
        c["admin"].patch(
            f"/api/orders/{identifier}/status",
            json={"expected_version": orders[0]["version"], "status": "NEEDS_REVIEW"},
        )
    )
    link = save(c["admin"].post(f"/api/orders/{identifier}/confirmation-link"), 201)
    token = link["confirmation_url"].rsplit("/", 1)[1]
    auth = verify_customer(c["admin"], token, db)
    start = datetime.fromisoformat(day() + "T10:00:00+06:30") + timedelta(days=1)
    end = start + timedelta(hours=2)
    request = save(
        c["admin"].patch(
            f"/api/confirm/{token}/response",
            headers={"Authorization": "Bearer " + auth["access_token"]},
            json={
                "request_id": str(uuid4()),
                "action": "RESCHEDULE",
                "time_window": {"start": start.isoformat(), "end": end.isoformat()},
            },
        )
    )
    assert request["decision"] == "REVIEW_REQUIRED"
    request = save(c["admin"].get(f"/api/orders/{identifier}/buyer-requests"))["items"][0]
    order = save(c["admin"].get(f"/api/orders/{identifier}"))
    save(
        c["admin"].patch(
            f"/api/orders/{identifier}/buyer-requests/{request['id']}",
            json={
                "expected_version": order["version"],
                "decision": "APPROVE",
                "reason": "Fictional courier policy review",
            },
        )
    )
    assert commit(c, plan, 409)["error"]["code"] == "ROUTE_PLAN_STALE"
    order = save(c["admin"].get(f"/api/orders/{identifier}"))
    assert order["parsing_metadata"]["parcel"]["delivery_day"] == start.date().isoformat()
    body["operating_window"] = {
        "start": start.replace(hour=8).isoformat(),
        "end": end.replace(hour=18).isoformat(),
    }
    replanned = save(c["admin"].post("/api/routes/optimize", json=body), 201)
    stop = replanned["result"]["vehicles"][0]["stops"][0]
    assert (
        start
        <= datetime.fromisoformat(stop["arrival"])
        < datetime.fromisoformat(stop["departure"])
        <= end
    )


def test_unverified_clients_cannot_request_or_read_routing(workspace):
    c, _, db = workspace
    for path in ["/api/routes/provider-status", "/api/routes/plans"]:
        assert c["admin"].get(path, headers={"X-Dev-Access-Token": ""}).status_code == 401
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(RoutingPlan)) == 0


def test_past_plan_does_not_override_a_new_legacy_assignment_sequence(workspace):
    c, ids, _ = workspace
    plan, orders, _ = preview(workspace, count=1)
    saved = commit(c, plan)
    old = save(c["admin"].get("/api/orders/" + orders[0]["id"]))
    save(
        c["admin"].post(
            "/api/orders/" + old["id"] + "/unassign", json={"expected_version": old["version"]}
        )
    )
    other = manual(workspace)
    for identifier in [other["id"], old["id"]]:
        order = save(c["admin"].get("/api/orders/" + identifier))
        save(
            c["admin"].post(
                "/api/orders/" + identifier + "/prepare-assignment",
                json={
                    "request_id": str(uuid4()),
                    "expected_version": order["version"],
                    "route_id": saved["routes"][str(ids["rider"])],
                    "acknowledge_unverified_location": True,
                },
            )
        )
    queue = save(c["rider"].get(f"/api/riders/{ids['rider']}/queue"))
    assert [o["order_id"] for o in queue["items"]] == [other["id"], old["id"]]
