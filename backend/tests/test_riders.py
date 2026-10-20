from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.rider_models import DeliveryAssignment, RiderActionReceipt, RiderProfile
from app.db.session import Database
from app.domain.lifecycle import UserRole
from app.main import create_app
from app.services.riders import RiderService

SECRET = "rider-test-local-only-secret-" + "x" * 32
HEADERS = {"X-Dev-Access-Token": SECRET}


@pytest.fixture
def env(tmp_path):
    db = Database(f"sqlite+pysqlite:///{tmp_path / 'riders.sqlite3'}")
    upgrade_database(db)
    dispatcher, merchant = uuid4(), uuid4()
    with db.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=dispatcher,
                    name="Dispatcher",
                    email="dispatch@example.test",
                    role=UserRole.DISPATCHER,
                ),
                User(
                    id=merchant,
                    name="Merchant",
                    email="merchant@example.test",
                    role=UserRole.MERCHANT,
                ),
            ]
        )
    settings = Settings(
        _env_file=None,
        environment="test",
        order_management_enabled=True,
        dev_access_token=SECRET,
        dev_actor_id=dispatcher,
    )
    app = create_app(settings, database=db)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield {
            "db": db,
            "client": client,
            "settings": settings,
            "app": app,
            "dispatcher": dispatcher,
            "merchant": merchant,
        }
    db.dispose()


def rider(env, name="Rider", **body):
    response = env["client"].post(
        "/api/riders",
        headers=HEADERS,
        json={"name": name, "operational_status": "AVAILABLE", **body},
    )
    assert response.status_code == 201, response.text
    return response.json()


def order(env, **structured):
    response = env["client"].post(
        "/api/orders",
        headers=HEADERS,
        json={
            "merchant_id": str(env["merchant"]),
            "structured": {
                "customer_name": "Buyer",
                "customer_phone": "09791234567",
                "township": "Hlaing",
                "street": "Baho Road",
                "landmark": "ဗဟိုလမ်းနား",
                "cod_amount": "25000",
                **structured,
            },
        },
    )
    assert response.status_code == 201, response.text
    row = response.json()
    for target in ("NEEDS_REVIEW", "CONFIRMED", "READY_FOR_DISPATCH"):
        response = env["client"].patch(
            f"/api/orders/{row['id']}/status",
            headers=HEADERS,
            json={
                "status": target,
                "expected_version": row["version"],
                "acknowledge_unverified_location": True,
            },
        )
        assert response.status_code == 200, response.text
        row = response.json()
    return row


def assign(env, row, who, sequence=None):
    response = env["client"].post(
        f"/api/orders/{row['id']}/assign",
        headers=HEADERS,
        json={"rider_id": who["id"], "expected_version": row["version"], "stop_sequence": sequence},
    )
    assert response.status_code == 201, response.text
    return response.json()


def saved(env, order_id):
    with env["db"].sessions() as session:
        row = session.get(Order, UUID(str(order_id)))
        return {"id": str(row.id), "version": row.version, "status": row.status.value}


def act(env, who, row, action, **body):
    return env["client"].patch(
        f"/api/riders/{who['id']}/deliveries/{row['id']}/status",
        headers=HEADERS,
        json={
            "request_id": str(uuid4()),
            "expected_version": row["version"],
            "action": action,
            **body,
        },
    )


def queue(env, who, **params):
    response = env["client"].get(f"/api/riders/{who['id']}/queue", headers=HEADERS, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_rider_profiles_reuse_users_and_optional_contact(env):
    who = rider(env)
    assert who["email"] is None and who["contact_phone"] is None
    with env["db"].sessions() as session:
        assert session.get(User, UUID(who["id"])).role == UserRole.RIDER
        assert session.get(RiderProfile, UUID(who["id"])) is not None
        assert session.scalar(select(func.count()).select_from(User)) == 3
    contact = rider(env, "Second", email="Rider@example.test", contact_phone="၀၉၇၉၁၂၃၄၅၆၇")
    assert contact["email"] == "rider@example.test" and contact["contact_phone"] == "09791234567"
    listing = env["client"].get("/api/riders", headers=HEADERS, params={"page_size": 1}).json()
    assert len(listing["items"]) == 1 and listing["total"] == 2
    detail = env["client"].get(f"/api/riders/{who['id']}", headers=HEADERS)
    assert detail.json()["name"] == "Rider" and detail.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": " "},
        {"name": "x" * 201},
        {"name": 1},
        {"name": "X", "email": "bad"},
        {"name": "X", "contact_phone": "1234"},
        {"name": "X", "role": "Admin"},
        {"name": "X", "operational_status": "BUSY"},
        {"name": "X", "email": "fake@riders.invalid"},
    ],
)
def test_rider_invalid_requests(env, body):
    response = env["client"].post("/api/riders", headers=HEADERS, json=body)
    assert response.status_code == 422


