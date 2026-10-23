import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.access_logging import HideQueryString
from app.core.config import Settings
from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerEditPolicy, BuyerOtpChallenge, BuyerReminderOutbox, BuyerRequest, BuyerSession, ConfirmationLink, LocationReference
from app.db.migrations import upgrade_database
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.session import Database
from app.domain.lifecycle import OrderStatus, UserRole
from app.main import create_app
from app.services.buyer_confirmation import BuyerConfirmationService, digest
from app.services.buyer_otp import normalize_phone
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
    start = linked["client"].post(linked["path"] + "/otp", json={})
    assert start.status_code == 200, start.text
    with linked["db"].sessions() as session:
        challenge = session.get(BuyerOtpChallenge, UUID(start.json()["challenge_id"]))
        code = challenge.demo_code
    response = linked["client"].post(linked["path"] + "/verify", json={"code": code})
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


def test_otp_start_returns_only_safe_challenge_state(linked):
    response = linked["client"].post(linked["path"] + "/otp", json={})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"challenge_id", "destination_masked", "expires_at", "resend_after", "mode"}
    assert payload["destination_masked"].endswith("4567")
    assert payload["mode"] == "DEMO"
    assert "code" not in payload and "09791234567" not in response.text


@pytest.mark.parametrize(
    "value", ["09791234567", "0991234567", "+959791234567", "959791234567"]
)
def test_myanmar_phone_normalization(value):
    expected = "+95991234567" if value == "0991234567" else "+959791234567"
    assert normalize_phone(value) == expected


@pytest.mark.parametrize("value", ["+14155552671", "09912345678", "not-a-phone"])
def test_myanmar_phone_normalization_rejects_invalid_or_non_myanmar(value):
    with pytest.raises(OrderAPIError):
        normalize_phone(value)


def test_otp_accepts_number_validated_by_order_phone_validator(env):
    order = order_create(env)
    changed = env["client"].patch(
        f"/api/orders/{order['id']}",
        headers=ADMIN,
        json={"expected_version": order["version"], "customer_phone": "0991234567"},
    )
    assert changed.status_code == 200, changed.text
    link = env["client"].post(
        f"/api/orders/{order['id']}/confirmation-link", headers=ADMIN
    )
    assert link.status_code == 201, link.text
    path = "/api" + link.json()["confirmation_url"]

    started = env["client"].post(path + "/otp", json={})

    assert started.status_code == 200, started.text
    assert started.json()["mode"] == "DEMO"


def test_otp_expiry_is_capped_by_confirmation_link(linked):
    link_expiry = utcnow() + timedelta(minutes=1)
    with linked["db"].sessions.begin() as session:
        session.scalar(
            select(ConfirmationLink).where(ConfirmationLink.id == UUID(linked["link"]["link_id"]))
        ).expires_at = link_expiry

    response = linked["client"].post(linked["path"] + "/otp", json={})
    assert response.status_code == 200, response.text
    with linked["db"].sessions() as session:
        challenge = session.get(BuyerOtpChallenge, UUID(response.json()["challenge_id"]))
        assert challenge.expires_at == link_expiry


def test_otp_start_locks_coordinator_before_order(linked, monkeypatch):
    import app.services.automatic_assignment as allocation
    import app.services.buyer_otp as otp

    locks = []
    lock_coordinator = allocation.lock_allocator
    lock_order = otp.lock_order

    def record_coordinator(session):
        locks.append("coordinator")
        return lock_coordinator(session)

    def record_order(session, order_id):
        locks.append("order")
        return lock_order(session, order_id)

    monkeypatch.setattr(allocation, "lock_allocator", record_coordinator)
    monkeypatch.setattr(otp, "lock_order", record_order)

    response = linked["client"].post(linked["path"] + "/otp", json={})
    assert response.status_code == 200, response.text
    assert locks[:2] == ["coordinator", "order"]


def test_last_four_is_not_accepted_as_public_verification(linked):
    response = linked["client"].post(linked["path"] + "/verify", json={"last_four": "4567"})
    assert response.status_code == 422


def test_otp_resend_cooldown_and_replacement(linked, monkeypatch):
    start = linked["client"].post(linked["path"] + "/otp", json={})
    assert start.status_code == 200
    challenge_id = UUID(start.json()["challenge_id"])
    assert linked["client"].post(linked["path"] + "/otp", json={}).status_code == 429
    now = utcnow() + timedelta(seconds=61)
    monkeypatch.setattr("app.services.buyer_otp.utcnow", lambda: now)
    resent = linked["client"].post(linked["path"] + "/otp", json={})
    assert resent.status_code == 200
    with linked["db"].sessions() as session:
        previous = session.get(BuyerOtpChallenge, challenge_id)
        replacement = session.get(BuyerOtpChallenge, UUID(resent.json()["challenge_id"]))
        assert previous.status == "REPLACED" and previous.demo_code is None
        assert replacement.status == "PENDING"
        assert previous.code_digest != replacement.code_digest


