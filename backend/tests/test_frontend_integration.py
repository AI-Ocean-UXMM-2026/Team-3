import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import BACKEND_ROOT, Database
from app.main import create_app
from scripts.demo_mvp import LocalDemo, approved_origin, fixtures

ORIGIN = "http://localhost:61234"


def local_app(**changes):
    if changes.get("environment") == "production":
        changes.setdefault("buyer_otp_mode", "twilio")
        changes.setdefault("buyer_otp_external_sends_enabled", True)
        changes.setdefault("buyer_twilio_account_sid", "ACsynthetic-test-only")
        changes.setdefault("buyer_twilio_auth_token", "synthetic-test-only")
        changes.setdefault("buyer_twilio_verify_service_sid", "VAsynthetic-test-only")
    return create_app(Settings(_env_file=None, cors_origins=[ORIGIN], **changes))


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/orders/parse", "POST"),
        ("/api/orders", "POST"),
        (f"/api/orders/{uuid4()}", "PATCH"),
        ("/api/confirm/demo/verify", "POST"),
        ("/api/confirm/demo/location", "PATCH"),
        (f"/api/riders/{uuid4()}/queue", "GET"),
    ],
)
def test_custom_local_port_preflights_without_credentials(path, method):
    with TestClient(local_app()) as client:
        response = client.options(
            path,
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type,x-dev-access-token,authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    "origin", ["https://unapproved.example.invalid", "null", "http://localhost:61235"]
)
def test_unapproved_origins_cannot_complete_preflight(origin):
    with TestClient(local_app()) as client:
        response = client.options(
            "/api/orders", headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_unexpected_errors_remain_readable_to_browser_and_private(monkeypatch, caplog):
    from app.services.hybrid import HybridOrderParsingService

    async def failed(*args, **kwargs):
        raise RuntimeError("private customer and credential")

    monkeypatch.setattr(HybridOrderParsingService, "parse", failed)
    with TestClient(local_app()) as client:
        response = client.post(
            "/api/orders/parse", headers={"Origin": ORIGIN}, json={"raw_text": "demo"}
        )
    assert response.status_code == 500 and response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private customer" not in response.text + caplog.text


def test_retry_after_is_exposed_on_real_rate_limit(tmp_path):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'rate.sqlite3'}")
    upgrade_database(database)
    app = create_app(
        Settings(
            _env_file=None,
            cors_origins=[ORIGIN],
            environment="test",
            order_management_enabled=True,
            buyer_request_limit_per_minute=1,
        ),
        database=database,
    )
    try:
        with TestClient(app) as client:
            assert client.get("/api/confirm/invalid", headers={"Origin": ORIGIN}).status_code == 404
            response = client.get("/api/confirm/invalid", headers={"Origin": ORIGIN})
            assert response.status_code == 429
            assert response.headers["retry-after"] == "60"
            assert "retry-after" in response.headers["access-control-expose-headers"].lower()
            assert response.headers["access-control-allow-origin"] == ORIGIN
    finally:
        database.dispose()


def test_unauthorized_errors_cors_and_production_fail_closed(tmp_path):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'auth.sqlite3'}")
    app = create_app(
        Settings(
            _env_file=None,
            cors_origins=[ORIGIN],
            environment="test",
            order_management_enabled=True,
            dev_access_token="test-only-secret-" + "x" * 32,
            dev_actor_id=uuid4(),
        ),
        database=database,
    )
    try:
        with TestClient(app, client=("127.0.0.1", 50000)) as client:
            response = client.get("/api/orders", headers={"Origin": ORIGIN})
            assert (
                response.status_code == 401
                and response.headers["access-control-allow-origin"] == ORIGIN
            )
            assert response.headers["cache-control"] == "no-store"
        with TestClient(
            local_app(environment="production", order_management_enabled=True)
        ) as client:
            assert client.get("/api/orders").status_code == 503
            assert client.get("/api/confirm/invalid").status_code == 503
    finally:
        database.dispose()


def test_exported_openapi_and_handoff_cover_all_operations():
    schema = local_app().openapi()
    exported = json.loads(
        (BACKEND_ROOT.parent / "docs" / "OPENAPI.json").read_text(encoding="utf-8")
    )
    assert schema == exported
    handoff = (BACKEND_ROOT.parent / "docs" / "FRONTEND_HANDOFF.md").read_text(encoding="utf-8")
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            assert f"`{method.upper()} {path}`" in handoff
            success = operation["responses"].get("200") or operation["responses"].get("201")
            assert success["content"]["application/json"]["schema"]


def test_demo_inputs_are_deterministic_unverified_and_rules_based():
    with TestClient(local_app()) as client:
        for name, raw in fixtures().items():
            data = client.post("/api/orders/parse", json={"raw_text": raw}).json()
            assert data["original_text"] == raw and not data["is_mock"]
            assert data["confidence"] == ("RED" if name.startswith("red_") else "AMBER")
            assert data["location_verification"]["status"] == "unverified"


def test_demo_refuses_production_and_preserves_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("LANNPYA_ENVIRONMENT", "production")
    monkeypatch.setenv("LANNPYA_BUYER_OTP_MODE", "twilio")
    monkeypatch.setenv("LANNPYA_BUYER_OTP_EXTERNAL_SENDS_ENABLED", "true")
    monkeypatch.setenv("LANNPYA_BUYER_TWILIO_ACCOUNT_SID", "ACsynthetic-test-only")
    monkeypatch.setenv("LANNPYA_BUYER_TWILIO_AUTH_TOKEN", "synthetic-test-only")
    monkeypatch.setenv("LANNPYA_BUYER_TWILIO_VERIFY_SERVICE_SID", "VAsynthetic-test-only")
    with pytest.raises(RuntimeError, match="disabled"):
        LocalDemo()
    monkeypatch.setenv("LANNPYA_ENVIRONMENT", "test")
    for name in (
        "LANNPYA_BUYER_OTP_MODE",
        "LANNPYA_BUYER_OTP_EXTERNAL_SENDS_ENABLED",
        "LANNPYA_BUYER_TWILIO_ACCOUNT_SID",
        "LANNPYA_BUYER_TWILIO_AUTH_TOKEN",
        "LANNPYA_BUYER_TWILIO_VERIFY_SERVICE_SID",
    ):
        monkeypatch.delenv(name)
    monkeypatch.setattr("scripts.demo_mvp.BACKEND_ROOT", tmp_path)
    first, second = LocalDemo(), LocalDemo()
    try:
        assert first.directory != second.directory
        assert Path(first.directory / "demo.sqlite3").is_file()
        assert Path(second.directory / "demo.sqlite3").is_file()
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "origin", ["http://public.example.invalid", "http://localhost:3000/path", "file:///demo"]
)
def test_demo_only_accepts_exact_local_frontend_origins(origin):
    with pytest.raises(ValueError):
        approved_origin(origin)