def test_duplicate_email_rollback_no_orphan_profile(env):
    rider(env, email="same@example.test")
    assert (
        env["client"]
        .post("/api/riders", headers=HEADERS, json={"name": "Other", "email": "same@example.test"})
        .status_code
        == 409
    )
    with env["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(RiderProfile)) == 1


def test_availability_and_versions(env):
    who = rider(env)
    response = env["client"].patch(
        f"/api/riders/{who['id']}",
        headers=HEADERS,
        json={"expected_version": who["version"], "operational_status": "ON_BREAK"},
    )
    assert response.status_code == 200 and response.json()["version"] == who["version"] + 1
    assert (
        env["client"]
        .patch(
            f"/api/riders/{who['id']}",
            headers=HEADERS,
            json={"expected_version": who["version"], "operational_status": "OFFLINE"},
        )
        .status_code
        == 409
    )
    listed = (
        env["client"]
        .get("/api/riders", headers=HEADERS, params={"operational_status": "AVAILABLE"})
        .json()
    )
    assert listed["total"] == 0
    row = order(env)
    assert (
        env["client"]
        .post(
            f"/api/orders/{row['id']}/assign",
            headers=HEADERS,
            json={"rider_id": who["id"], "expected_version": row["version"]},
        )
        .status_code
        == 409
    )


def test_assignment_queue_no_fabrication_and_unassign(env):
    who, row = rider(env), order(env)
    result = assign(env, row, who, 3)
    assert result["order_status"] == "ASSIGNED"
    snapshot = queue(env, who)
    item = snapshot["items"][0]
    assert item["stop_sequence"] == 3 and item["status"] == "ASSIGNED"
    assert item["latitude"] is None and item["navigation_url"] is None
    assert item["coordinate_status"] == "MISSING" and not item["navigation_ready"]
    assert (
        item["confidence_level"] == "AMBER"
        and item["location_verification"]["status"] == "unverified"
    )
    assert item["cod_amount"] == "25000" and item["landmark"] == "ဗဟိုလမ်းနား"
    assert "original_message" not in item and "field_sources" not in item
    unchanged = queue(env, who, cursor=snapshot["cursor"])
    assert unchanged["unchanged"] and unchanged["items"] == [] and unchanged["total"] == 1
    response = env["client"].post(
        f"/api/orders/{row['id']}/unassign",
        headers=HEADERS,
        json={"expected_version": result["order_version"]},
    )
    assert response.status_code == 200 and response.json()["assignment"]["status"] == "UNASSIGNED"
    removed = queue(env, who, cursor=snapshot["cursor"])
    assert not removed["unchanged"] and removed["total"] == 0
    second = assign(env, saved(env, row["id"]), who)
    assert second["assignment"]["id"] != result["assignment"]["id"]
    history = env["client"].get(f"/api/orders/{row['id']}/assignments", headers=HEADERS).json()
    assert history["total"] == 2


def test_rider_scope_and_public_denial(env):
    who, other = rider(env), rider(env, "Other")
    row = order(env)
    assign(env, row, other)
    env["settings"].dev_actor_id = UUID(who["id"])
    assert queue(env, who)["total"] == 0
    for suffix in ("", "/queue"):
        assert (
            env["client"].get(f"/api/riders/{other['id']}" + suffix, headers=HEADERS).status_code
            == 404
        )
    assert env["client"].get("/api/riders", headers=HEADERS).json()["total"] == 1
    assert act(env, who, saved(env, row["id"]), "START").status_code == 404
    assert env["client"].get("/api/orders", headers=HEADERS).status_code == 403
    assert (
        env["client"].post("/api/riders", headers=HEADERS, json={"name": "Forbidden"}).status_code
        == 403
    )
    assert env["client"].get(f"/api/riders/{who['id']}/queue").status_code == 401
    assert (
        env["client"]
        .get(f"/api/riders/{who['id']}/queue", headers={"Authorization": "Bearer " + "a" * 43})
        .status_code
        == 401
    )
    env["settings"].dev_actor_id = env["merchant"]
    assert env["client"].get("/api/riders", headers=HEADERS).status_code == 403


def test_rider_self_availability_only(env):
    who, other = rider(env), rider(env, "Other")
    env["settings"].dev_actor_id = UUID(who["id"])
    assert (
        env["client"]
        .patch(
            f"/api/riders/{who['id']}",
            headers=HEADERS,
            json={"expected_version": who["version"], "operational_status": "OFFLINE"},
        )
        .status_code
        == 200
    )
    assert (
        env["client"]
        .patch(
            f"/api/riders/{other['id']}",
            headers=HEADERS,
            json={"expected_version": other["version"], "operational_status": "OFFLINE"},
        )
        .status_code
        == 404
    )
    assert (
        env["client"]
        .patch(
            f"/api/riders/{who['id']}",
            headers=HEADERS,
            json={"expected_version": 2, "operational_status": "OFFLINE", "name": "Spoof"},
        )
        .status_code
        == 422
    )


def test_delivery_cod_idempotence_events_and_view_only_link(env):
    who, row = rider(env), order(env)
    link = env["client"].post(f"/api/orders/{row['id']}/confirmation-link", headers=HEADERS)
    # Generate while CONFIRMED, not READY_FOR_DISPATCH.
    assert link.status_code == 409
    assigned = assign(env, row, who)
    env["settings"].dev_actor_id = UUID(who["id"])
    started = act(env, who, saved(env, row["id"]), "START")
    assert started.status_code == 200 and started.json()["status"] == "OUT_FOR_DELIVERY"
    assert act(env, who, saved(env, row["id"]), "DELIVERED").status_code == 409
    body = {
        "expected_version": started.json()["order_version"],
        "request_id": str(uuid4()),
        "action": "DELIVERED",
        "cod_collected": True,
    }
    url = f"/api/riders/{who['id']}/deliveries/{row['id']}/status"
    delivered = env["client"].patch(url, headers=HEADERS, json=body)
    assert delivered.status_code == 200 and delivered.json()["assignment_status"] == "COMPLETED"
    duplicate = env["client"].patch(url, headers=HEADERS, json=body)
    assert duplicate.json() == delivered.json()
    assert (
        env["client"].patch(url, headers=HEADERS, json={**body, "cod_collected": False}).status_code
        == 409
    )
    assert act(env, who, saved(env, row["id"]), "DELIVERED", cod_collected=True).status_code == 404
    assert queue(env, who)["total"] == 0
    with env["db"].sessions() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(DeliveryEvent.event_type == "DELIVERY_COMPLETED")
            )
            == 1
        )
        event = session.scalar(
            select(DeliveryEvent).where(DeliveryEvent.event_type == "DELIVERY_COMPLETED")
        )
        assert (
            event.event_metadata["actor_id"] == who["id"]
            and event.event_metadata["actor_role"] == "Rider"
        )
        assert event.event_metadata["assignment_id"] == assigned["assignment"]["id"]
        assert session.scalar(select(func.count()).select_from(RiderActionReceipt)) == 2