def test_otp_expires_rejects_replay_and_is_link_bound(linked, monkeypatch):
    started = linked["client"].post(linked["path"] + "/otp", json={}).json()
    challenge_id = UUID(started["challenge_id"])
    with linked["db"].sessions.begin() as session:
        session.get(BuyerOtpChallenge, challenge_id).expires_at = utcnow() - timedelta(seconds=1)
    assert linked["client"].post(linked["path"] + "/verify", json={"code": "000000"}).status_code == 403
    with linked["db"].sessions() as session:
        assert session.get(BuyerOtpChallenge, challenge_id).status == "EXPIRED"
    auth = verified(linked)
    assert linked["client"].get(linked["path"] + "/details", headers=auth).status_code == 200
    with linked["db"].sessions() as session:
        assert session.scalar(select(BuyerOtpChallenge).where(BuyerOtpChallenge.status == "CONSUMED"))
    assert linked["client"].post(linked["path"] + "/verify", json={"code": "000000"}).status_code in {403, 423}


def test_otp_from_one_link_cannot_verify_another_link(linked):
    started = linked["client"].post(linked["path"] + "/otp", json={})
    assert started.status_code == 200
    with linked["db"].sessions() as session:
        code = session.get(BuyerOtpChallenge, UUID(started.json()["challenge_id"])).demo_code

    other_order = order_create(linked)
    other_link = linked["client"].post(
        f"/api/orders/{other_order['id']}/confirmation-link", headers=ADMIN
    )
    assert other_link.status_code == 201
    other_path = "/api" + other_link.json()["confirmation_url"]
    rejected = linked["client"].post(other_path + "/verify", json={"code": code})
    assert rejected.status_code == 403

    accepted = linked["client"].post(linked["path"] + "/verify", json={"code": code})
    assert accepted.status_code == 200


def test_otp_is_invalid_after_link_revocation_or_phone_change(linked):
    assert linked["client"].post(linked["path"] + "/otp", json={}).status_code == 200
    revoked = linked["client"].post(
        f"/api/orders/{linked['order']['id']}/confirmation-link/revoke", headers=ADMIN
    )
    assert revoked.status_code == 200
    assert linked["client"].post(linked["path"] + "/verify", json={"code": "000000"}).status_code == 404


def test_phone_change_revokes_pending_otp(linked):
    started = linked["client"].post(linked["path"] + "/otp", json={})
    challenge_id = UUID(started.json()["challenge_id"])
    order = saved(linked)
    changed = linked["client"].patch(
        f"/api/orders/{order['id']}",
        headers=ADMIN,
        json={"expected_version": order["version"], "customer_phone": "09961234567"},
    )
    assert changed.status_code == 200
    with linked["db"].sessions() as session:
        challenge = session.get(BuyerOtpChallenge, challenge_id)
        assert challenge.status == "REVOKED" and challenge.demo_code is None
    assert linked["client"].post(linked["path"] + "/verify", json={"code": "000000"}).status_code == 404


def test_same_phone_challenges_serialize_across_distinct_links(linked, monkeypatch):
    other_order = order_create(linked)
    other_link = linked["client"].post(
        f"/api/orders/{other_order['id']}/confirmation-link", headers=ADMIN
    ).json()
    other_path = "/api" + other_link["confirmation_url"]
    first = linked["client"].post(linked["path"] + "/otp", json={})
    assert first.status_code == 200
    assert linked["client"].post(other_path + "/otp", json={}).status_code == 429
    with linked["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(BuyerOtpChallenge).where(BuyerOtpChallenge.status == "PENDING")) == 1
    monkeypatch.setattr("app.services.buyer_otp.utcnow", lambda: utcnow() + timedelta(seconds=61))
    replacement = linked["client"].post(other_path + "/otp", json={})
    assert replacement.status_code == 200
    with linked["db"].sessions() as session:
        previous = session.scalar(select(BuyerOtpChallenge).where(BuyerOtpChallenge.id == UUID(first.json()["challenge_id"])))
        assert previous.status == "REPLACED" and previous.demo_code is None
        assert session.scalar(select(func.count()).select_from(BuyerOtpChallenge).where(BuyerOtpChallenge.status == "PENDING")) == 1


def test_concurrent_first_challenges_for_same_phone_serialize(linked):
    other_order = order_create(linked)
    other_link = linked["client"].post(
        f"/api/orders/{other_order['id']}/confirmation-link", headers=ADMIN
    ).json()
    other_path = "/api" + other_link["confirmation_url"]

    def start(path):
        with TestClient(linked["app"], client=("127.0.0.1", 50002)) as client:
            return client.post(path + "/otp", json={}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(start, [linked["path"], other_path]))
    assert sorted(statuses) == [200, 429]
    with linked["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(BuyerOtpChallenge).where(
            BuyerOtpChallenge.status == "PENDING"
        )) == 1


