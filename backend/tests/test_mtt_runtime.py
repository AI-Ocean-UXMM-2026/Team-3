from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import utcnow
from app.services.buyer_confirmation import YANGON
from tools.integrated_workspace import WorkspaceSandbox, application


def test_live_runtime_is_explicit_private_no_store_and_has_real_ui_assets():
    with TestClient(
        application(temporary=True),
        base_url="http://127.0.0.1:8780",
        client=("127.0.0.1", 53100),
    ) as client:
        assert client.get("/api/orders").status_code == 404
        runtime = client.get("/runtime-config.js")
        assert "LIVE_BACKEND" in runtime.text
        assert runtime.headers["cache-control"] == "no-store"
        assert "style-src-attr 'unsafe-inline'" in runtime.headers["content-security-policy"]
        assert "script-src 'self';" in runtime.headers["content-security-policy"]
        assert "secret" not in runtime.text.lower()
        root = client.get("/").text
        for asset in ("live-bootstrap.js", "customer-map.js", "runtime-config.js"):
            assert asset in root
        assert client.get("/js/live-store.mjs").status_code == 200
        assert "DEMO_SIMULATION" in client.get("/demo-config.js").text
        assert "demo-config.js" in client.get("/prototype.html").text
        assert client.get("/backend/.env").status_code == 404


def test_runtime_rejects_remote_peers_and_host_spoofing():
    with TestClient(
        application(temporary=True),
        base_url="http://127.0.0.1:8780",
        client=("198.51.100.2", 53100),
    ) as client:
        assert client.get("/runtime-config.js").status_code == 403
    with TestClient(
        application(temporary=True),
        base_url="http://127.0.0.1:8780",
        client=("127.0.0.1", 53100),
    ) as client:
        assert (
            client.get("/runtime-config.js", headers={"Host": "example.invalid"}).status_code == 403
        )


def test_mtt_cod_delivery_pin_and_audit_persist_after_application_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(WorkspaceSandbox, "storage_directory", lambda self: tmp_path)

    def connect(client):
        client.get("/")
        bootstrap = client.get("/dashboard/bootstrap").json()
        client.headers["X-Dashboard-CSRF"] = bootstrap["csrf"]

    def call(client, method, path, body=None, **actor):
        result = client.post(
            "/dashboard/api", json={"method": method, "path": path, "body": body, **actor}
        )
        assert result.status_code < 300, result.json()
        return result.json()["data"]

    with TestClient(
        application(), base_url="http://127.0.0.1:8780", client=("127.0.0.1", 53100)
    ) as client:
        connect(client)
        order = call(
            client,
            "POST",
            "/api/orders",
            {
                "raw_text": "Fictional QA buyer, 09790000000, Hlaing, COD 25000",
                "parcel": {
                    "item": "Synthetic shirt",
                    "delivery_day": utcnow().astimezone(YANGON).date().isoformat(),
                    "hub_received": True,
                },
            },
        )
        identifier = order["id"]
        path = f"/api/orders/{identifier}"
        call(client, "PATCH", path + "/status", {"expected_version": 1, "status": "NEEDS_REVIEW"})
        handle = call(client, "POST", path + "/confirmation-link")["buyer_handle"]
        call(client, "POST", "/api/confirm/@buyer/otp", {}, buyer_handle=handle)
        code = client.get("/dashboard/buyer-otp", params={"buyer_handle": handle}).json()["code"]
        call(
            client,
            "POST",
            "/api/confirm/@buyer/verify",
            {"code": code},
            buyer_handle=handle,
        )
        call(
            client,
            "PATCH",
            "/api/confirm/@buyer/location",
            {
                "request_id": str(uuid4()),
                "latitude": "0",
                "longitude": "0",
                "initial_pin_acknowledged": True,
            },
            buyer_handle=handle,
        )
        pending = call(client, "GET", path + "/buyer-requests")["items"][0]
        current = call(client, "GET", path)
        call(
            client,
            "PATCH",
            path + "/buyer-requests/" + pending["id"],
            {
                "expected_version": current["version"],
                "decision": "APPROVE",
                "reason": "Synthetic location; no claim of a real customer home",
            },
        )
        rider = call(client, "GET", "/api/riders")["items"][0]
        current = call(client, "GET", path)
        prepared = call(
            client,
            "POST",
            path + "/prepare-assignment",
            {
                "request_id": str(uuid4()),
                "expected_version": current["version"],
                "rider_id": rider["id"],
                "acknowledge_unverified_location": True,
            },
        )
        route = prepared["route"]
        call(
            client,
            "POST",
            f"/api/routes/{route['id']}/actions",
            {
                "request_id": str(uuid4()),
                "expected_version": route["version"],
                "action": "DISPATCH",
            },
        )
        current = call(client, "GET", path)
        call(
            client,
            "PATCH",
            f"/api/riders/{rider['id']}/deliveries/{identifier}/status",
            {
                "request_id": str(uuid4()),
                "expected_version": current["version"],
                "action": "DELIVERED",
                "cod_collected": True,
                "actual_amount": 25000,
            },
            actor="rider",
            rider_id=rider["id"],
        )
        first_events = call(client, "GET", path + "/events")["total"]
    with TestClient(
        application(), base_url="http://127.0.0.1:8780", client=("127.0.0.1", 53101)
    ) as client:
        connect(client)
        saved = call(client, "GET", path)
        assert saved["status"] == "DELIVERED"
        assert saved["parsing_metadata"]["parcel"]["collection"]["actual"] == 25000
        assert saved["latitude"] == "0E-7"
        assert saved["confidence_level"] == "AMBER"
        assert call(client, "GET", path + "/events")["total"] == first_events