def test_prepaid_and_disabled_cod_policy(env):
    who = rider(env)
    for amount, disabled in (("0", False), ("25000", True)):
        row = order(env, cod_amount=amount)
        assign(env, row, who)
        env["settings"].rider_require_cod_confirmation = not disabled
        assert act(env, who, saved(env, row["id"]), "START").status_code == 200
        assert act(env, who, saved(env, row["id"]), "DELIVERED").status_code == 200


def test_failure_requires_reason_and_records_private_note(env):
    who, row = rider(env), order(env)
    assign(env, row, who)
    assert act(env, who, saved(env, row["id"]), "START").status_code == 200
    assert act(env, who, saved(env, row["id"]), "FAILED").status_code == 422
    failed = act(
        env,
        who,
        saved(env, row["id"]),
        "FAILED",
        failure_reason="CUSTOMER_UNAVAILABLE",
        failure_note="Sensitive internal follow-up",
    )
    assert failed.status_code == 200 and failed.json()["status"] == "FAILED"
    assert queue(env, who)["total"] == 0
    with env["db"].sessions() as session:
        assignment = session.scalar(select(DeliveryAssignment))
        assert assignment.failure_note == "Sensitive internal follow-up"
        event = session.scalar(
            select(DeliveryEvent).where(DeliveryEvent.event_type == "DELIVERY_FAILED")
        )
        assert "Sensitive internal" not in str(event.event_metadata)