def test_twilio_resend_cancels_and_checks_the_stored_sid(linked, monkeypatch):
    import app.services.buyer_otp as otp

    linked["settings"].buyer_otp_mode = "twilio"
    linked["settings"].buyer_otp_external_sends_enabled = True
    linked["settings"].buyer_twilio_account_sid = "ACtest"
    linked["settings"].buyer_twilio_auth_token = SecretStr("test-token")
    linked["settings"].buyer_twilio_verify_service_sid = "VAtest"
    calls = []

    class Response:
        def __init__(self, status_code, payload): self.status_code, self.payload = status_code, payload
        def json(self): return self.payload

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data, auth):
            calls.append((url, data, auth))
            if url.endswith("/VerificationCheck"):
                return Response(200, {"status": "approved"})
            if url.endswith("/Verifications/VEold"):
                return Response(404, {"code": 20404})
            return Response(200, {"sid": "VEold" if len(calls) == 1 else "VEnew"})

    monkeypatch.setattr(otp.httpx, "Client", Client)
    assert linked["client"].post(linked["path"] + "/otp", json={}).status_code == 200
    monkeypatch.setattr(otp, "utcnow", lambda: utcnow() + timedelta(seconds=61))
    replacement = linked["client"].post(linked["path"] + "/otp", json={})
    assert replacement.status_code == 200
    check = linked["client"].post(linked["path"] + "/verify", json={"code": "123456"})
    assert check.status_code == 200
    assert any(url.endswith("/Verifications/VEold") and data == {"Status": "canceled"} for url, data, _ in calls)
    assert calls[-1][0].endswith("/VerificationCheck")
    assert calls[-1][1]["VerificationSid"] == "VEnew"
    with linked["db"].sessions() as session:
        replacement_challenge = session.get(BuyerOtpChallenge, UUID(replacement.json()["challenge_id"]))
        assert replacement_challenge.verification_sid == "VEnew"


@pytest.mark.parametrize(
    "status_code,body", [(404, {"code": 60000}), (404, None), (500, {"code": 20404})]
)
def test_twilio_unrelated_or_malformed_cancel_error_fails_closed(
    env, monkeypatch, status_code, body
):
    import app.services.buyer_otp as otp

    settings = env["settings"]
    settings.buyer_otp_external_sends_enabled = True
    settings.buyer_twilio_account_sid = "ACtest"
    settings.buyer_twilio_auth_token = SecretStr("test-token")
    settings.buyer_twilio_verify_service_sid = "VAtest"

    class Response:
        def __init__(self, status_code, payload): self.status_code, self.payload = status_code, payload
        def json(self):
            if self.payload is None:
                raise ValueError("not JSON")
            return self.payload

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data, auth):
            return Response(status_code, body)

    monkeypatch.setattr(otp.httpx, "Client", Client)
    with pytest.raises(OrderAPIError):
        otp._twilio(settings, "cancel", sid="VEold")


def test_twilio_missing_resource_during_check_remains_fail_closed(linked, monkeypatch):
    import app.services.buyer_otp as otp

    linked["settings"].buyer_otp_mode = "twilio"
    linked["settings"].buyer_otp_external_sends_enabled = True
    linked["settings"].buyer_twilio_account_sid = "ACtest"
    linked["settings"].buyer_twilio_auth_token = SecretStr("test-token")
    linked["settings"].buyer_twilio_verify_service_sid = "VAtest"

    class Response:
        def __init__(self, status_code, payload): self.status_code, self.payload = status_code, payload
        def json(self): return self.payload

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data, auth):
            if url.endswith("/VerificationCheck"):
                return Response(404, {"code": 20404})
            return Response(200, {"sid": "VEnew"})

    monkeypatch.setattr(otp.httpx, "Client", Client)
    started = linked["client"].post(linked["path"] + "/otp", json={})
    assert started.status_code == 200

    checked = linked["client"].post(linked["path"] + "/verify", json={"code": "123456"})

    assert checked.status_code == 503
    with linked["db"].sessions() as session:
        challenge = session.get(BuyerOtpChallenge, UUID(started.json()["challenge_id"]))
        link = session.scalar(select(ConfirmationLink))
        assert challenge.status == "PENDING" and challenge.attempts == 0
        assert link.failed_attempts == 0


def test_twilio_expired_challenge_is_cancelled_before_replacement(linked, monkeypatch):
    import app.services.buyer_otp as otp

    linked["settings"].buyer_otp_mode = "twilio"
    linked["settings"].buyer_otp_external_sends_enabled = True
    linked["settings"].buyer_twilio_account_sid = "ACtest"
    linked["settings"].buyer_twilio_auth_token = SecretStr("test-token")
    linked["settings"].buyer_twilio_verify_service_sid = "VAtest"
    calls = []

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data, auth):
            calls.append((url, data, auth))
            if url.endswith("/Verifications/VEold"):
                return Response({"status": "canceled"})
            return Response({"sid": "VEold" if len(calls) == 1 else "VEnew"})

    monkeypatch.setattr(otp.httpx, "Client", Client)
    started = linked["client"].post(linked["path"] + "/otp", json={})
    assert started.status_code == 200
    challenge_id = UUID(started.json()["challenge_id"])
    monkeypatch.setattr(otp, "utcnow", lambda: utcnow() + timedelta(minutes=6))

    replacement = linked["client"].post(linked["path"] + "/otp", json={})
    assert replacement.status_code == 200
    cancel_index = next(i for i, (url, _, _) in enumerate(calls) if url.endswith("/Verifications/VEold"))
    replacement_index = next(i for i, (url, _, _) in enumerate(calls) if url.endswith("/Verifications") and i > 0)
    assert cancel_index < replacement_index
    with linked["db"].sessions() as session:
        assert session.get(BuyerOtpChallenge, challenge_id).status == "REPLACED"


