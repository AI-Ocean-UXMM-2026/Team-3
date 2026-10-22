from uuid import uuid4

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.order_errors import OrderAPIError
from app.core.supabase_auth import verify_user
from app.db.migrations import upgrade_database
from app.db.models import User
from app.db.session import Database
from app.domain.lifecycle import UserRole
from app.main import create_app


@pytest.fixture
def secure(tmp_path):
    db = Database(f"sqlite+pysqlite:///{tmp_path / 'auth.sqlite3'}")
    upgrade_database(db)
    user_id = uuid4()
    with db.sessions.begin() as session:
        session.add(
            User(
                id=user_id,
                name="Dispatcher",
                email="dispatch@example.com",
                role=UserRole.DISPATCHER,
            )
        )
    settings = Settings(
        _env_file=None,
        environment="production",
        order_management_enabled=True,
        supabase_auth_enabled=True,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
    )
    app = create_app(settings, database=db)
    with TestClient(app, client=("203.0.113.1", 5000)) as client:
        yield client, user_id
    db.dispose()


def test_production_requires_bearer_even_with_dev_token(secure):
    client, _ = secure
    response = client.get("/api/session", headers={"X-Dev-Access-Token": "x" * 40})
    assert response.status_code == 401


def test_verified_subject_maps_to_server_database_role(secure, monkeypatch):
    client, user_id = secure
    monkeypatch.setattr("app.core.supabase_auth.verify_user", lambda *_: user_id)
    response = client.get("/api/session", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    assert response.json()["role"] == "Dispatcher"
    assert response.json()["local_only"] is False


def test_unknown_account_never_becomes_dispatcher(secure, monkeypatch):
    client, _ = secure
    monkeypatch.setattr("app.core.supabase_auth.verify_user", lambda *_: uuid4())
    response = client.get("/api/session", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 403


def test_unconfigured_auth_fails_closed():
    with pytest.raises(ValueError, match="Supabase"):
        Settings(_env_file=None, supabase_auth_enabled=True)


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {}, 401),
        (503, {}, 503),
        (200, {"id": str(uuid4()), "email_confirmed_at": None}, 403),
        (200, {"id": "invalid", "email_confirmed_at": "verified"}, 503),
    ],
)
def test_provider_rejects_invalid_expired_unverified_and_malformed_users(
    monkeypatch, status, body, expected
):
    real_client = httpx.Client

    def handler(request):
        assert request.url.path == "/auth/v1/user"
        assert request.headers["Authorization"] == "Bearer untrusted"
        return httpx.Response(status, json=body)

    monkeypatch.setattr(
        "app.core.supabase_auth.httpx.Client",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
    )
    with pytest.raises(OrderAPIError) as error:
        verify_user(settings, "untrusted")
    assert error.value.status == expected


def test_rider_cannot_read_dispatcher_orders(secure, monkeypatch):
    client, user_id = secure
    with client.app.state.database.sessions.begin() as session:
        session.get(User, user_id).role = UserRole.RIDER
    monkeypatch.setattr("app.core.supabase_auth.verify_user", lambda *_: user_id)
    response = client.get("/api/orders", headers={"Authorization": "Bearer rider"})
    assert response.status_code == 403


def test_private_supabase_keys_are_rejected_before_serving_them():
    with pytest.raises(ValueError, match="publishable"):
        Settings(
            _env_file=None,
            supabase_auth_enabled=True,
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="sb_secret_never_public",
        )
