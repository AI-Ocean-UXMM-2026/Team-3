from contextlib import ExitStack
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import User, utcnow
from app.db.rider_models import RiderProfile
from app.db.session import Database
from app.domain.lifecycle import UserRole
from app.main import create_app
from app.services.buyer_confirmation import YANGON

SECRET = "three-role-local-only-" + "x" * 40


@pytest.fixture
def workspace(tmp_path):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'workflow.sqlite3'}")
    upgrade_database(database)
    ids = {key: uuid4() for key in ("admin", "rider", "other")}
    with database.sessions.begin() as session:
        for key, identifier in ids.items():
            session.add(
                User(
                    id=identifier,
                    name=key,
                    email=f"{key}@example.test",
                    role=UserRole.ADMIN if key == "admin" else UserRole.RIDER,
                )
            )
        session.flush()
        for key in ("rider", "other"):
            session.add(RiderProfile(id=ids[key], operational_status="AVAILABLE"))
    with ExitStack() as stack:
        clients = {}
        for key in ids:
            settings = Settings(
                _env_file=None,
                environment="test",
                order_management_enabled=True,
                dev_actor_id=ids[key],
                dev_access_token=SECRET,
                serve_workspace=True,
            )
            clients[key] = stack.enter_context(
                TestClient(
                    create_app(settings, database=database),
                    client=("127.0.0.1", 50000),
                    headers={"X-Dev-Access-Token": SECRET},
                )
            )
        yield clients, ids, database
    database.dispose()