def test_twilio_cancellation_failure_revokes_local_challenge_and_keeps_cooldown(linked, monkeypatch):
    import app.services.buyer_otp as otp

    linked["settings"].buyer_otp_mode = "twilio"
    linked["settings"].buyer_otp_external_sends_enabled = True
    linked["settings"].buyer_twilio_account_sid = "ACtest"
    linked["settings"].buyer_twilio_auth_token = SecretStr("test-token")
    linked["settings"].buyer_twilio_verify_service_sid = "VAtest"

    class Response:
        def __init__(self, status_code, payload): self.status_code, self.payload = status_code, payload
        def json(self): return self.payload

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data, auth):
            if url.endswith("/Verifications/VEold"):
                return Response(500, {})
            return Response(200, {"sid": "VEold"})

    monkeypatch.setattr(otp.httpx, "Client", Client)
    first = linked["client"].post(linked["path"] + "/otp", json={})
    challenge_id = UUID(first.json()["challenge_id"])
    now = utcnow() + timedelta(seconds=61)
    monkeypatch.setattr(otp, "utcnow", lambda: now)
    assert linked["client"].post(linked["path"] + "/otp", json={}).status_code == 503
    assert linked["client"].post(linked["path"] + "/otp", json={}).status_code == 429
    with linked["db"].sessions() as session:
        challenge = session.get(BuyerOtpChallenge, challenge_id)
        assert challenge.status == "CANCEL_FAILED" and challenge.demo_code is None


def test_twilio_outage_fails_closed_and_production_rejects_demo(linked, monkeypatch):
    linked["settings"].buyer_otp_mode = "twilio"
    linked["settings"].buyer_otp_external_sends_enabled = True
    linked["settings"].buyer_twilio_account_sid = "ACtest"
    linked["settings"].buyer_twilio_auth_token = "test-token"
    linked["settings"].buyer_twilio_verify_service_sid = "VAtest"
    from app.core.order_errors import OrderAPIError
    monkeypatch.setattr(
        "app.services.buyer_otp._twilio",
        lambda *args, **kwargs: (_ for _ in ()).throw(OrderAPIError(503, "BUYER_OTP_UNAVAILABLE", "Phone verification is temporarily unavailable.")),
    )
    response = linked["client"].post(linked["path"] + "/otp", json={})
    assert response.status_code == 503 and "ACtest" not in response.text
    with pytest.raises(Exception):
        Settings(_env_file=None, environment="production")


@pytest.mark.parametrize(
    "code", ["", "123", "1234567", "၁၂٣٤٥٦", 123456, None, True, " 123456", "123456\n"]
)
def test_verification_input_validation(linked, code):
    assert (
        linked["client"].post(linked["path"] + "/verify", json={"code": code}).status_code
        == 422
    )
    with linked["db"].sessions() as session:
        assert session.scalar(select(ConfirmationLink)).failed_attempts == 0


def test_three_failed_attempts_lock_all_sessions(linked):
    start = linked["client"].post(linked["path"] + "/otp", json={})
    assert start.status_code == 200
    for _ in range(3):
        response = linked["client"].post(linked["path"] + "/verify", json={"code": "000000"})
        assert response.status_code == 403
        assert "0000" not in response.text and "4567" not in response.text
    assert (
        linked["client"].post(linked["path"] + "/verify", json={"code": "123456"}).status_code
        == 423
    )
    assert linked["client"].get(linked["path"]).json()["state"] == "LOCKED"
    assert (
        linked["client"].patch(linked["path"] + "/location", json=pin()).status_code
        == 423
    )
    with linked["db"].sessions() as session:
        assert session.scalar(select(ConfirmationLink)).failed_attempts == 3
        events = session.scalars(
            select(DeliveryEvent).where(DeliveryEvent.event_type == "BUYER_SECURITY")
        ).all()
        assert len(events) == 3
        assert all("last_four" not in str(row.event_metadata) for row in events)


