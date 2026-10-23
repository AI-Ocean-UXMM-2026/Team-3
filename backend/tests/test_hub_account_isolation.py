"""Hub accounts own independent workspaces, including direct API access."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import User, utcnow
from app.db.rider_models import DeliveryAssignment, RiderProfile
from app.db.session import Database
from app.db.workflow_models import WorkflowRoute
from app.domain.lifecycle import OrderStatus, UserRole
from app.main import create_app
from app.services.buyer_confirmation import YANGON


@pytest.fixture
def hubs(tmp_path, monkeypatch):
    db = Database(f"sqlite+pysqlite:///{tmp_path / 'hubs.sqlite3'}")
    upgrade_database(db)
    ids = {name: uuid4() for name in ("a", "b", "rider", "merchant")}
    with db.sessions.begin() as session:
        for name, role in (
            ("a", UserRole.DISPATCHER),
            ("b", UserRole.ADMIN),
            ("rider", UserRole.RIDER),
            ("merchant", UserRole.MERCHANT),
        ):
            session.add(User(id=ids[name], name=name, email=f"{name}@example.test", role=role))
        session.flush()
        session.add(RiderProfile(id=ids["rider"], operational_status="AVAILABLE"))
    monkeypatch.setattr("app.core.supabase_auth.verify_user", lambda settings, token, request=None: ids[token])
    settings = Settings(
        _env_file=None,
        environment="test",
        order_management_enabled=True,
        supabase_auth_enabled=True,
        supabase_url="https://auth.example.test",
        supabase_publishable_key="sb_publishable_test",
    )
    with TestClient(create_app(settings, database=db)) as client:
        yield client, ids, db
    db.dispose()


def headers(account):
    return {"Authorization": f"Bearer {account}"}


def create(client, account, **extra):
    response = client.post(
        "/api/orders",
        headers=headers(account),
        json={
            "structured": {
                "customer_name": f"Buyer {account}",
                "customer_phone": "09790000000",
                "township": "Hlaing",
                "street": "Test street",
                "cod_amount": "0",
            },
            "parcel": {
                "item": "Test parcel",
                "delivery_day": utcnow().astimezone(YANGON).date().isoformat(),
            },
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_hub_boards_and_search_are_separate(hubs):
    client, _, _ = hubs
    a, b = create(client, "a"), create(client, "b")
    for account, own in (("a", a), ("b", b)):
        result = client.get("/api/orders?page_size=1", headers=headers(account)).json()
        assert result["total"] == 1
        assert [row["id"] for row in result["items"]] == [own["id"]]
        other = "b" if account == "a" else "a"
        result = client.get(f"/api/orders?q=Buyer%20{other}", headers=headers(account)).json()
        assert result["total"] == 0


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "", None),
        ("get", "/events", None),
        ("patch", "", {"expected_version": 1, "street": "Changed"}),
        ("patch", "/status", {"expected_version": 1, "status": "NEEDS_REVIEW"}),
        ("post", "/operations", {"expected_version": 1, "action": "REMOVE_FROM_BOARD"}),
        ("post", "/confirmation-link", None),
        ("get", "/buyer-requests", None),
        ("get", "/assignments", None),
        ("post", "/auto-assignment", {"expected_version": 1, "request_id": str(uuid4())}),
    ],
)
def test_other_hub_cannot_access_order(hubs, method, path, body):
    client, _, _ = hubs
    own = create(client, "a")
    response = client.request(
        method, f"/api/orders/{own['id']}{path}", headers=headers("b"), json=body
    )
    assert response.status_code == 404, response.text
    assert client.get(f"/api/orders/{own['id']}", headers=headers("a")).json()["version"] == 1


def test_delegated_merchant_orders_belong_to_creating_hub(hubs):
    client, ids, _ = hubs
    own = create(client, "a", merchant_id=str(ids["merchant"]))
    assert client.get("/api/orders", headers=headers("a")).json()["total"] == 1
    assert client.get("/api/orders", headers=headers("b")).json()["total"] == 0
    assert client.get(f"/api/orders/{own['id']}", headers=headers("merchant")).status_code == 200


def test_routes_are_owned_even_before_parcels_are_attached(hubs):
    client, ids, _ = hubs
    route = client.post(
        "/api/routes",
        headers=headers("a"),
        json={
            "rider_id": str(ids["rider"]),
            "day": utcnow().astimezone(YANGON).date().isoformat(),
        },
    )
    assert route.status_code == 201, route.text
    assert client.get("/api/routes", headers=headers("a")).json()["total"] == 1
    assert client.get("/api/routes", headers=headers("b")).json()["total"] == 0
    result = client.post(
        f"/api/routes/{route.json()['id']}/actions",
        headers=headers("b"),
        json={
            "expected_version": 1,
            "request_id": str(uuid4()),
            "action": "DISPATCH",
        },
    )
    assert result.status_code == 404, result.text


def test_other_hub_cannot_assign_or_act_on_a_riders_order(hubs):
    client, ids, _ = hubs
    own = create(client, "a")
    for method, path, body in [
        (
            "post",
            f"/api/orders/{own['id']}/assign",
            {"rider_id": str(ids["rider"]), "expected_version": 1},
        ),
        (
            "patch",
            f"/api/riders/{ids['rider']}/deliveries/{own['id']}/status",
            {"expected_version": 1, "request_id": str(uuid4()), "action": "START"},
        ),
    ]:
        result = client.request(method, path, headers=headers("b"), json=body)
        assert result.status_code == 404, result.text


def test_existing_routes_and_rider_queues_do_not_leak_orders(hubs):
    client, ids, db = hubs
    own = create(client, "a")
    # Model a pre-fix route without an ownership marker, already assigned to a rider.
    route_id = uuid4()
    with db.sessions.begin() as session:
        from app.db.models import Order

        order = session.get(Order, UUID(own["id"]))
        order.status = OrderStatus.ASSIGNED
        session.add(
            WorkflowRoute(
                id=route_id,
                rider_id=ids["rider"],
                data={
                    "day": utcnow().astimezone(YANGON).date().isoformat(),
                    "state": "draft",
                    "order_ids": [own["id"]],
                    "handover": None,
                    "events": [],
                    "operations": {},
                },
            )
        )
        session.add(
            DeliveryAssignment(
                id=uuid4(),
                order_id=order.id,
                rider_id=ids["rider"],
                dispatcher_id=ids["a"],
                status="ACTIVE",
            )
        )
    assert client.get("/api/routes", headers=headers("a")).json()["total"] == 1
    assert client.get("/api/routes", headers=headers("b")).json()["total"] == 0
    assert client.get("/api/routes", headers=headers("rider")).json()["total"] == 1
    for account, expected in (("a", 1), ("b", 0), ("rider", 1)):
        result = client.get(f"/api/riders/{ids['rider']}/queue", headers=headers(account))
        assert result.status_code == 200, result.text
        assert len(result.json()["items"]) == expected
    with db.sessions.begin() as session:
        from app.services.workflow import route_row

        route = route_row(session, route_id, session.get(User, ids["a"]), lock=True)
        route.data = {**route.data, "order_ids": []}
    assert client.get("/api/routes", headers=headers("a")).json()["total"] == 1
    assert client.get("/api/routes", headers=headers("b")).json()["total"] == 0


def test_historical_preview_with_foreign_orders_is_withheld(hubs):
    from app.db.routing_models import RoutingPlan

    client, ids, db = hubs
    foreign, own = create(client, "a"), create(client, "b")
    now = utcnow()
    response = client.post(
        "/api/routes/optimize",
        headers=headers("b"),
        json={
            "origin": {"latitude": 16.8, "longitude": 96.1},
            "orders": [{"order_id": own["id"]}],
            "riders": [{"rider_id": str(ids["rider"])}],
            "operating_window": {
                "start": now.isoformat(),
                "end": (now + timedelta(hours=2)).isoformat(),
            },
            "allow_simulation": True,
            "solver_seconds": 1,
        },
    )
    assert response.status_code == 201, response.text
    plan_id = response.json()["id"]
    assert client.get("/api/routes/plans", headers=headers("b")).json()["total"] == 1
    assert client.get("/api/routes/plans", headers=headers("a")).json()["total"] == 0
    assert client.get(f"/api/routes/plans/{plan_id}", headers=headers("a")).status_code == 404
    with db.sessions.begin() as session:
        plan = session.get(RoutingPlan, UUID(plan_id))
        import json

        # Simulate a preview persisted before account isolation was implemented.
        plan.data = json.loads(json.dumps(plan.data).replace(own["id"], foreign["id"]))
    assert client.get("/api/routes/plans", headers=headers("b")).json()["total"] == 0
    assert client.get(f"/api/routes/plans/{plan_id}", headers=headers("b")).status_code == 404
    response = client.post(
        f"/api/routes/plans/{plan_id}/commit",
        headers=headers("b"),
        json={
            "expected_version": 1,
            "allow_simulation": True,
            "acknowledge_unverified_location": True,
        },
    )
    assert response.status_code == 404, response.text


def test_background_allocation_rechecks_owning_hub_before_retry(hubs):
    from app.db.models import Order
    from app.services.automatic_assignment import attempt

    client, ids, db = hubs
    own = create(client, "a")
    with db.sessions() as session:
        order = session.get(Order, UUID(own["id"]))
        old_allocation = SimpleNamespace(
            dispatcher_id=ids["b"],
            buyer_response_id=uuid4(),
            cycle=1,
            status="WAITING_FOR_RIDER",
            reason="Waiting",
        )
        result = attempt(
            session,
            order,
            old_allocation,
            SimpleNamespace(id=None),
            client.app.state.settings,
            client.app.state.location_catalog,
        )
        assert result is None
        assert old_allocation.status == "CANCELLED"
        assert "owning hub" in old_allocation.reason
        assert session.query(WorkflowRoute).count() == 0