def save(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def day():
    return utcnow().astimezone(YANGON).date().isoformat()


def manual(workspace, received=True, amount="25000", coordinates=True):
    c, ids, db = workspace
    structured = {
        "customer_name": "Test buyer",
        "customer_phone": "09791234567",
        "township": "Kamaryut",
        "street": "Hledan Road",
        "cod_amount": amount,
        "delivery_time_window": "Any time",
    }
    if coordinates:
        structured.update(latitude="16.8254000", longitude="96.1309000")
    return save(
        c["admin"].post(
            "/api/orders",
            json={
                "structured": structured,
                "parcel": {
                    "item": "Envelope",
                    "reference": "LOCAL-TEST",
                    "delivery_day": day(),
                    "hub_received": received,
                },
            },
        ),
        201,
    )


def status(client, order, target):
    return save(
        client.patch(
            f"/api/orders/{order['id']}/status",
            json={
                "expected_version": order["version"],
                "status": target,
                "acknowledge_unverified_location": True,
            },
        )
    )


def assign(workspace, order):
    c, ids, db = workspace
    for target in ("NEEDS_REVIEW", "CONFIRMED", "READY_FOR_DISPATCH"):
        if order["status"] != target:
            order = status(c["admin"], order, target)
    route = save(
        c["admin"].post("/api/routes", json={"rider_id": str(ids["rider"]), "day": day()}), 201
    )
    save(
        c["admin"].post(
            f"/api/orders/{order['id']}/assign",
            json={
                "expected_version": order["version"],
                "rider_id": str(ids["rider"]),
                "route_id": route["id"],
            },
        ),
        201,
    )
    route = save(c["admin"].get("/api/routes"))["items"][0]
    return route


def action(client, route, kind, **extra):
    return client.post(
        f"/api/routes/{route['id']}/actions",
        json={
            "request_id": str(uuid4()),
            "expected_version": route["version"],
            "action": kind,
            **extra,
        },
    )


def departed(workspace, amount="25000"):
    order = manual(workspace, amount=amount)
    route = assign(workspace, order)
    route = save(action(workspace[0]["admin"], route, "DISPATCH"))
    queue = save(workspace[0]["rider"].get(f"/api/riders/{workspace[1]['rider']}/queue"))
    return route, queue["items"][0]


def deliver(workspace, stop, actual=25000, reason=None):
    return workspace[0]["rider"].patch(
        f"/api/riders/{workspace[1]['rider']}/deliveries/{stop['order_id']}/status",
        json={
            "request_id": str(uuid4()),
            "expected_version": stop["order_version"],
            "action": "DELIVERED",
            "cod_collected": True,
            "actual_amount": actual,
            "difference_reason": reason,
        },
    )


def test_full_manual_customer_review_rider_and_short_cash_closeout(workspace):
    c, ids, db = workspace
    order = manual(workspace, coordinates=False)
    assert order["merchant_id"] == str(ids["admin"])
    with db.sessions() as session:
        assert not session.scalar(select(User).where(User.role == UserRole.MERCHANT))
    order = status(c["admin"], order, "NEEDS_REVIEW")
    link = save(c["admin"].post(f"/api/orders/{order['id']}/confirmation-link"), 201)
    token = link["confirmation_url"].rsplit("/", 1)[1]
    public = save(c["admin"].get(f"/api/confirm/{token}"))
    assert "customer_phone" not in public and "latitude" not in public
    auth = save(c["admin"].post(f"/api/confirm/{token}/verify", json={"last_four": "4567"}))
    bearer = {"Authorization": f"Bearer {auth['access_token']}"}
    result = save(
        c["admin"].patch(
            f"/api/confirm/{token}/location",
            headers=bearer,
            json={
                "request_id": str(uuid4()),
                "latitude": "16.8254000",
                "longitude": "96.1309000",
                "initial_pin_acknowledged": True,
            },
        )
    )
    assert result["decision"] == "REVIEW_REQUIRED"
    save(
        c["admin"].patch(
            f"/api/confirm/{token}/response",
            headers=bearer,
            json={"request_id": str(uuid4()), "action": "AVAILABLE", "instructions": "Ring bell"},
        )
    )
    requests = save(c["admin"].get(f"/api/orders/{order['id']}/buyer-requests"))["items"]
    for request in requests:
        if request["decision"] == "REVIEW_REQUIRED":
            latest = save(c["admin"].get(f"/api/orders/{order['id']}"))
            save(
                c["admin"].patch(
                    f"/api/orders/{order['id']}/buyer-requests/{request['id']}",
                    json={
                        "expected_version": latest["version"],
                        "decision": "APPROVE",
                        "reason": "Reviewed customer point and receiving instructions",
                    },
                )
            )
    order = save(c["admin"].get(f"/api/orders/{order['id']}"))
    # The order is already in NEEDS_REVIEW after reviewing customer requests.
    order = status(c["admin"], order, "CONFIRMED")
    order = status(c["admin"], order, "READY_FOR_DISPATCH")
    route = save(
        c["admin"].post("/api/routes", json={"rider_id": str(ids["rider"]), "day": day()}), 201
    )
    save(
        c["admin"].post(
            f"/api/orders/{order['id']}/assign",
            json={
                "expected_version": order["version"],
                "rider_id": str(ids["rider"]),
                "route_id": route["id"],
            },
        ),
        201,
    )
    route = save(c["admin"].get("/api/routes"))["items"][0]
    route = save(action(c["admin"], route, "DISPATCH"))
    stop = save(c["rider"].get(f"/api/riders/{ids['rider']}/queue"))["items"][0]
    save(deliver(workspace, stop))
    route = save(action(c["rider"], route, "HANDOVER", amount=25000, recorded_total=25000))
    assert route["handover"]["status"] == "submitted" and route["state"] == "closing"
    route = save(action(c["admin"], route, "RECEIVE_CLOSE", amount=25000))
    assert route["state"] == "closed" and route["receipt_history"][0]["amount"] == 25000
    assert save(c["admin"].get(f"/api/orders/{order['id']}"))["status"] == "DELIVERED"
    assert save(c["admin"].get(f"/api/confirm/{token}"))["state"] == "VIEW_ONLY"


def test_route_assignment_requires_hub_receipt_and_rolls_back(workspace):
    c, ids, db = workspace
    order = manual(workspace, received=False)
    for target in ("NEEDS_REVIEW", "CONFIRMED", "READY_FOR_DISPATCH"):
        order = status(c["admin"], order, target)
    route = save(
        c["admin"].post("/api/routes", json={"rider_id": str(ids["rider"]), "day": day()}), 201
    )
    response = c["admin"].post(
        f"/api/orders/{order['id']}/assign",
        json={
            "expected_version": order["version"],
            "rider_id": str(ids["rider"]),
            "route_id": route["id"],
        },
    )
    assert response.status_code == 409
    assert save(c["admin"].get(f"/api/orders/{order['id']}"))["status"] == "READY_FOR_DISPATCH"
    assert not save(c["admin"].get("/api/routes"))["items"][0]["items"]


def test_cash_difference_cannot_silently_close_and_original_amount_is_preserved(workspace):
    c, ids, db = workspace
    route, stop = departed(workspace)
    assert deliver(workspace, stop, 24000).status_code == 422
    save(deliver(workspace, stop, 24000, "Customer paid short"))
    route = save(action(c["rider"], route, "HANDOVER", amount=24000, recorded_total=24000))
    route = save(action(c["admin"], route, "RECEIVE_CLOSE", amount=24000))
    assert route["state"] == "closing" and route["handover"]["status"] == "received"
    assert action(c["admin"], route, "CLOSE").status_code == 409
    order = save(c["admin"].get(f"/api/orders/{stop['order_id']}"))
    order = save(
        c["admin"].post(
            f"/api/orders/{order['id']}/operations",
            json={
                "expected_version": order["version"],
                "action": "RESOLVE_DIFFERENCE",
                "reason": "Admin accepted documented short payment",
            },
        )
    )
    assert order["parsing_metadata"]["parcel"]["collection"]["actual"] == 24000
    assert save(action(c["admin"], route, "CLOSE"))["state"] == "closed"


def test_handover_requires_return_receipt_and_zero_cash_closes(workspace):
    c, ids, db = workspace
    route, stop = departed(workspace, amount="0")
    save(
        c["rider"].patch(
            f"/api/riders/{ids['rider']}/deliveries/{stop['order_id']}/status",
            json={
                "request_id": str(uuid4()),
                "expected_version": stop["order_version"],
                "action": "FAILED",
                "failure_reason": "CUSTOMER_UNAVAILABLE",
            },
        )
    )
    assert action(c["rider"], route, "HANDOVER", amount=0, recorded_total=0).status_code == 409
    order = save(c["admin"].get(f"/api/orders/{stop['order_id']}"))
    save(
        c["admin"].post(
            f"/api/orders/{order['id']}/operations",
            json={"expected_version": order["version"], "action": "RETURN_RECEIVED"},
        )
    )
    route = save(action(c["rider"], route, "HANDOVER", amount=0, recorded_total=0))
    assert save(action(c["admin"], route, "RECEIVE_CLOSE", amount=0))["state"] == "closed"


def test_role_scope_stale_versions_replay_and_physical_receipt_are_enforced(workspace):
    c, ids, db = workspace
    route, stop = departed(workspace)
    assert not save(c["other"].get("/api/routes"))["items"]
    assert action(c["other"], route, "HANDOVER", amount=0, recorded_total=0).status_code == 404
    assert action(c["rider"], route, "RECEIVE_CLOSE", amount=0).status_code == 403
    assert c["rider"].get(f"/api/orders/{stop['order_id']}").status_code == 403
    assert (
        action(c["rider"], route, "HANDOVER", amount=25000, recorded_total=25000).status_code == 409
    )
    save(deliver(workspace, stop))
    route = save(action(c["rider"], route, "HANDOVER", amount=25000, recorded_total=25000))
    assert action(c["admin"], route, "RECEIVE_CLOSE").status_code == 422
    body = {
        "request_id": str(uuid4()),
        "expected_version": route["version"],
        "action": "RECEIVE_CLOSE",
        "amount": 25000,
    }
    closed = save(c["admin"].post(f"/api/routes/{route['id']}/actions", json=body))
    repeated = save(c["admin"].post(f"/api/routes/{route['id']}/actions", json=body))
    assert closed == repeated and len(repeated["receipt_history"]) == 1
    assert (
        c["admin"]
        .post(f"/api/routes/{route['id']}/actions", json={**body, "amount": 24000})
        .status_code
        == 409
    )


def test_frontend_allowlist_and_production_gate(workspace):
    from app.db.session import BACKEND_ROOT
    from tools.backend_test_dashboard.server import create_dashboard

    app = create_dashboard(frontend=BACKEND_ROOT.parent / "frontend")
    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)) as client:
        assert client.get("/").status_code == 200
        assert (
            client.get("/dev/api-workspace.mjs")
            .headers["content-type"]
            .startswith("text/javascript")
        )
        assert client.get("/vendor/lannpya-order-parser.js").status_code == 200
        for path in (
            "/order-parser/package.json",
            "/data/workspace_access.json",
            "/.env",
            "/app/main.py",
        ):
            assert client.get(path).status_code == 404
    core = create_app(
        Settings(_env_file=None, environment="production", order_management_enabled=True)
    )
    with TestClient(core) as client:
        assert client.get("/api/routes").status_code == 503
        assert client.get("/api.html").status_code == 404