def test_concurrent_failure_limit(linked):
    assert linked["client"].post(linked["path"] + "/otp", json={}).status_code == 200
    def attempt(_):
        with TestClient(linked["app"], client=("127.0.0.1", 50001)) as client:
            return client.post(linked["path"] + "/verify", json={"code": "000000"}).status_code

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
    auth = verified({**linked, "path": new_path})
    revoked = linked["client"].post(
        f"/api/orders/{linked['order']['id']}/confirmation-link/revoke", headers=ADMIN
    )
    assert revoked.status_code == 200
    assert linked["client"].get(new_path).status_code == 404
    assert (
        linked["client"]
            .get(new_path + "/details", headers=auth)
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
    current = utcnow()
    selected = window(current)
    selected_start = datetime.fromisoformat(selected["start"])
    with linked["db"].sessions.begin() as session:
        order = session.get(Order, UUID(linked["order"]["id"]))
        order.delivery_time_window = f"{selected_start.isoformat()}/{datetime.fromisoformat(selected['end']).isoformat()}"
        policy = session.get(BuyerEditPolicy, order.id)
        policy.cutoff_at = selected_start - timedelta(hours=1)
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


def test_atomic_request_initial_available_saves_requested_window_and_zero_edit_policy(linked, monkeypatch):
    auth = verified(linked)
    now = utcnow()
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: now)
    start = (now + timedelta(days=2)).replace(hour=5, minute=30, second=0, microsecond=0)
    body = {
        "request_id": str(uuid4()),
        "latitude": "16.8000000",
        "longitude": "96.1000000",
        "initial_pin_acknowledged": True,
        "action": "AVAILABLE",
        "time_window": {"start": start.isoformat(), "end": (start + timedelta(hours=2)).isoformat()},
        "instructions": "Call at the gate",
    }
    response = linked["client"].patch(linked["path"] + "/request", headers=auth, json=body)
    assert response.status_code == 200, response.text
    saved_order = saved(linked)
    assert saved_order["delivery_time_window"] == f"{start.isoformat()}/{(start + timedelta(hours=2)).isoformat()}"
    details = linked["client"].get(linked["path"] + "/details", headers=auth).json()
    assert details["delivery_time_window"] == saved_order["delivery_time_window"]
    assert details["policy"]["edit_count"] == 0
    assert details["policy"]["max_edits"] == 3
    assert details["policy"]["editable"] is True
    assert datetime.fromisoformat(details["policy"]["cutoff_at"]) == start - timedelta(hours=1)
    with linked["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(BuyerRequest)) == 2


def atomic_body(start, **extra):
    return {
        "request_id": str(uuid4()), "latitude": "16.8000000", "longitude": "96.1000000",
        "initial_pin_acknowledged": True, "action": "AVAILABLE",
        "time_window": {"start": start.isoformat(), "end": (start + timedelta(hours=2)).isoformat()},
        **extra,
    }


@pytest.mark.parametrize("stage", [OrderStatus.DRAFT, OrderStatus.NEEDS_REVIEW])
@pytest.mark.parametrize("minutes_before_eta", [960, 90, 30, -180])
def test_first_address_confirmation_ignores_edit_cutoff(
    env, monkeypatch, stage, minutes_before_eta
):
    start = (utcnow() + timedelta(days=1)).astimezone(
        timezone(timedelta(hours=6, minutes=30))
    ).replace(hour=10, minute=0, second=0, microsecond=0).astimezone(UTC)
    now = start - timedelta(minutes=minutes_before_eta)
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: now)
    created = env["client"].post(
        "/api/orders", headers=ADMIN,
        json={"structured": {
            "customer_name": "First confirmation buyer", "customer_phone": "09791234567",
            "township": "Hlaing", "street": "Private street", "cod_amount": "0",
        }, "parcel": {"item": "Test parcel", "delivery_day": start.date().isoformat()}},
    )
    assert created.status_code == 201, created.text
    order_id = UUID(created.json()["id"])
    with env["db"].sessions.begin() as session:
        session.get(Order, order_id).status = stage
    lookup = env["client"].post(
        "/api/confirm/lookup", json={"tracking_id": str(order_id), "phone": "09791234567"}
    )
    assert lookup.status_code == 200, lookup.text
    credentials = lookup.json()
    path = "/api/confirm/" + credentials["token"]
    auth = {"Authorization": "Bearer " + credentials["access_token"]}
    initial_policy = env["client"].get(path + "/details", headers=auth).json()["policy"]
    assert initial_policy["editable"] is True
    first = env["client"].patch(path + "/request", headers=auth, json=atomic_body(start))
    assert first.status_code == 200, first.text
    assert first.json()["editing_policy"]["edit_count"] == 0
    later = env["client"].patch(
        path + "/request", headers=auth, json=atomic_body(start, instructions="Later edit")
    )
    if minutes_before_eta > 60:
        assert later.status_code == 200, later.text
        assert later.json()["editing_policy"]["edit_count"] == 1
    else:
        assert later.status_code == 409, later.text
        assert later.json()["error"]["code"] == "BUYER_EDIT_CUTOFF_PASSED"


