import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.access_logging import HideQueryString
from app.core.config import Settings
from app.db.buyer_models import BuyerRequest, BuyerSession, ConfirmationLink, LocationReference
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.session import Database
from app.domain.lifecycle import OrderStatus, UserRole
from app.main import create_app
from app.services.buyer_confirmation import BuyerConfirmationService, digest
from app.services.buyer_policy import TownshipBoundaryResolver, distance_meters

DEV_TOKEN = "buyer-fixture-private-dispatcher-token-" + "x" * 32
ADMIN = {"X-Dev-Access-Token": DEV_TOKEN}


class SyntheticBoundaries(TownshipBoundaryResolver):
    """Isolated test geography, not claimed to represent real Yangon boundaries."""

    def township_at(self, latitude, longitude):
        if not 16 < float(latitude) < 17:
            return None
        return "Hlaing" if float(longitude) < 96.11 else "Kamaryut"


@pytest.fixture
def env(tmp_path):
    db = Database(f"sqlite+pysqlite:///{tmp_path / 'buyers.sqlite3'}")
    upgrade_database(db)
    dispatcher, merchant, other = uuid4(), uuid4(), uuid4()
    with db.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=dispatcher,
                    name="Test dispatcher",
                    email="dispatch@example.test",
                    role=UserRole.DISPATCHER,
                ),
                User(
                    id=merchant,
                    name="Not verified branding",
                    email="merchant@example.test",
                    role=UserRole.MERCHANT,
                ),
                User(id=other, name="Other", email="other@example.test", role=UserRole.MERCHANT),
            ]
        )
    settings = Settings(
        _env_file=None,
        environment="test",
        order_management_enabled=True,
        dev_access_token=DEV_TOKEN,
        dev_actor_id=dispatcher,
    )
    app = create_app(settings, database=db, township_boundaries=SyntheticBoundaries())
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield {
            "db": db,
            "app": app,
            "client": client,
            "merchant": merchant,
            "other": other,
            "dispatcher": dispatcher,
            "settings": settings,
        }
    db.dispose()