@pytest.mark.parametrize(
    "bad",
    [
        {"action": "DELIVERED", "cod_collected": "true"},
        {"action": "START", "cod_collected": True},
        {"action": "FAILED", "failure_reason": "unknown"},
        {"action": "START", "failure_note": "not permitted"},
        {"action": "FAILED", "failure_reason": "OTHER", "failure_note": " "},
        {"action": "FAILED", "failure_reason": "OTHER", "failure_note": "x" * 501},
        {"action": "START", "expected_version": True},
        {"action": "START", "rider_id": str(uuid4())},
    ],
)
def test_invalid_delivery_requests(env, bad):
    who, row = rider(env), order(env)
    assign(env, row, who)
    body = {"request_id": str(uuid4()), "expected_version": saved(env, row["id"])["version"], **bad}
    assert (
        env["client"]
        .patch(f"/api/riders/{who['id']}/deliveries/{row['id']}/status", headers=HEADERS, json=body)
        .status_code
        == 422
    )


def test_active_assignment_cannot_use_legacy_completion_bypass(env):
    who, row = rider(env), order(env)
    assign(env, row, who)
    current = saved(env, row["id"])
    response = env["client"].patch(
        f"/api/orders/{row['id']}/status",
        headers=HEADERS,
        json={"expected_version": current["version"], "status": "OUT_FOR_DELIVERY"},
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "USE_RIDER_DELIVERY_ACTION"
    )
    assert act(env, who, current, "START").status_code == 200
    response = env["client"].post(
        f"/api/orders/{row['id']}/unassign",
        headers=HEADERS,
        json={"expected_version": saved(env, row["id"])["version"]},
    )
    assert response.status_code == 409


@pytest.mark.parametrize("target", ["READY_FOR_DISPATCH", "CANCELLED"])
def test_generic_status_unassigns_atomically(env, target):
    who, row = rider(env), order(env)
    result = assign(env, row, who)
    before = queue(env, who)
    response = env["client"].patch(
        f"/api/orders/{row['id']}/status",
        headers=HEADERS,
        json={
            "expected_version": result["order_version"],
            "status": target,
            "acknowledge_unverified_location": True,
        },
    )
    assert response.status_code == 200
    assert queue(env, who, cursor=before["cursor"])["total"] == 0
    with env["db"].sessions() as session:
        assignment = session.scalar(select(DeliveryAssignment))
        assert assignment.status == ("CANCELLED" if target == "CANCELLED" else "UNASSIGNED")


def test_navigation_only_confirmed_coords_and_no_sensitive_parameters(env):
    who = rider(env)
    row = order(
        env, latitude="16.8", longitude="96.1", delivery_instructions="Private instructions"
    )
    assign(env, row, who)
    assert not queue(env, who)["items"][0]["navigation_ready"]
    with env["db"].sessions.begin() as session:
        current = session.get(Order, UUID(row["id"]))
        sources = deepcopy(current.field_sources)
        for field in ("latitude", "longitude"):
            sources[field] = {
                "method": "buyer_confirmation",
                "requires_review": False,
                "verified": False,
            }
        current.field_sources = sources
    item = queue(env, who)["items"][0]
    assert item["coordinate_status"] == "BUYER_CONFIRMED" and item["navigation_ready"]
    parsed = urlsplit(item["navigation_url"])
    assert parsed.hostname == "www.google.com" and "%2C" in item["navigation_url"]
    assert set(parse_qs(parsed.query)) == {"api", "destination", "travelmode"}
    assert (
        "09791234567" not in item["navigation_url"]
        and "Private instructions" not in item["navigation_url"]
    )
    assert item["confidence_level"] == "AMBER"