def test_address_edits_remain_open_inside_two_hour_notice_and_noop_costs_nothing(linked, monkeypatch):
    auth = verified(linked)
    now = utcnow()
    start = now + timedelta(hours=4)
    clock = [now]
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: clock[0])
    initial = atomic_body(start)
    client, path = linked["client"], linked["path"]
    assert client.patch(path + "/request", headers=auth, json=initial).status_code == 200
    duplicate = client.patch(path + "/request", headers=auth, json={**initial, "request_id": str(uuid4()), "latitude": "16.8"})
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["editing_policy"]["edit_count"] == 0
    with linked["db"].sessions.begin() as session:
        session.scalar(select(BuyerSession)).expires_at = start
    clock[0] = start - timedelta(minutes=90)
    edit = client.patch(path + "/request", headers=auth, json=atomic_body(start, longitude="96.1001000"))
    assert edit.status_code == 200, edit.text
    assert edit.json()["editing_policy"]["edit_count"] == 1
    clock[0] = start - timedelta(hours=1)
    denied = client.patch(path + "/request", headers=auth, json=atomic_body(start, longitude="96.1002000"))
    assert denied.status_code == 409, denied.text
    assert client.get(path + "/details", headers=auth).json()["policy"]["editable"] is False
    assert client.patch(path + "/response", headers=auth, json={"request_id": str(uuid4()), "action": "AVAILABLE"}).status_code == 409


@pytest.mark.parametrize("stage", [OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY])
def test_assigned_amendments_preserve_stage_and_require_independent_location_review(linked, stage):
    auth = verified(linked)
    start = utcnow() + timedelta(hours=4)
    client, path = linked["client"], linked["path"]
    assert client.patch(path + "/request", headers=auth, json=atomic_body(start)).status_code == 200
    def review_all():
        history = client.get(f"/api/orders/{linked['order']['id']}/buyer-requests", headers=ADMIN).json()["items"]
        for request in history:
            if request["decision"] == "REVIEW_REQUIRED" and request["resolution"] is None:
                result = client.patch(f"/api/orders/{linked['order']['id']}/buyer-requests/{request['id']}", headers=ADMIN,
                    json={"expected_version": saved(linked)["version"], "decision": "APPROVE", "reason": "Checked proposed delivery point and instructions"})
                assert result.status_code == 200, result.text
    review_all()
    with linked["db"].sessions.begin() as session:
        session.get(Order, UUID(linked["order"]["id"])).status = stage
    original = saved(linked)["latitude"]
    edit = client.patch(path + "/request", headers=auth, json=atomic_body(start, latitude="16.8001000"))
    assert edit.status_code == 200, edit.text
    assert saved(linked)["status"] == stage
    assert saved(linked)["latitude"] == original
    assert client.get(path + "/details", headers=auth).status_code == 200
    review_all()
    assert saved(linked)["status"] == stage
    assert Decimal(saved(linked)["latitude"]) == Decimal("16.8001000")


def test_atomic_request_caps_material_edits_and_readable_policy_after_cutoff(linked, monkeypatch):
    auth = verified(linked)
    now = utcnow()
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: now)
    start = (now + timedelta(days=2)).replace(hour=5, minute=30, second=0, microsecond=0)
    initial = {
        "request_id": str(uuid4()), "latitude": "16.8000000", "longitude": "96.1000000",
        "initial_pin_acknowledged": True, "action": "AVAILABLE",
        "time_window": {"start": start.isoformat(), "end": (start + timedelta(hours=2)).isoformat()},
    }
    first = linked["client"].patch(linked["path"] + "/request", headers=auth, json=initial)
    assert first.status_code == 200, first.text
    for index in range(3):
        body = {**initial, "request_id": str(uuid4()), "longitude": f"{96.1001 + index * 0.0001:.7f}", "instructions": f"Call {index}"}
        edit = linked["client"].patch(linked["path"] + "/request", headers=auth, json=body)
        assert edit.status_code == 200, edit.text
    fourth = linked["client"].patch(linked["path"] + "/request", headers=auth, json={**initial, "request_id": str(uuid4()), "longitude": "96.1010"})
    assert fourth.status_code == 409
    with linked["db"].sessions.begin() as session:
        session.scalar(select(BuyerSession)).expires_at = now + timedelta(days=3)
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: now + timedelta(days=2))
    detail = linked["client"].get(linked["path"] + "/details", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["policy"]["editable"] is False
    assert detail.json()["policy"]["reason"] in {"CUTOFF_PASSED", "EDITS_EXHAUSTED"}


def test_due_reminder_is_simulation_and_has_one_durable_order_claim(linked):
    from app.services.buyer_confirmation import YANGON
    from app.services.buyer_reminders import run_reminder_pass

    now = utcnow()
    start = (now + timedelta(hours=4)).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)
    scheduled = start - timedelta(minutes=90)
    with linked["db"].sessions.begin() as session:
        order = session.get(Order, UUID(linked["order"]["id"]))
        order.delivery_time_window = f"{start.isoformat()}/{end.isoformat()}"
        order.parsing_metadata = {**order.parsing_metadata, "parcel": {"delivery_day": start.astimezone(YANGON).date().isoformat()}}
        session.add(BuyerEditPolicy(order_id=order.id, edit_count=0, initial_submitted_at=now, cutoff_at=start - timedelta(hours=1), updated_at=now))

    class NoNetwork:
        def send(self, phone, message):
            raise AssertionError("local/test reminder must not call an external provider")

    result = run_reminder_pass(linked["db"], linked["settings"], provider=NoNetwork(), now=scheduled)
    again = run_reminder_pass(linked["db"], linked["settings"], provider=NoNetwork(), now=scheduled)
    assert result["simulation"] == 1
    assert again["simulation"] == 0
    with linked["db"].sessions() as session:
        rows = session.scalars(select(BuyerReminderOutbox)).all()
        assert len(rows) == 1
        assert rows[0].status == "SIMULATION"
        assert "3 delivery detail edits" in rows[0].message_body
        assert "Yangon time" in rows[0].message_body