def test_approved_customer_reschedule_updates_route_day_and_enforces_window(workspace):
    c, ids, db = workspace
    order = manual(workspace)
    order = status(c["admin"], order, "NEEDS_REVIEW")
    link = save(c["admin"].post(f"/api/orders/{order['id']}/confirmation-link"), 201)
    token = link["confirmation_url"].rsplit("/", 1)[1]
    auth = save(c["admin"].post(f"/api/confirm/{token}/verify", json={"last_four": "4567"}))
    tomorrow = (utcnow().astimezone(YANGON) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    result = save(
        c["admin"].patch(
            f"/api/confirm/{token}/response",
            headers={"Authorization": "Bearer " + auth["access_token"]},
            json={
                "request_id": str(uuid4()),
                "action": "RESCHEDULE",
                "time_window": {
                    "start": tomorrow.isoformat(),
                    "end": (tomorrow + timedelta(hours=2)).isoformat(),
                },
            },
        )
    )
    assert result["decision"] == "REVIEW_REQUIRED"
    request = save(c["admin"].get(f"/api/orders/{order['id']}/buyer-requests"))["items"][0]
    latest = save(c["admin"].get(f"/api/orders/{order['id']}"))
    save(
        c["admin"].patch(
            f"/api/orders/{order['id']}/buyer-requests/{request['id']}",
            json={
                "expected_version": latest["version"],
                "decision": "APPROVE",
                "reason": "Reviewed requested future delivery slot",
            },
        )
    )
    latest = save(c["admin"].get(f"/api/orders/{order['id']}"))
    assert latest["parsing_metadata"]["parcel"]["delivery_day"] == tomorrow.date().isoformat()
    from app.db.models import Order
    from app.services.workflow import delivery_window

    with db.sessions() as session:
        start, end = delivery_window(session.get(Order, UUID(order["id"])))
        assert start == tomorrow and end == tomorrow + timedelta(hours=2)


def test_legacy_status_and_assignment_cannot_bypass_workspace_route_or_custody(workspace):
    c, ids, db = workspace
    order = manual(workspace)
    for target in ("NEEDS_REVIEW", "CONFIRMED", "READY_FOR_DISPATCH"):
        order = status(c["admin"], order, target)
    assert (
        c["admin"]
        .post(
            f"/api/orders/{order['id']}/assign",
            json={"expected_version": order["version"], "rider_id": str(ids["rider"])},
        )
        .status_code
        == 422
    )
    assert (
        c["admin"]
        .patch(
            f"/api/orders/{order['id']}/status",
            json={"expected_version": order["version"], "status": "ASSIGNED"},
        )
        .status_code
        == 409
    )


def preparation(workspace, order, **extra):
    return {
        "request_id": str(uuid4()),
        "expected_version": order["version"],
        "rider_id": str(workspace[1]["rider"]),
        "acknowledge_unverified_location": True,
        **extra,
    }


def test_prepare_assign_atomic_short_path_and_idempotent_retry(workspace):
    c, ids, db = workspace
    order = manual(workspace, received=False)
    body = preparation(workspace, order, receive_at_hub=True)
    path = f"/api/orders/{order['id']}/prepare-assignment"
    prepared = save(c["admin"].post(path, json=body))
    assert prepared["order"]["status"] == "ASSIGNED"
    assert prepared["order"]["parsing_metadata"]["parcel"]["hub_received_at"]
    assert prepared["route"]["state"] == "draft"
    assert len(prepared["route"]["items"]) == 1
    assert save(c["admin"].post(path, json=body)) == prepared
    assert save(c["admin"].get("/api/routes"))["total"] == 1
    assert c["admin"].post(path, json={**body, "request_id": str(uuid4())}).status_code == 409
    assert c["admin"].post(path, json={**body, "receive_at_hub": False}).status_code == 409
    route = save(action(c["admin"], prepared["route"], "DISPATCH"))
    stop = save(c["rider"].get(f"/api/riders/{ids['rider']}/queue"))["items"][0]
    save(deliver(workspace, stop))
    route = save(action(c["rider"], route, "HANDOVER", amount=25000, recorded_total=25000))
    assert save(action(c["admin"], route, "RECEIVE_CLOSE", amount=25000))["state"] == "closed"


def test_prepare_existing_route_appends_and_does_not_auto_dispatch(workspace):
    c, ids, db = workspace
    first = manual(workspace)
    result = save(
        c["admin"].post(
            f"/api/orders/{first['id']}/prepare-assignment", json=preparation(workspace, first)
        )
    )
    second = manual(workspace)
    body = preparation(workspace, second, route_id=result["route"]["id"])
    body.pop("rider_id")
    result = save(c["admin"].post(f"/api/orders/{second['id']}/prepare-assignment", json=body))
    assert len(result["route"]["items"]) == 2
    assert result["assignment"]["stop_sequence"] == 2
    assert result["route"]["state"] == "draft"
    assert save(c["admin"].get("/api/routes"))["total"] == 1


@pytest.mark.parametrize(
    "problem", ["receipt", "ack", "location", "stale", "rider", "day", "pending", "incident"]
)
def test_prepare_failure_rolls_back_receipt_status_and_route(workspace, problem):
    from app.db.models import Order

    c, ids, db = workspace
    order = manual(workspace, received=False, coordinates=problem != "location")
    body = preparation(workspace, order, receive_at_hub=problem != "receipt")
    if problem == "ack":
        body["acknowledge_unverified_location"] = False
    if problem == "stale":
        body["expected_version"] += 5
    with db.sessions.begin() as session:
        stored = session.get(Order, UUID(order["id"]))
        if problem == "rider":
            session.get(RiderProfile, ids["rider"]).operational_status = "OFFLINE"
        if problem in {"day", "incident"}:
            context = dict(stored.parsing_metadata["parcel"])
            if problem == "day":
                context["delivery_day"] = (
                    utcnow().astimezone(YANGON).date() - timedelta(days=1)
                ).isoformat()
            else:
                context["incident"] = "Parcel damaged"
            stored.parsing_metadata = {**stored.parsing_metadata, "parcel": context}
    if problem == "pending":
        order = status(c["admin"], order, "NEEDS_REVIEW")
        link = save(c["admin"].post(f"/api/orders/{order['id']}/confirmation-link"), 201)
        token = link["confirmation_url"].rsplit("/", 1)[1]
        auth = save(c["admin"].post(f"/api/confirm/{token}/verify", json={"last_four": "4567"}))
        save(
            c["admin"].patch(
                f"/api/confirm/{token}/location",
                headers={"Authorization": "Bearer " + auth["access_token"]},
                json={
                    "request_id": str(uuid4()),
                    "latitude": "16.8254000",
                    "longitude": "96.1309000",
                    "initial_pin_acknowledged": True,
                },
            )
        )
    order = save(c["admin"].get(f"/api/orders/{order['id']}"))
    if problem != "stale":
        body["expected_version"] = order["version"]
    rejected = c["admin"].post(f"/api/orders/{order['id']}/prepare-assignment", json=body)
    assert rejected.status_code in {409, 422}, rejected.text
    latest = save(c["admin"].get(f"/api/orders/{order['id']}"))
    assert latest["version"] == order["version"]
    assert latest["status"] == order["status"]
    assert not latest["parsing_metadata"]["parcel"].get("hub_received_at")
    assert not save(c["admin"].get("/api/routes"))["items"]
    assert not save(c["rider"].get(f"/api/riders/{ids['rider']}/queue"))["items"]


def test_prepare_checks_role_route_choice_and_day(workspace):
    c, ids, db = workspace
    order = manual(workspace)
    path = f"/api/orders/{order['id']}/prepare-assignment"
    body = preparation(workspace, order)
    assert c["rider"].post(path, json=body).status_code == 403
    route = save(
        c["admin"].post(
            "/api/routes",
            json={
                "rider_id": str(ids["rider"]),
                "day": (utcnow().astimezone(YANGON).date() + timedelta(days=1)).isoformat(),
            },
        ),
        201,
    )
    assert c["admin"].post(path, json={**body, "route_id": route["id"]}).status_code == 422
    body.pop("rider_id")
    assert c["admin"].post(path, json=body).status_code == 422
    rejected = c["admin"].post(path, json={**body, "route_id": route["id"]})
    assert rejected.status_code == 409
    assert save(c["admin"].get(f"/api/orders/{order['id']}"))["status"] == "DRAFT"
    assert not save(c["admin"].get("/api/routes"))["items"][0]["items"]


def test_prepare_future_parcel_is_plannable_but_not_departable_today(workspace):
    from app.db.models import Order

    c, ids, db = workspace
    order = manual(workspace)
    tomorrow = (utcnow().astimezone(YANGON).date() + timedelta(days=1)).isoformat()
    with db.sessions.begin() as session:
        stored = session.get(Order, UUID(order["id"]))
        context = {**stored.parsing_metadata["parcel"], "delivery_day": tomorrow}
        stored.parsing_metadata = {**stored.parsing_metadata, "parcel": context}
    order = save(c["admin"].get(f"/api/orders/{order['id']}"))
    result = save(
        c["admin"].post(
            f"/api/orders/{order['id']}/prepare-assignment", json=preparation(workspace, order)
        )
    )
    assert result["route"]["day"] == tomorrow
    assert action(c["admin"], result["route"], "DISPATCH").status_code == 409
    assert save(c["admin"].get(f"/api/orders/{order['id']}"))["status"] == "ASSIGNED"