def test_deterministic_queue_ordering_status_window_sequence_and_ties(env):
    who = rider(env)
    orders = [order(env) for _ in range(4)]
    for index, row in enumerate(orders):
        assign(env, row, who, sequence=[1, 99, 2, 2][index])
    with env["db"].sessions.begin() as session:
        row = session.get(Order, UUID(orders[1]["id"]))
        start = (utcnow() + timedelta(days=1)).replace(microsecond=0)
        row.delivery_time_window = f"{start.isoformat()}/{(start + timedelta(hours=2)).isoformat()}"
        sources = deepcopy(row.field_sources)
        sources["delivery_time_window"] = {
            "method": "buyer_confirmation",
            "status": "extracted",
            "requires_review": False,
        }
        row.field_sources = sources
    snapshot = queue(env, who)
    assert [item["order_id"] for item in snapshot["items"]] == [
        orders[1]["id"],
        orders[0]["id"],
        orders[2]["id"],
        orders[3]["id"],
    ]
    assert act(env, who, saved(env, orders[3]["id"]), "START").status_code == 200
    assert queue(env, who)["items"][0]["order_id"] == orders[3]["id"]
    assert queue(env, who)["cursor"] != snapshot["cursor"]


def test_sequence_changes_and_poll_removals(env):
    who, row = rider(env), order(env)
    assigned = assign(env, row, who)
    before = queue(env, who)
    response = env["client"].patch(
        f"/api/orders/{row['id']}/assignment",
        headers=HEADERS,
        json={"expected_version": assigned["order_version"], "stop_sequence": 1},
    )
    assert response.status_code == 200
    assert queue(env, who, cursor=before["cursor"])["items"][0]["stop_sequence"] == 1
    assert queue(env, who)["cursor"] != before["cursor"]
    assert act(env, who, saved(env, row["id"]), "START").status_code == 200
    assert (
        env["client"]
        .patch(
            f"/api/orders/{row['id']}/assignment",
            headers=HEADERS,
            json={"expected_version": saved(env, row["id"])["version"], "stop_sequence": 2},
        )
        .status_code
        == 409
    )


def test_queue_capacity_concurrency_and_assignment_unique(env):
    who = rider(env)
    rows = [order(env), order(env)]
    env["settings"].rider_max_active_assignments = 1

    def submit(row):
        with TestClient(env["app"], client=("127.0.0.1", 50001)) as client:
            return client.post(
                f"/api/orders/{row['id']}/assign",
                headers=HEADERS,
                json={"rider_id": who["id"], "expected_version": row["version"]},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, rows)) == [201, 409]
    assert queue(env, who)["total"] == 1
    with env["db"].sessions() as session:
        active = session.scalar(select(DeliveryAssignment))
        session.add(
            DeliveryAssignment(
                order_id=active.order_id, rider_id=active.rider_id, dispatcher_id=env["dispatcher"]
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_concurrent_delivery_completion_single_event(env):
    who, row = rider(env), order(env)
    assign(env, row, who)
    act(env, who, saved(env, row["id"]), "START")
    current = saved(env, row["id"])
    body = {
        "expected_version": current["version"],
        "request_id": str(uuid4()),
        "action": "DELIVERED",
        "cod_collected": True,
    }

    def finish(_):
        with TestClient(env["app"], client=("127.0.0.1", 50001)) as client:
            response = client.patch(
                f"/api/riders/{who['id']}/deliveries/{row['id']}/status", headers=HEADERS, json=body
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(finish, range(4))) == [200, 200, 200, 200]
    with env["db"].sessions() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(DeliveryEvent.event_type == "DELIVERY_COMPLETED")
            )
            == 1
        )


def test_transaction_rollback_preserves_assignment_and_order(env, monkeypatch):
    who, row = rider(env), order(env)
    assign(env, row, who)

    def failure(*args, **kwargs):
        raise OperationalError("private SQL", {}, Exception("private contact"))

    monkeypatch.setattr(RiderService, "event", failure)
    response = act(env, who, saved(env, row["id"]), "START")
    assert response.status_code == 503 and "private" not in response.text
    assert saved(env, row["id"])["status"] == "ASSIGNED"
    with env["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(RiderActionReceipt)) == 0


def test_unknown_cod_rejected_and_stale_assignment_version(env):
    who, row = rider(env), order(env, cod_amount=None)
    response = env["client"].post(
        f"/api/orders/{row['id']}/assign",
        headers=HEADERS,
        json={"rider_id": who["id"], "expected_version": row["version"]},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "COD_AMOUNT_REQUIRED"
    assert (
        env["client"]
        .post(
            f"/api/orders/{row['id']}/assign",
            headers=HEADERS,
            json={"rider_id": who["id"], "expected_version": 1},
        )
        .status_code
        == 409
    )


def test_production_disabled_and_remote_denial(env):
    who = rider(env)
    with TestClient(env["app"], client=("203.0.113.1", 50000)) as client:
        assert client.get(f"/api/riders/{who['id']}/queue", headers=HEADERS).status_code == 403
    production = Settings(_env_file=None, environment="production", order_management_enabled=True)
    with TestClient(create_app(production), client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/riders", headers=HEADERS).status_code == 503


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 101}, {"operational_status": "UNKNOWN"}]
)
def test_rider_list_query_validation(env, params):
    assert env["client"].get("/api/riders", headers=HEADERS, params=params).status_code == 422