@pytest.mark.parametrize("uncertain", [False, True])
def test_reminder_provider_claim_is_not_retried_and_warning_names_cutoff(linked, uncertain):
    from app.services.buyer_confirmation import YANGON
    from app.services.buyer_reminders import run_reminder_pass

    start = utcnow().astimezone(YANGON).replace(hour=12, minute=0, second=0, microsecond=0).astimezone(UTC)
    due = start - timedelta(minutes=90)
    with linked["db"].sessions.begin() as session:
        order = session.get(Order, UUID(linked["order"]["id"]))
        order.delivery_time_window = f"{start.isoformat()}/{(start + timedelta(hours=2)).isoformat()}"
        order.parsing_metadata = {"parcel": {"delivery_day": start.astimezone(YANGON).date().isoformat()}}
        session.add(BuyerEditPolicy(order_id=order.id, edit_count=1, initial_submitted_at=due-timedelta(days=1), cutoff_at=start-timedelta(hours=1), updated_at=due))
    linked["settings"].environment = "production"
    linked["settings"].buyer_reminder_external_sends_enabled = True
    calls = []
    class FakeProvider:
        def send(self, phone, message):
            calls.append((phone, message))
            if uncertain:
                raise TimeoutError("provider acceptance unknown")
            return "SM" + "a" * 32
    assert run_reminder_pass(linked["db"], linked["settings"], FakeProvider(), now=due-timedelta(seconds=1))["accepted"] == 0
    first = run_reminder_pass(linked["db"], linked["settings"], FakeProvider(), now=due)
    run_reminder_pass(linked["db"], linked["settings"], FakeProvider(), now=due+timedelta(minutes=1))
    assert len(calls) == 1
    assert "12:00–14:00" in calls[0][1] and "11:00 Yangon time" in calls[0][1]
    assert "up to 3" in calls[0][1] and "2 remain" in calls[0][1]
    assert first["accepted"] == (0 if uncertain else 1)
    with linked["db"].sessions() as session:
        assert session.get(BuyerReminderOutbox, UUID(linked["order"]["id"])).status == ("UNKNOWN" if uncertain else "ACCEPTED")


def test_atomic_concurrent_edits_do_not_exceed_three(linked):
    auth = verified(linked)
    start = utcnow()+timedelta(hours=4)
    assert linked["client"].patch(linked["path"]+"/request", headers=auth, json=atomic_body(start)).status_code == 200
    def amend(index):
        return linked["client"].patch(linked["path"]+"/request", headers=auth,
            json=atomic_body(start, instructions=f"Concurrent amendment {index}")).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(amend, range(4)))
    assert sorted(statuses) == [200, 200, 200, 409]
    assert linked["client"].get(linked["path"]+"/details", headers=auth).json()["policy"]["edit_count"] == 3


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
        ("verify", {"code": "123456"}),
    ):
        response = (linked["client"].post if suffix == "verify" else linked["client"].patch)(
            linked["path"] + "/" + suffix, headers=auth, json=body
        )
        if status in {"READY_FOR_DISPATCH", "ASSIGNED", "OUT_FOR_DELIVERY"}:
            assert response.status_code == (403 if suffix == "verify" else 409)
            assert saved(linked)["status"] == status
        else:
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
    assert linked["client"].get(linked["path"] + "/details", headers=auth).status_code == 401
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


def test_verification_rate_limit_even_with_correct_digits(linked, monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 22, 12, 0, tzinfo=tz or UTC)

    monkeypatch.setattr("app.core.buyer_access.datetime", FrozenDateTime)
    linked["settings"].buyer_verify_limit_per_minute = 1
    start = linked["client"].post(linked["path"] + "/otp", json={})
    assert start.status_code == 200
    with linked["db"].sessions() as session:
        code = session.get(BuyerOtpChallenge, UUID(start.json()["challenge_id"])).demo_code
    assert linked["client"].post(linked["path"] + "/verify", json={"code": code}).status_code == 429


def test_public_production_fail_closed_without_db(env):
    settings = Settings(
        _env_file=None,
        environment="production",
        order_management_enabled=True,
        buyer_otp_mode="twilio",
        buyer_otp_external_sends_enabled=True,
        buyer_twilio_account_sid="ACtest",
        buyer_twilio_auth_token="test-token",
        buyer_twilio_verify_service_sid="VAtest",
    )
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


