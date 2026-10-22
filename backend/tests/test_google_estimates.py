"""Local SQLite + mock HTTP only; real private credentials are never loaded."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import httpx2 as httpx
import pytest
from pydantic import SecretStr
from test_three_role_workflow import assign, manual, save
from test_three_role_workflow import workspace as source_workspace

from app.db.models import Order, User
from app.routing.base import RoutingFailure
from app.schemas.routing import GoogleEstimateQuery
from app.services import google_estimates as service


@pytest.fixture
def workspace(tmp_path):
    yield from source_workspace.__wrapped__(tmp_path)


@pytest.fixture
def configured(workspace, tmp_path):
    clients, _, _ = workspace
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url).endswith("/directions/v2:computeRoutes")
        body = json.loads(request.content)
        assert body["travelMode"] == "DRIVE"
        assert body["routingPreference"] == "TRAFFIC_UNAWARE"
        assert "origins" not in body and "trafficModel" not in body
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "distanceMeters": 1741,
                        "duration": "405s",
                        "polyline": {
                            "geoJsonLinestring": {
                                "type": "LineString",
                                "coordinates": [
                                    [96.13, 16.825],
                                    [96.125, 16.815],
                                ],
                            },
                        },
                    }
                ]
            },
        )

    for client in clients.values():
        client.app.state.settings = client.app.state.settings.model_copy(
            update={
                "google_demo_enabled": True,
                "google_demo_max_requests": 2,
                "google_demo_budget_directory": tmp_path / "budget",
                "routing_external_requests_enabled": True,
                "google_routes_api_key": SecretStr("fictional-test-key-only"),
            }
        )
        client.app.state.google_demo_transport_override = httpx.MockTransport(handler)
    return clients, calls


def query(order, **changes):
    return {
        "order_id": order["id"],
        "origin": {"latitude": 16.825, "longitude": 96.13},
        "request_id": str(uuid4()),
        "authorize_external_request": True,
        **changes,
    }


def test_disabled_by_default_never_loads_key(workspace, monkeypatch):
    c, _, _ = workspace
    monkeypatch.setattr(service, "key_for", lambda s: pytest.fail("No key load while disabled"))
    assert save(c["admin"].get("/api/routes/google-demo/status"))["enabled"] is False
    order = manual(workspace)
    r = c["admin"].post("/api/routes/google-demo", json=query(order))
    assert r.status_code == 503 and r.json()["error"]["code"] == "GOOGLE_DEMO_DISABLED"


def test_google_estimate_is_mock_labelled_ephemeral_and_leaves_optimizer_offline(
    workspace, configured
):
    c, calls = configured
    order = manual(workspace)
    result = save(c["admin"].post("/api/routes/google-demo", json=query(order)))
    assert result["observation"] == "GOOGLE_MOCK"
    assert result["route"]["distance_meters"] == 1741
    assert result["route"]["duration_seconds"] == 405
    assert len(calls) == 1
    assert c["admin"].app.state.settings.routing_provider == "offline"
    assert save(c["admin"].get("/api/orders/" + order["id"])) == order
    assert save(c["admin"].get("/api/routes/google-demo/status"))["remaining_requests"] == 1
    assert "fictional-test-key-only" not in json.dumps(result)


def test_duplicate_nonce_and_global_budget_survive_new_settings(workspace, configured):
    c, calls = configured
    order = manual(workspace)
    body = query(order)
    save(c["admin"].post("/api/routes/google-demo", json=body))
    assert c["admin"].post("/api/routes/google-demo", json=body).status_code == 409
    save(c["admin"].post("/api/routes/google-demo", json=query(order)))
    c["admin"].app.state.settings = c["admin"].app.state.settings.model_copy()
    assert c["admin"].post("/api/routes/google-demo", json=query(order)).status_code == 429
    assert len(calls) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"authorize_external_request": False},
        {"authorize_external_request": 1},
        {"origin": {"latitude": 91.0, "longitude": 96.0}},
        {"order_id": "invalid"},
        {"request_id": "invalid"},
        {"mode": "TWO_WHEELER"},
    ],
)
def test_invalid_requests_do_not_reserve_or_call(workspace, configured, change):
    c, calls = configured
    r = c["admin"].post("/api/routes/google-demo", json=query(manual(workspace), **change))
    assert r.status_code == 422 and calls == []


def test_missing_and_unreviewed_pins_rejected(workspace, configured):
    c, calls = configured
    order = manual(workspace, coordinates=False)
    assert c["admin"].post("/api/routes/google-demo", json=query(order)).status_code == 409
    order = manual(workspace)
    with workspace[2].sessions.begin() as session:
        record = session.get(Order, UUID(order["id"]))
        record.field_sources = {
            **record.field_sources,
            "latitude": {"method": "buyer_confirmation", "requires_review": True},
        }
    assert c["admin"].post("/api/routes/google-demo", json=query(order)).status_code == 409
    assert calls == []


def test_rider_must_have_current_assignment(workspace, configured):
    c, calls = configured
    order = manual(workspace)
    assert c["rider"].post("/api/routes/google-demo", json=query(order)).status_code == 403
    assign(workspace, order)
    save(c["rider"].post("/api/routes/google-demo", json=query(order)))
    assert c["other"].post("/api/routes/google-demo", json=query(order)).status_code == 403
    assert len(calls) == 1


def test_unauthorized_api_access_rejected(workspace, configured):
    c, calls = configured
    order = manual(workspace)
    assert (
        c["admin"]
        .post("/api/routes/google-demo", json=query(order), headers={"X-Dev-Access-Token": ""})
        .status_code
        == 401
    )
    assert calls == []


def test_provider_rejection_consumes_budget_without_retry(workspace, configured):
    c, calls = configured
    order = manual(workspace)

    def reject(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "never expose provider internals"}})

    c["admin"].app.state.google_demo_transport_override = httpx.MockTransport(reject)
    c["admin"].app.state.settings.google_demo_max_requests = 1
    r = c["admin"].post("/api/routes/google-demo", json=query(order))
    assert r.status_code == 429 and "provider internals" not in r.text
    assert c["admin"].post("/api/routes/google-demo", json=query(order)).status_code == 429
    assert len(calls) == 1


def test_concurrent_reservations_cannot_exceed_shared_budget(workspace, configured):
    settings = configured[0]["admin"].app.state.settings

    def attempt(_):
        try:
            service.reserve(settings, uuid4())
            return "reserved"
        except RoutingFailure as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count("reserved") == 2
    assert service.status(settings)["remaining_requests"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"routing_external_requests_enabled": False},
        {"google_demo_max_requests": 0},
        {"environment": "production"},
    ],
)
def test_independent_gates_fail_closed(workspace, configured, change, monkeypatch):
    c, calls = configured
    order = manual(workspace)
    settings = c["admin"].app.state.settings.model_copy(update=change)
    assert service.enabled(settings) is False
    monkeypatch.setattr(service, "key_for", lambda s: pytest.fail("Disabled gate read credentials"))
    with workspace[2].sessions() as session:
        actor = session.get(User, workspace[1]["admin"])

        with pytest.raises(RoutingFailure, match="GOOGLE_DEMO_DISABLED"):
            service.estimate(
                session, actor, settings, GoogleEstimateQuery.model_validate(query(order))
            )
    assert calls == []