def test_queue_cursor_validation_and_rider_binding(env):
    who, other = rider(env), rider(env, "Other")
    assert queue(env, who)["cursor"] != queue(env, other)["cursor"]
    assert (
        env["client"]
        .get(f"/api/riders/{who['id']}/queue", headers=HEADERS, params={"cursor": "bad"})
        .status_code
        == 422
    )
    assert env["client"].get(f"/api/riders/{uuid4()}", headers=HEADERS).status_code == 404


def test_existing_rider_and_buyer_records_survive_migration(tmp_path):
    from alembic import command
    from alembic.config import Config

    from app.db.buyer_models import ConfirmationLink
    from app.db.session import BACKEND_ROOT

    db = Database(f"sqlite+pysqlite:///{tmp_path / 'previous_phase.sqlite3'}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002_buyer_confirmation")
    rider_id, merchant_id, order_id = uuid4(), uuid4(), uuid4()
    with db.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=rider_id,
                    name="Existing rider",
                    email="rider@example.test",
                    role=UserRole.RIDER,
                ),
                User(
                    id=merchant_id,
                    name="Existing merchant",
                    email="merchant@example.test",
                    role=UserRole.MERCHANT,
                ),
            ]
        )
        session.flush()
        session.add(
            Order(
                id=order_id,
                merchant_id=merchant_id,
                confidence_level="RED",
                confidence_reasons=[],
                parsing_mode="structured",
                ai_availability_status="not_requested",
                field_sources={},
                parsing_metadata={},
            )
        )
        session.flush()
        session.add(
            ConfirmationLink(
                order_id=order_id,
                token_hash="h" * 64,
                phone_binding="b" * 64,
                expires_at=utcnow() + timedelta(days=1),
            )
        )
    upgrade_database(db)
    with db.sessions() as session:
        assert session.get(RiderProfile, rider_id).operational_status == "OFFLINE"
        assert session.get(User, rider_id).name == "Existing rider"
        assert session.scalar(select(ConfirmationLink)).token_hash == "h" * 64
        assert session.get(Order, order_id).status.value == "DRAFT"
    db.dispose()


def test_buyer_approved_update_reaches_reassigned_queue(env):
    who, row = rider(env), order(env)
    assigned = assign(env, row, who)
    old_cursor = queue(env, who)["cursor"]
    assert (
        env["client"]
        .post(
            f"/api/orders/{row['id']}/unassign",
            headers=HEADERS,
            json={"expected_version": assigned["order_version"]},
        )
        .status_code
        == 200
    )
    current = saved(env, row["id"])
    assert (
        env["client"]
        .patch(
            f"/api/orders/{row['id']}/status",
            headers=HEADERS,
            json={"status": "NEEDS_REVIEW", "expected_version": current["version"]},
        )
        .status_code
        == 200
    )
    link = env["client"].post(f"/api/orders/{row['id']}/confirmation-link", headers=HEADERS).json()
    path = "/api" + link["confirmation_url"]
    verified = env["client"].post(path + "/verify", json={"last_four": "4567"}).json()
    auth = {"Authorization": "Bearer " + verified["access_token"]}
    proposed = env["client"].patch(
        path + "/location",
        headers=auth,
        json={
            "request_id": str(uuid4()),
            "latitude": "16.8",
            "longitude": "96.1",
            "initial_pin_acknowledged": True,
        },
    )
    assert proposed.json()["decision"] == "REVIEW_REQUIRED"
    assert queue(env, who)["total"] == 0
    request = (
        env["client"]
        .get(f"/api/orders/{row['id']}/buyer-requests", headers=HEADERS)
        .json()["items"][0]
    )
    approval = env["client"].patch(
        f"/api/orders/{row['id']}/buyer-requests/{request['id']}",
        headers=HEADERS,
        json={
            "expected_version": saved(env, row["id"])["version"],
            "decision": "APPROVE",
            "reason": "Checked updated buyer pin",
        },
    )
    assert approval.status_code == 200
    assert (
        env["client"]
        .patch(
            path + "/response",
            headers=auth,
            json={
                "request_id": str(uuid4()),
                "action": "AVAILABLE",
                "instructions": "ဘေးတံခါးမှဝင်ပါ",
            },
        )
        .status_code
        == 200
    )
    current = saved(env, row["id"])
    ready = (
        env["client"]
        .patch(
            f"/api/orders/{row['id']}/status",
            headers=HEADERS,
            json={
                "status": "READY_FOR_DISPATCH",
                "expected_version": current["version"],
                "acknowledge_unverified_location": True,
            },
        )
        .json()
    )
    assign(env, ready, who)
    snapshot = queue(env, who, cursor=old_cursor)
    item = snapshot["items"][0]
    assert not snapshot["unchanged"] and Decimal(item["latitude"]) == Decimal("16.8")
    assert item["delivery_instructions"] == "ဘေးတံခါးမှဝင်ပါ"
    assert item["buyer_confirmation"]["availability"] == "AVAILABLE" and item["navigation_ready"]
    assert (
        env["client"]
        .patch(
            path + "/response",
            headers=auth,
            json={
                "request_id": str(uuid4()),
                "action": "INSTRUCTIONS",
                "instructions": "unapproved new note",
            },
        )
        .status_code
        == 409
    )
    assert queue(env, who)["items"][0]["delivery_instructions"] == "ဘေးတံခါးမှဝင်ပါ"


