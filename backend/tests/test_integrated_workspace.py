import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tools.integrated_workspace import WorkspaceSandbox, application

ORIGIN = "http://127.0.0.1:8780"


def boot(client):
    assert client.get("/").status_code == 200
    result = client.get("/dashboard/bootstrap").json()
    client.headers["X-Dashboard-CSRF"] = result["csrf"]
    return result


def call(client, method, path, body=None, **extra):
    return client.post(
        "/dashboard/api", json={"method": method, "path": path, "body": body, **extra}
    )


def test_persistent_workspace_and_native_buyer_capability_survive_restart(tmp_path, monkeypatch):
    directory = tmp_path / "persistent-workspace"
    directory.mkdir()
    monkeypatch.setattr(WorkspaceSandbox, "storage_directory", lambda self: directory)
    first = application()
    with TestClient(first, base_url=ORIGIN, client=("127.0.0.1", 53100)) as client:
        initial = boot(client)
        created = call(
            client,
            "POST",
            "/api/orders",
            {
                "merchant_id": initial["merchant_id"],
                "raw_text": "09790000000, Hlaing, COD 25000",
            },
        ).json()["data"]
        response = call(
            client,
            "PATCH",
            f"/api/orders/{created['id']}/status",
            {
                "expected_version": created["version"],
                "status": "NEEDS_REVIEW",
            },
        )
        assert response.status_code == 200
        link = call(client, "POST", f"/api/orders/{created['id']}/confirmation-link").json()["data"]
        handle = link["buyer_handle"]
        assert "confirmation_url" not in link
    assert directory.exists()  # A persistent workspace never resets user data on exit.
    assert handle.encode() not in (directory / "sandbox.sqlite3").read_bytes()
    second = application()
    with TestClient(second, base_url=ORIGIN, client=("127.0.0.1", 53101)) as client:
        later = boot(client)
        assert initial["merchant_id"] == later["merchant_id"]
        saved = call(client, "GET", f"/api/orders/{created['id']}").json()["data"]
        assert saved["original_message"] == "09790000000, Hlaing, COD 25000"
        assert saved["status"] == "NEEDS_REVIEW"
        assert call(client, "GET", "/api/confirm/@buyer", buyer_handle=handle).status_code == 200
        assert (
            call(client, "GET", "/api/confirm/@buyer/details", buyer_handle=handle).status_code
            == 401
        )
        verified = call(
            client, "POST", "/api/confirm/@buyer/verify", {"last_four": "0000"}, buyer_handle=handle
        )
        assert verified.status_code == 200
        assert "access_token" not in json.dumps(verified.json())
        assert (
            call(client, "GET", "/api/confirm/@buyer/details", buyer_handle=handle).status_code
            == 200
        )
        assert (
            client.post("/dashboard/reset", json={"confirm": "RESET FICTIONAL DATA"}).status_code
            == 409
        )
        assert call(client, "GET", "/api/orders").json()["data"]["total"] == 1


@pytest.mark.parametrize("value", ["../normal-db", "", "a/b", "a" * 65])
def test_workspace_cannot_select_arbitrary_storage(value):
    with pytest.raises(ValueError):
        WorkspaceSandbox(value)


def test_workspace_factory_fails_closed_in_production(monkeypatch):
    monkeypatch.setenv("LANNPYA_ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="disabled in production"):
        application()


def test_workspace_unauthenticated_proxy_cannot_read_orders():
    with TestClient(
        application(temporary=True), base_url=ORIGIN, client=("127.0.0.1", 53100)
    ) as client:
        assert call(client, "GET", "/api/orders").status_code == 401
        boot(client)
        denied = client.post(
            "/dashboard/api",
            json={
                "method": "PATCH",
                "path": f"/api/orders/{uuid4()}",
                "body": {"expected_version": 1, "street": "Unauthorized"},
            },
            headers={"X-Dashboard-CSRF": "invalid"},
        )
        assert denied.status_code == 403