@pytest.mark.parametrize("kind", ["LOCATION", "RESPONSE"])
@pytest.mark.parametrize("decision", ["APPROVE", "REJECT"])
@pytest.mark.parametrize("reason", [None, "", "ok"])
def test_review_reason_is_optional(linked, kind, decision, reason):
    auth = verified(linked)
    linked["client"].patch(linked["path"] + "/location", headers=auth,
                            json=pin(initial_pin_acknowledged=True))
    current = saved(linked)
    with linked["db"].sessions.begin() as session:
        row = session.scalar(select(BuyerRequest).where(BuyerRequest.order_id == UUID(current["id"])))
        if kind == "RESPONSE":
            row.kind = kind
            row.submitted_values = {"request_id": str(uuid4()), "action": "INSTRUCTIONS",
                                    "instructions": "Ring at the gate"}
        identifier = row.id
    body = {"expected_version": current["version"], "decision": decision}
    if reason is not None:
        body["reason"] = reason
    url = f"/api/orders/{current['id']}/buyer-requests/{identifier}"
    result = linked["client"].patch(url, headers=ADMIN, json=body)
    assert result.status_code == 200, result.text
    assert linked["client"].patch(url, headers=ADMIN, json=body).status_code == 200


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
    start = client.post(linked["path"] + "/otp", json={})
    with linked["db"].sessions() as session:
        code = session.get(BuyerOtpChallenge, UUID(start.json()["challenge_id"])).demo_code
    for _ in range(2):
        assert (
            client.post(linked["path"] + "/verify", json={"code": "000000"}).status_code == 403
        )
    assert client.post(linked["path"] + "/verify", json={"code": code}).status_code == 200
    start = client.post(linked["path"] + "/otp", json={})
    assert start.status_code == 200
    assert client.post(linked["path"] + "/verify", json={"code": "000000"}).status_code == 403
    assert client.post(linked["path"] + "/verify", json={"code": "123456"}).status_code == 423


def test_cutoff_boundary_exact_hour(linked, monkeypatch):
    auth = verified(linked)
    evening = (utcnow() + timedelta(days=1)).astimezone(
        timezone(timedelta(hours=6, minutes=30))
    ).replace(hour=18, minute=0, second=0, microsecond=0).astimezone(UTC)
    start = evening + timedelta(hours=18)  # Noon on the following delivery day.
    client, path = linked["client"], linked["path"]
    first = client.patch(path + "/request", headers=auth, json=atomic_body(start))
    assert first.status_code == 200, first.text
    with linked["db"].sessions.begin() as session:
        session.scalar(select(BuyerSession)).expires_at = start + timedelta(hours=1)
    clock = [evening]
    monkeypatch.setattr("app.services.buyer_confirmation.utcnow", lambda: clock[0])
    # Evening clock times on earlier days must not close tomorrow's delivery edits.
    previous_day = client.patch(
        path + "/request", headers=auth, json=atomic_body(start, instructions="Previous day")
    )
    assert previous_day.status_code == 200, previous_day.text
    clock[0] = start - timedelta(minutes=61)
    before = client.patch(
        path + "/request", headers=auth, json=atomic_body(start, instructions="Before cutoff")
    )
    assert before.status_code == 200, before.text
    clock[0] = start - timedelta(hours=1)
    closed = client.patch(
        path + "/request", headers=auth, json=atomic_body(start, instructions="At cutoff")
    )
    assert closed.status_code == 409, closed.text
    assert closed.json()["error"]["code"] == "BUYER_EDIT_CUTOFF_PASSED"


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


def test_buyer_lookup_by_tracking_id_and_phone(linked):
    order_id = linked["order"]["id"]
    short_id = f"LP-{str(order_id)[:6].upper()}"

    # Lookup by short prefix (LP-XXXXXX)
    res = linked["client"].post(
        "/api/confirm/lookup",
        json={"tracking_id": short_id, "phone": "09791234567"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["order_reference"] == order_id
    assert data["token_type"] == "Bearer"
    assert "access_token" in data
    assert "token" in data
    details = linked["client"].get(
        f"/api/confirm/{data['token']}/details",
        headers={"Authorization": "Bearer " + data["access_token"]},
    )
    assert details.status_code == 200, details.text

    # Lookup by full UUID with formatted +959 phone
    res2 = linked["client"].post(
        "/api/confirm/lookup",
        json={"tracking_id": order_id, "phone": "+95 9 791234567"},
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["order_reference"] == order_id
    second = res2.json()
    details = linked["client"].get(
        f"/api/confirm/{second['token']}/details",
        headers={"Authorization": "Bearer " + second["access_token"]},
    )
    assert details.status_code == 200, details.text

    # Lookup with wrong phone fails with 404
    res_wrong = linked["client"].post(
        "/api/confirm/lookup",
        json={"tracking_id": short_id, "phone": "09799999999"},
    )
    assert res_wrong.status_code == 404

    # Lookup with nonexistent tracking ID fails with 404
    res_unknown = linked["client"].post(
        "/api/confirm/lookup",
        json={"tracking_id": "LP-000000", "phone": "09791234567"},
    )
    assert res_unknown.status_code == 404