def test_rider_completion_applies_buyer_24h_view_policy(env):
    who, row = rider(env), order(env)
    current = saved(env, row["id"])
    env["client"].patch(
        f"/api/orders/{row['id']}/status",
        headers=HEADERS,
        json={"status": "NEEDS_REVIEW", "expected_version": current["version"]},
    )
    link = env["client"].post(f"/api/orders/{row['id']}/confirmation-link", headers=HEADERS).json()
    current = saved(env, row["id"])
    for status in ("CONFIRMED", "READY_FOR_DISPATCH"):
        response = env["client"].patch(
            f"/api/orders/{row['id']}/status",
            headers=HEADERS,
            json={
                "status": status,
                "expected_version": current["version"],
                "acknowledge_unverified_location": True,
            },
        )
        assert response.status_code == 200
        current = response.json()
    assign(env, current, who)
    act(env, who, saved(env, row["id"]), "START")
    assert act(env, who, saved(env, row["id"]), "DELIVERED", cod_collected=True).status_code == 200
    card = env["client"].get("/api" + link["confirmation_url"])
    assert card.json()["state"] == "VIEW_ONLY"
    expiry = datetime.fromisoformat(card.json()["expires_at"].replace("Z", "+00:00"))
    assert timedelta(hours=23, minutes=59) < expiry - utcnow() < timedelta(hours=24, minutes=1)


def test_active_assignment_persists_on_reopen(env):
    who, row = rider(env), order(env)
    assigned = assign(env, row, who)
    reopened = Database(env["db"].engine.url.render_as_string(hide_password=False))
    try:
        with reopened.sessions() as session:
            assignment = session.get(DeliveryAssignment, UUID(assigned["assignment"]["id"]))
            assert assignment.rider_id == UUID(who["id"]) and assignment.status == "ACTIVE"
            assert session.get(Order, UUID(row["id"])).status.value == "ASSIGNED"
    finally:
        reopened.dispose()


def test_legacy_status_completion_also_requires_cod_confirmation(env):
    row = order(env)
    current = row
    for target in ("ASSIGNED", "OUT_FOR_DELIVERY"):
        response = env["client"].patch(
            f"/api/orders/{row['id']}/status",
            headers=HEADERS,
            json={"status": target, "expected_version": current["version"]},
        )
        assert response.status_code == 200
        current = response.json()
    body = {"status": "DELIVERED", "expected_version": current["version"]}
    assert (
        env["client"]
        .patch(f"/api/orders/{row['id']}/status", headers=HEADERS, json=body)
        .status_code
        == 409
    )
    completed = env["client"].patch(
        f"/api/orders/{row['id']}/status", headers=HEADERS, json={**body, "cod_collected": True}
    )
    assert completed.status_code == 200
    assert completed.json()["parsing_metadata"]["delivery_completion"]["cod_collected"] is True