def order_create(env):
    response = env["client"].post(
        "/api/orders",
        headers=ADMIN,
        json={
            "merchant_id": str(env["merchant"]),
            "structured": {
                "customer_name": "Private buyer",
                "customer_phone": "09791234567",
                "township": "Hlaing",
                "street": "Private street",
                "cod_amount": "25000",
            },
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()
    response = env["client"].patch(
        f"/api/orders/{order['id']}/status",
        headers=ADMIN,
        json={"status": "NEEDS_REVIEW", "expected_version": order["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def linked(env):
    order = order_create(env)
    response = env["client"].post(f"/api/orders/{order['id']}/confirmation-link", headers=ADMIN)
    assert response.status_code == 201, response.text
    info = response.json()
    return {**env, "order": order, "link": info, "path": "/api" + info["confirmation_url"]}


def verified(linked):
    response = linked["client"].post(linked["path"] + "/verify", json={"last_four": "4567"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def pin(**changes):
    return {
        "request_id": str(uuid4()),
        "latitude": "16.8000000",
        "longitude": "96.1000000",
        **changes,
    }


def reference(linked):
    response = linked["client"].post(
        f"/api/orders/{linked['order']['id']}/location-reference",
        headers=ADMIN,
        json={
            **pin(),
            "township": "Hlaing",
            "source_reference": "synthetic-test-anchor-only",
            "independently_checked": True,
        },
    )
    assert response.status_code == 201, response.text


def saved(linked):
    return linked["client"].get(f"/api/orders/{linked['order']['id']}", headers=ADMIN).json()


def test_hashed_credentials_minimal_card_and_details(linked):
    client = linked["client"]
    card = client.get(linked["path"])
    assert card.status_code == 200
    assert set(card.json()) == {
        "order_reference",
        "shop_display_name",
        "delivery_status",
        "state",
        "expires_at",
    }
    assert card.json()["shop_display_name"] is None
    for private in ("Private buyer", "Private street", "09791234567", DEV_TOKEN):
        assert private not in card.text
    assert card.headers["cache-control"] == "no-store"
    assert card.headers["referrer-policy"] == "no-referrer"
    assert card.headers["x-robots-tag"] == "noindex, nofollow"
    assert client.get(linked["path"] + "/details").status_code == 401
    auth = verified(linked)
    detail = client.get(linked["path"] + "/details", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["street"] == "Private street"
    assert "customer_phone" not in detail.json()
    with linked["db"].sessions() as session:
        link = session.scalar(select(ConfirmationLink))
        credential = session.scalar(select(BuyerSession))
        assert link.token_hash == digest(linked["path"].rsplit("/", 1)[1])
        assert linked["path"].rsplit("/", 1)[1] != link.token_hash
        assert credential.token_hash == digest(auth["Authorization"][7:])
        assert link.verified_at.tzinfo is not None
    assert client.get("/api/orders", headers=auth).status_code == 401


@pytest.mark.parametrize(
    "last_four", ["", "123", "12345", "၄၅၆၇", 4567, None, True, " 4567", "4567\n"]
)
def test_verification_input_validation(linked, last_four):
    assert (
        linked["client"].post(linked["path"] + "/verify", json={"last_four": last_four}).status_code
        == 422
    )
    with linked["db"].sessions() as session:
        assert session.scalar(select(ConfirmationLink)).failed_attempts == 0


def test_three_failed_attempts_lock_all_sessions(linked):
    auth = verified(linked)
    for _ in range(3):
        response = linked["client"].post(linked["path"] + "/verify", json={"last_four": "0000"})
        assert response.status_code == 403
        assert "0000" not in response.text and "4567" not in response.text
    assert (
        linked["client"].post(linked["path"] + "/verify", json={"last_four": "4567"}).status_code
        == 423
    )
    assert linked["client"].get(linked["path"]).json()["state"] == "LOCKED"
    assert (
        linked["client"].patch(linked["path"] + "/location", headers=auth, json=pin()).status_code
        == 423
    )
    with linked["db"].sessions() as session:
        assert session.scalar(select(ConfirmationLink)).failed_attempts == 3
        events = session.scalars(
            select(DeliveryEvent).where(DeliveryEvent.event_type == "BUYER_SECURITY")
        ).all()
        assert len(events) == 4
        assert all("last_four" not in str(row.event_metadata) for row in events)


def test_concurrent_failure_limit(linked):
    def attempt(_):
        with TestClient(linked["app"], client=("127.0.0.1", 50001)) as client:
            return client.post(linked["path"] + "/verify", json={"last_four": "0000"}).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(attempt, range(6)))
    assert statuses.count(403) == 3
    assert statuses.count(423) == 3
    with linked["db"].sessions() as session:
        assert session.scalar(select(ConfirmationLink)).failed_attempts == 3


def test_session_rotation_and_expiry(linked):
    first, second = verified(linked), verified(linked)
    assert linked["client"].get(linked["path"] + "/details", headers=first).status_code == 401
    assert linked["client"].get(linked["path"] + "/details", headers=second).status_code == 200
    with linked["db"].sessions.begin() as session:
        for item in session.scalars(select(BuyerSession)):
            item.expires_at = utcnow() - timedelta(seconds=1)
    assert linked["client"].get(linked["path"] + "/details", headers=second).status_code == 401


def test_invalid_expired_revoked_and_replaced_links(linked):
    assert linked["client"].get("/api/confirm/" + "x" * 43).status_code == 404
    assert linked["client"].get("/api/confirm/not-a-token").status_code == 404
    with linked["db"].sessions.begin() as session:
        session.scalar(select(ConfirmationLink)).expires_at = utcnow() - timedelta(seconds=1)
    assert linked["client"].get(linked["path"]).status_code == 410
    fresh = linked["client"].post(
        f"/api/orders/{linked['order']['id']}/confirmation-link", headers=ADMIN
    )
    assert fresh.status_code == 201
    assert linked["client"].get(linked["path"]).status_code == 404
    new_path = "/api" + fresh.json()["confirmation_url"]
    auth = linked["client"].post(new_path + "/verify", json={"last_four": "4567"}).json()
    revoked = linked["client"].post(
        f"/api/orders/{linked['order']['id']}/confirmation-link/revoke", headers=ADMIN
    )
    assert revoked.status_code == 200
    assert linked["client"].get(new_path).status_code == 404
    assert (
        linked["client"]
        .get(new_path + "/details", headers={"Authorization": "Bearer " + auth["access_token"]})
        .status_code
        == 404
    )


def test_wrong_link_session_cannot_authorize_another_order(linked):
    auth = verified(linked)
    other = order_create(linked)
    new = (
        linked["client"].post(f"/api/orders/{other['id']}/confirmation-link", headers=ADMIN).json()
    )
    assert (
        linked["client"]
        .patch("/api" + new["confirmation_url"] + "/location", headers=auth, json=pin())
        .status_code
        == 401
    )


def test_initial_pin_requires_ack_and_dispatcher_approval(linked):
    auth = verified(linked)
    assert (
        linked["client"].patch(linked["path"] + "/location", headers=auth, json=pin()).status_code
        == 409
    )
    body = pin(initial_pin_acknowledged=True)
    response = linked["client"].patch(linked["path"] + "/location", headers=auth, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "REVIEW_REQUIRED"
    assert saved(linked)["latitude"] is None
    history = (
        linked["client"]
        .get(f"/api/orders/{linked['order']['id']}/buyer-requests", headers=ADMIN)
        .json()
    )
    request = history["items"][0]
    assert request["submitted_values"]["latitude"] == body["latitude"]
    approved = linked["client"].patch(
        f"/api/orders/{linked['order']['id']}/buyer-requests/{request['id']}",
        headers=ADMIN,
        json={
            "expected_version": saved(linked)["version"],
            "decision": "APPROVE",
            "reason": "Reviewed customer submitted pin",
        },
    )
    assert approved.status_code == 200, approved.text
    order = saved(linked)
    assert Decimal(order["latitude"]) == Decimal(body["latitude"])
    assert order["confidence_level"] == "AMBER"
    assert order["field_sources"]["latitude"]["method"] == "buyer_confirmation"
    assert not order["field_sources"]["latitude"]["verified"]
    # Approved initial pin does not create a trusted movement reference.
    with linked["db"].sessions() as session:
        assert session.get(LocationReference, UUID(order["id"])) is None


@pytest.mark.parametrize(
    "latitude,longitude,reason",
    [
        ("16.8001000", "96.1001000", None),
        ("16.8100000", "96.1000000", "ZONE_2_RESCHEDULE_REVIEW_REQUIRED"),
        ("16.8000000", "96.1200000", "CROSS_TOWNSHIP_APPROVAL_REQUIRED"),
        ("18.0000000", "96.1000000", "TOWNSHIP_BOUNDARY_UNVERIFIED"),
    ],
)
def test_location_zones(linked, latitude, longitude, reason):
    reference(linked)
    auth = verified(linked)
    body = pin(latitude=latitude, longitude=longitude)
    response = linked["client"].patch(linked["path"] + "/location", headers=auth, json=body)
    assert response.status_code == 200, response.text
    if reason:
        assert reason in response.json()["reason_codes"]
        assert saved(linked)["latitude"] is None
    else:
        assert response.json()["decision"] == "APPLIED"
        assert Decimal(saved(linked)["latitude"]) == Decimal(latitude)
        assert saved(linked)["confidence_level"] == "AMBER"


def test_missing_boundaries_no_auto_accept_and_anchor_cannot_drift(linked):
    reference(linked)
    auth = verified(linked)
    first = linked["client"].patch(
        linked["path"] + "/location", headers=auth, json=pin(latitude="16.8040000")
    )
    assert first.json()["decision"] == "APPLIED"
    second = linked["client"].patch(
        linked["path"] + "/location", headers=auth, json=pin(latitude="16.8080000")
    )
    assert second.json()["decision"] == "REVIEW_REQUIRED"  # <500m from first, >500m from anchor.
    linked["app"].state.township_boundaries = TownshipBoundaryResolver()
    third = linked["client"].patch(linked["path"] + "/location", headers=auth, json=pin())
    assert "TOWNSHIP_BOUNDARY_UNVERIFIED" in third.json()["reason_codes"]


@pytest.mark.parametrize(
    "fields",
    [
        {"latitude": "91"},
        {"longitude": "181"},
        {"latitude": "NaN"},
        {"latitude": True},
        {"latitude": "16.12345678"},
        {"longitude": None},
        {"township": "Hlaing"},
        {"verified": True},
        {"distance_meters": 1},
    ],
)
def test_location_cannot_inject_trust_or_invalid_coordinates(linked, fields):
    auth = verified(linked)
    assert (
        linked["client"]
        .patch(linked["path"] + "/location", headers=auth, json=pin(**fields))
        .status_code
        == 422
    )


def test_idempotent_requests_conflicts_and_atomic_events(linked):
    auth = verified(linked)
    body = pin(initial_pin_acknowledged=True)
    first = linked["client"].patch(linked["path"] + "/location", headers=auth, json=body)
    before = saved(linked)["version"]
    second = linked["client"].patch(linked["path"] + "/location", headers=auth, json=body)
    assert first.json()["request_id"] == second.json()["request_id"]
    assert saved(linked)["version"] == before
    assert (
        linked["client"]
        .patch(linked["path"] + "/location", headers=auth, json={**body, "latitude": "16.9"})
        .status_code
        == 409
    )
    with linked["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(BuyerRequest)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(DeliveryEvent.event_type == "BUYER_LOCATION")
            )
            == 1
        )


def test_no_unauthorized_location_or_response(linked):
    for action, body in (
        ("location", pin()),
        ("response", {"request_id": str(uuid4()), "action": "AVAILABLE"}),
    ):
        assert linked["client"].patch(linked["path"] + "/" + action, json=body).status_code == 401
        assert (
            linked["client"]
            .patch(linked["path"] + "/" + action, headers=ADMIN, json=body)
            .status_code
            == 401
        )


def test_availability_and_instructions_persist_without_green(linked):
    auth = verified(linked)
    response = linked["client"].patch(
        linked["path"] + "/response",
        headers=auth,
        json={
            "request_id": str(uuid4()),
            "action": "AVAILABLE",
            "instructions": "Call at the gate",
        },
    )
    assert response.status_code == 200
    assert response.json()["order_status"] == "CONFIRMED"
    assert response.json()["confidence_level"] == "AMBER"
    assert saved(linked)["delivery_instructions"] == "Call at the gate"
    assert saved(linked)["field_sources"]["delivery_instructions"]["method"] == "buyer_confirmation"


def window(now=None):
    now = now or utcnow()
    start = (now + timedelta(days=2)).replace(hour=3, minute=0, second=0, microsecond=0)
    return {"start": start.isoformat(), "end": (start + timedelta(hours=2)).isoformat()}


def test_rescheduling_disabled_or_cutoff_creates_review(linked, monkeypatch):
    auth = verified(linked)
    morning = datetime.now(UTC).replace(hour=1)
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: morning)
    body = {"request_id": str(uuid4()), "action": "RESCHEDULE", "time_window": window(morning)}
    response = linked["client"].patch(linked["path"] + "/response", headers=auth, json=body)
    assert "COURIER_RESCHEDULING_REVIEW_REQUIRED" in response.json()["reason_codes"]
    assert saved(linked)["delivery_time_window"] is None
    linked["settings"].buyer_rescheduling_enabled = True
    late = morning.replace(hour=12)  # 18:30 Yangon, after the 15:00 cutoff.
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: late)
    # Extend the session for this isolated clock jump.
    with linked["db"].sessions.begin() as session:
        session.scalar(select(BuyerSession)).expires_at = late + timedelta(minutes=15)
    response = linked["client"].patch(
        linked["path"] + "/response", headers=auth, json={**body, "request_id": str(uuid4())}
    )
    assert "COURIER_CUTOFF_REVIEW_REQUIRED" in response.json()["reason_codes"]


def test_supported_reschedule_and_leave_with_security(linked, monkeypatch):
    linked["settings"].buyer_rescheduling_enabled = True
    linked["settings"].buyer_leave_with_security_enabled = True
    now = utcnow().replace(hour=1)
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: now)
    auth = verified(linked)
    response = linked["client"].patch(
        linked["path"] + "/response",
        headers=auth,
        json={"request_id": str(uuid4()), "action": "RESCHEDULE", "time_window": window(now)},
    )
    assert response.json()["decision"] == "APPLIED", response.text
    assert saved(linked)["delivery_time_window"] is not None
    response = linked["client"].patch(
        linked["path"] + "/response",
        headers=auth,
        json={
            "request_id": str(uuid4()),
            "action": "LEAVE_WITH_SECURITY",
            "instructions": "Leave with front desk",
        },
    )
    assert response.json()["decision"] == "APPLIED"


@pytest.mark.parametrize(
    "body",
    [
        {"action": "RESCHEDULE"},
        {"action": "INSTRUCTIONS"},
        {"action": "UNKNOWN"},
        {"action": "INSTRUCTIONS", "instructions": " "},
        {"action": "INSTRUCTIONS", "instructions": "x" * 2001},
        {"action": "AVAILABLE", "status": "DELIVERED"},
        {
            "action": "RESCHEDULE",
            "time_window": {"start": "2026-01-01T12:00:00", "end": "2026-01-01T14:00:00"},
        },
        {
            "action": "RESCHEDULE",
            "time_window": {"start": "2026-01-01T12:00:00Z", "end": "2026-01-01T11:00:00Z"},
        },
    ],
)
def test_invalid_response_payloads(linked, body):
    auth = verified(linked)
    assert (
        linked["client"]
        .patch(
            linked["path"] + "/response", headers=auth, json={"request_id": str(uuid4()), **body}
        )
        .status_code
        == 422
    )


def test_past_and_overnight_windows_rejected(linked):
    auth = verified(linked)
    for times in (
        {"start": (utcnow() - timedelta(days=1)).isoformat(), "end": utcnow().isoformat()},
        {
            "start": (utcnow() + timedelta(days=2)).replace(hour=16).isoformat(),
            "end": (utcnow() + timedelta(days=2)).replace(hour=19).isoformat(),
        },
    ):
        assert (
            linked["client"]
            .patch(
                linked["path"] + "/response",
                headers=auth,
                json={"request_id": str(uuid4()), "action": "RESCHEDULE", "time_window": times},
            )
            .status_code
            == 422
        )


def test_pending_location_prevents_availability_bypass(linked):
    auth = verified(linked)
    linked["client"].patch(
        linked["path"] + "/location", headers=auth, json=pin(initial_pin_acknowledged=True)
    )
    response = linked["client"].patch(
        linked["path"] + "/response",
        headers=auth,
        json={"request_id": str(uuid4()), "action": "AVAILABLE"},
    )
    assert response.json()["decision"] == "REVIEW_REQUIRED"
    assert saved(linked)["status"] == "NEEDS_REVIEW"


@pytest.mark.parametrize(
    "status",
    ["READY_FOR_DISPATCH", "ASSIGNED", "OUT_FOR_DELIVERY", "FAILED", "CANCELLED", "DELIVERED"],
)
def test_closed_order_never_accepts_buyer_changes(linked, status):
    auth = verified(linked)
    with linked["db"].sessions.begin() as session:
        session.get(Order, UUID(linked["order"]["id"])).status = OrderStatus(status)
    for suffix, body in (
        ("location", pin()),
        ("response", {"request_id": str(uuid4()), "action": "AVAILABLE"}),
        ("verify", {"last_four": "4567"}),
    ):
        response = (linked["client"].post if suffix == "verify" else linked["client"].patch)(
            linked["path"] + "/" + suffix, headers=auth, json=body
        )
        assert response.status_code in {404, 409, 410}


def test_delivery_view_only_24h_and_cancel_revoke(linked, monkeypatch):
    auth = verified(linked)
    now = utcnow()
    for target in ("CONFIRMED", "READY_FOR_DISPATCH", "ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED"):
        current = saved(linked)
        response = linked["client"].patch(
            f"/api/orders/{current['id']}/status",
            headers=ADMIN,
            json={
                "status": target,
                "expected_version": current["version"],
                "acknowledge_unverified_location": True,
                **({"cod_collected": True} if target == "DELIVERED" else {}),
            },
        )
        assert response.status_code == 200, response.text
    card = linked["client"].get(linked["path"])
    assert card.status_code == 200 and card.json()["state"] == "VIEW_ONLY"
    expiry = datetime.fromisoformat(card.json()["expires_at"].replace("Z", "+00:00"))
    assert timedelta(hours=23, minutes=59) < expiry - now < timedelta(hours=24, minutes=1)
    assert linked["client"].get(linked["path"] + "/details", headers=auth).status_code == 409
    monkeypatch.setattr(
        "app.services.buyer_confirmation.utcnow", lambda: expiry + timedelta(seconds=1)
    )
    assert linked["client"].get(linked["path"]).status_code == 410


def test_phone_correction_invalidates_link_and_session(linked):
    auth = verified(linked)
    response = linked["client"].patch(
        f"/api/orders/{linked['order']['id']}",
        headers=ADMIN,
        json={"expected_version": saved(linked)["version"], "customer_phone": "09961234567"},
    )
    assert response.status_code == 200
    assert linked["client"].get(linked["path"]).status_code == 404
    assert linked["client"].get(linked["path"] + "/details", headers=auth).status_code == 404
    current = saved(linked)
    assert (
        linked["client"]
        .patch(
            f"/api/orders/{current['id']}",
            headers=ADMIN,
            json={"expected_version": current["version"], "customer_phone": "09791234567"},
        )
        .status_code
        == 200
    )
    assert linked["client"].get(linked["path"]).status_code == 404


def test_rate_limit_shared_db_and_ignored_forwarded_ip(linked):
    linked["settings"].buyer_request_limit_per_minute = 2
    assert linked["client"].get(linked["path"]).status_code == 200
    assert linked["client"].get(linked["path"]).status_code == 200
    response = linked["client"].get(linked["path"], headers={"X-Forwarded-For": "8.8.8.8"})
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    second_app = create_app(linked["settings"], database=linked["db"])
    with TestClient(second_app, client=("127.0.0.1", 50001)) as client:
        assert client.get(linked["path"]).status_code == 429


def test_verification_rate_limit_even_with_correct_digits(linked):
    linked["settings"].buyer_verify_limit_per_minute = 1
    verified(linked)
    assert (
        linked["client"].post(linked["path"] + "/verify", json={"last_four": "4567"}).status_code
        == 429
    )


def test_public_production_fail_closed_without_db(env):
    settings = Settings(_env_file=None, environment="production", order_management_enabled=True)
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/confirm/" + "x" * 43).status_code == 503


def test_link_generation_authorization_and_scope(linked):
    url = f"/api/orders/{linked['order']['id']}/confirmation-link"
    assert linked["client"].post(url).status_code == 401
    linked["settings"].dev_actor_id = linked["other"]
    assert linked["client"].post(url, headers=ADMIN).status_code == 404
    linked["settings"].dev_actor_id = linked["merchant"]
    assert linked["client"].post(url, headers=ADMIN).status_code == 201
    assert (
        linked["client"]
        .post(
            f"/api/orders/{linked['order']['id']}/location-reference",
            headers=ADMIN,
            json={
                **pin(),
                "township": "Hlaing",
                "source_reference": "test",
                "independently_checked": True,
            },
        )
        .status_code
        == 403
    )


def test_safe_log_filter_redacts_capability_path():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        1,
        "%s %s %s %s %s",
        ("peer", "GET", "/api/confirm/private-secret/details?token=also-secret", "1.1", 200),
        None,
    )
    HideQueryString().filter(record)
    assert "private-secret" not in record.getMessage() and "also-secret" not in record.getMessage()
    assert "[REDACTED]/details" in record.getMessage()


def test_rollback_does_not_partially_apply_buyer_request(linked, monkeypatch):
    reference(linked)
    auth = verified(linked)
    before = saved(linked)

    def failed_event(*args, **kwargs):
        raise OperationalError("private SQL", {}, Exception("private data"))

    monkeypatch.setattr(BuyerConfirmationService, "event", failed_event)
    response = linked["client"].patch(linked["path"] + "/location", headers=auth, json=pin())
    assert response.status_code == 503
    assert "private" not in response.text
    assert saved(linked)["latitude"] == before["latitude"]
    with linked["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(BuyerRequest)) == 0


def test_geo_distance_known_scales():
    assert distance_meters(0, 0, 0, 0) == 0
    assert 111000 < distance_meters(0, 0, 0, 1) < 112000
    assert distance_meters(16.8, 96.1, 16.804, 96.1) < 500
    assert distance_meters(16.8, 96.1, 16.805, 96.1) > 500


def test_frontend_absolute_url_configuration(linked):
    linked["settings"].buyer_frontend_base_url = "https://buyer.example.test"
    response = (
        linked["client"]
        .post(f"/api/orders/{linked['order']['id']}/confirmation-link", headers=ADMIN)
        .json()
    )
    assert response["absolute_url"] == "https://buyer.example.test" + response["confirmation_url"]
    for bad in (
        "http://unsafe.example.test",
        "https://user:password@example.test",
        "https://example.test?token=x",
    ):
        with pytest.raises(ValueError):
            Settings(_env_file=None, buyer_frontend_base_url=bad)


def test_cross_township_review_and_repeated_decision(linked):
    reference(linked)
    auth = verified(linked)
    linked["client"].patch(
        linked["path"] + "/location", headers=auth, json=pin(longitude="96.1200000")
    )
    current = saved(linked)
    blocked = linked["client"].patch(
        f"/api/orders/{current['id']}/status",
        headers=ADMIN,
        json={"status": "CONFIRMED", "expected_version": current["version"]},
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "BUYER_REVIEW_REQUIRED"
    row = (
        linked["client"]
        .get(f"/api/orders/{current['id']}/buyer-requests", headers=ADMIN)
        .json()["items"][0]
    )
    url = f"/api/orders/{current['id']}/buyer-requests/{row['id']}"
    body = {
        "expected_version": current["version"],
        "decision": "APPROVE",
        "reason": "Dispatcher reviewed cross township courier policy",
    }
    approved = linked["client"].patch(url, headers=ADMIN, json=body)
    assert approved.status_code == 200, approved.text
    after = saved(linked)
    assert after["township"] == "Kamaryut"
    assert Decimal(after["longitude"]) == Decimal("96.12")
    assert after["confidence_level"] == "AMBER"
    assert linked["client"].patch(url, headers=ADMIN, json=body).status_code == 200
    assert saved(linked)["version"] == after["version"]
    assert (
        linked["client"].patch(url, headers=ADMIN, json={**body, "decision": "REJECT"}).status_code
        == 409
    )


def test_review_rejection_scope_and_stale_version(linked):
    auth = verified(linked)
    linked["client"].patch(
        linked["path"] + "/location", headers=auth, json=pin(initial_pin_acknowledged=True)
    )
    current = saved(linked)
    row = (
        linked["client"]
        .get(f"/api/orders/{current['id']}/buyer-requests", headers=ADMIN)
        .json()["items"][0]
    )
    url = f"/api/orders/{current['id']}/buyer-requests/{row['id']}"
    body = {
        "expected_version": current["version"],
        "decision": "REJECT",
        "reason": "Customer asked to keep existing delivery details",
    }
    assert (
        linked["client"].patch(url, headers=ADMIN, json={**body, "expected_version": 1}).status_code
        == 409
    )
    linked["settings"].dev_actor_id = linked["other"]
    assert (
        linked["client"]
        .get(f"/api/orders/{current['id']}/buyer-requests", headers=ADMIN)
        .status_code
        == 404
    )
    linked["settings"].dev_actor_id = linked["merchant"]
    assert linked["client"].patch(url, headers=ADMIN, json=body).status_code == 403
    linked["settings"].dev_actor_id = linked["dispatcher"]
    assert linked["client"].patch(url, headers=ADMIN, json=body).status_code == 200
    assert saved(linked)["latitude"] is None


def test_no_trusted_coordinate_inference_from_manual_order_pin(linked):
    current = saved(linked)
    linked["client"].patch(
        f"/api/orders/{current['id']}",
        headers=ADMIN,
        json={"expected_version": current["version"], "latitude": "16.8", "longitude": "96.1"},
    )
    auth = verified(linked)
    response = linked["client"].patch(
        linked["path"] + "/location", headers=auth, json=pin(initial_pin_acknowledged=True)
    )
    assert response.json()["decision"] == "REVIEW_REQUIRED"
    assert response.json()["confirmed_at"] is None


def test_concurrent_duplicate_location_creates_one_request(linked):
    auth = verified(linked)
    body = pin(initial_pin_acknowledged=True)

    def submit(_):
        with TestClient(linked["app"], client=("127.0.0.1", 50001)) as client:
            return client.patch(linked["path"] + "/location", headers=auth, json=body).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(submit, range(4))) == [200, 200, 200, 200]
    with linked["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(BuyerRequest)) == 1


def test_db_reopen_retains_buyer_audit_and_no_plaintext_tokens(linked):
    auth = verified(linked)
    linked["client"].patch(
        linked["path"] + "/response",
        headers=auth,
        json={
            "request_id": str(uuid4()),
            "action": "INSTRUCTIONS",
            "instructions": "Use the gate bell",
        },
    )
    reopened = Database(linked["db"].engine.url.render_as_string(hide_password=False))
    try:
        with reopened.sessions() as session:
            assert session.scalar(select(func.count()).select_from(BuyerRequest)) == 1
            order = session.get(Order, UUID(linked["order"]["id"]))
            assert order.delivery_instructions == "Use the gate bell"
            assert order.field_sources["delivery_instructions"]["method"] == "buyer_confirmation"
            for table in (BuyerSession, ConfirmationLink):
                assert not any(
                    value == auth["Authorization"][7:]
                    for value in vars(session.scalar(select(table))).values()
                )
    finally:
        reopened.dispose()


def test_malformed_requests_safe_errors_and_cors(linked):
    response = linked["client"].post(
        linked["path"] + "/verify",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422 and "{not json" not in response.text
    response = linked["client"].options(
        linked["path"] + "/location",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_failed_budget_never_resets_after_success(linked):
    client = linked["client"]
    for _ in range(2):
        assert (
            client.post(linked["path"] + "/verify", json={"last_four": "0000"}).status_code == 403
        )
    verified(linked)
    assert client.post(linked["path"] + "/verify", json={"last_four": "0000"}).status_code == 403
    assert client.post(linked["path"] + "/verify", json={"last_four": "4567"}).status_code == 423


def test_cutoff_boundary_exact_hour(linked, monkeypatch):
    linked["settings"].buyer_rescheduling_enabled = True
    now = utcnow().replace(hour=8, minute=29, second=0, microsecond=0)  # 14:59 Yangon.
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: now)
    auth = verified(linked)
    body = {"request_id": str(uuid4()), "action": "RESCHEDULE", "time_window": window(now)}
    assert (
        linked["client"]
        .patch(linked["path"] + "/response", headers=auth, json=body)
        .json()["decision"]
        == "APPLIED"
    )
    monkeypatch.setattr(
        "app.services.buyer_confirmation.utcnow", lambda: now + timedelta(minutes=1)
    )
    response = linked["client"].patch(
        linked["path"] + "/response", headers=auth, json={**body, "request_id": str(uuid4())}
    )
    assert "COURIER_CUTOFF_REVIEW_REQUIRED" in response.json()["reason_codes"]


def test_unexpected_failures_never_emit_private_exception_text(linked, monkeypatch, caplog):
    def failure(*args):
        raise RuntimeError("private-buyer-name and private-capability")

    monkeypatch.setattr(BuyerConfirmationService, "card", failure)
    with caplog.at_level(logging.ERROR):
        response = linked["client"].get(linked["path"])
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert "private-buyer-name" not in caplog.text + response.text
    assert "private-capability" not in caplog.text + response.text


def test_migration_preserves_phase4_records(tmp_path):
    from alembic import command
    from alembic.config import Config

    from app.db.session import BACKEND_ROOT

    database = Database(f"sqlite+pysqlite:///{tmp_path / 'existing_phase4.sqlite3'}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_order_management")
    merchant_id, order_id = uuid4(), uuid4()
    with database.sessions.begin() as session:
        session.add(
            User(
                id=merchant_id,
                name="Existing",
                email="existing@example.test",
                role=UserRole.MERCHANT,
            )
        )
        session.flush()
        session.add(
            Order(
                id=order_id,
                merchant_id=merchant_id,
                customer_phone="09791234567",
                original_message="Existing message preserved",
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
            DeliveryEvent(
                order_id=order_id,
                event_type="ORDER_CREATED",
                previous_status=None,
                new_status=OrderStatus.DRAFT,
                event_metadata={"existing": True},
            )
        )
    upgrade_database(database)
    with database.sessions() as session:
        assert session.get(Order, order_id).original_message == "Existing message preserved"
        assert session.scalar(select(DeliveryEvent)).event_metadata == {"existing": True}
        assert session.get(User, merchant_id).name == "Existing"
    database.dispose()
