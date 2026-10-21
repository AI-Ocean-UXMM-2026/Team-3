import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import BACKEND_ROOT, Database
from app.main import create_app


def contract():
    snapshot = BACKEND_ROOT.parent / "docs" / "integration" / "OPENAPI.json"
    return json.loads(snapshot.read_text(encoding="utf-8"))


def test_checked_in_openapi_is_generated_from_the_application():
    app = create_app(Settings(_env_file=None, order_management_enabled=False))
    assert app.openapi() == contract()
    prior_snapshot = BACKEND_ROOT.parent / "docs" / "OPENAPI.json"
    assert json.loads(prior_snapshot.read_text(encoding="utf-8")) == contract()
    assert sum(len(methods) for methods in app.openapi()["paths"].values()) == 35


def test_health_and_actual_parse_match_openapi_response_contract():
    schema = contract()
    with TestClient(create_app(Settings(_env_file=None, order_management_enabled=False))) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": "LannPya AI"}
        assert set(health.json()) == set(
            schema["components"]["schemas"]["HealthResponse"]["properties"]
        )

        missing = client.post("/api/orders/parse", json={})
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "VALIDATION_ERROR"

        parsed = client.post("/api/orders/parse", json={"raw_text": "Hlaing Township COD 25000"})
        assert parsed.status_code == 200
        assert parsed.json()["address"]["township"] == "Hlaing"
        assert parsed.json()["address"]["cod_amount"] == 25000
        assert parsed.json()["confidence"] == "RED"  # No phone, so review is required.
        assert set(parsed.json()) == set(
            schema["components"]["schemas"]["ParseResponse"]["properties"]
        )


def test_private_order_and_rider_routes_fail_closed_without_credentials(tmp_path):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'contract.sqlite3'}")
    upgrade_database(database)
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            order_management_enabled=True,
            dev_access_token="contract-test-token-" + "x" * 40,
            dev_actor_id=uuid4(),
        ),
        database=database,
    )
    with TestClient(app, client=("127.0.0.1", 52341)) as client:
        for method, path, body in (
            ("get", "/api/orders", None),
            ("post", "/api/orders", {"merchant_id": str(uuid4()), "raw_text": "test"}),
            ("get", f"/api/riders/{uuid4()}/queue", None),
        ):
            request = getattr(client, method)
            response = request(path, json=body) if body else request(path)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "DEV_ACCESS_REQUIRED"

        # Invalid buyer capabilities are handled as public link errors, without an order leak.
        response = client.get("/api/confirm/invalid-capability")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CONFIRMATION_UNAVAILABLE"
    database.dispose()
