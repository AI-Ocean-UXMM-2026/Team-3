import hashlib
import json
import logging
import re
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError

from app.ai.extraction import AddressExtractionProvider, ExtractionUnavailableError
from app.db.models import DeliveryEvent, Order
from app.db.session import BACKEND_ROOT, Database
from tools.backend_test_dashboard.server import STATIC, create_dashboard

ORIGIN = "http://127.0.0.1:8765"
RAW = "09790000000, Hlaing township, Demo Street, COD 25000 MMK, Fictional test only."


@pytest.fixture
def dashboard():
    app = create_dashboard()
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 55000)) as client:
        assert client.get("/").status_code == 200
        boot = client.get("/dashboard/bootstrap").json()
        client.headers["X-Dashboard-CSRF"] = boot["csrf"]
        yield client, app.state.sandbox, boot


def call(client, method, path, body=None, status=200, **kwargs):
    response = client.post(
        "/dashboard/api", json={"method": method, "path": path, "body": body, **kwargs}
    )
    assert response.status_code == status, response.text
    return response.json().get("data", response.json())


def order(client, boot):
    return call(
        client, "POST", "/api/orders", {"merchant_id": boot["merchant_id"], "raw_text": RAW}, 201
    )


def transition(client, identifier, status):
    row = call(client, "GET", f"/api/orders/{identifier}")
    return call(
        client,
        "PATCH",
        f"/api/orders/{identifier}/status",
        {
            "expected_version": row["version"],
            "status": status,
            "acknowledge_unverified_location": True,
        },
    )


def link(client, identifier):
    transition(client, identifier, "NEEDS_REVIEW")
    return call(client, "POST", f"/api/orders/{identifier}/confirmation-link", status=201)


def buyer(client, handle, method="GET", suffix="", body=None, status=200):
    if method == "POST" and suffix == "/verify" and body and "last_four" in body:
        demo = client.get("/dashboard/buyer-otp", params={"buyer_handle": handle})
        if demo.status_code != 200:
            if buyer(client, handle).get("state") == "LOCKED":
                return call(client, method, "/api/confirm/@buyer" + suffix, {"code": "000000"}, status, buyer_handle=handle)
            call(client, "POST", "/api/confirm/@buyer/otp", {}, buyer_handle=handle)
            demo = client.get("/dashboard/buyer-otp", params={"buyer_handle": handle})
        if body["last_four"] == "1111":
            body = {"code": "111111"}
        else:
            assert demo.status_code == 200 and demo.json()["simulation"] is True
            body = {"code": demo.json()["code"]}
    return call(client, method, "/api/confirm/@buyer" + suffix, body, status, buyer_handle=handle)


def test_dashboard_startup_assets_health_and_test_mode(dashboard):
    client, box, boot = dashboard
    assert boot["test_mode"] and "MOCK" in boot["ai"]
    assert box.directory.exists()
    assert call(client, "GET", "/health")["status"] == "ok"
    for name in ("app.js", "style.css"):
        result = client.get("/assets/" + name)
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert client.get("/assets/secret.env").status_code == 404
    assert client.get("/").headers["content-security-policy"].startswith("default-src 'self'")
    assert "HttpOnly" in client.get("/").headers["set-cookie"]
    assert "SameSite=strict" in client.get("/").headers["set-cookie"]
    assert client.get("/api/orders").status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.invalid:8765"},
        {"Origin": "https://attacker.invalid"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_dashboard_rejects_host_and_origin_attacks(dashboard, headers):
    client, _, _ = dashboard
    assert client.get("/dashboard/bootstrap", headers=headers).status_code == 403


def test_dashboard_requires_cookie_csrf_json_and_bounds(dashboard):
    client, box, _ = dashboard
    with TestClient(create_dashboard(), base_url=ORIGIN, client=("127.0.0.1", 55000)) as other:
        assert other.get("/dashboard/bootstrap").status_code == 401
    assert (
        client.post(
            "/dashboard/reset",
            json={"confirm": "RESET FICTIONAL DATA"},
            headers={"X-Dashboard-CSRF": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/dashboard/api", content="{}", headers={"Content-Type": "text/plain"}
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/dashboard/api", content="x" * 65537, headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )
    assert box.bootstrap()["test_mode"]


def test_dashboard_rejects_nonloopback_even_with_forwarded_headers():
    with TestClient(create_dashboard(), base_url=ORIGIN, client=("192.0.2.1", 55000)) as client:
        assert client.get("/", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "https://attacker.invalid/api/orders",
        "//attacker.invalid/api/orders",
        "/api/../orders",
        "/api/orders%2f",
        "/api/confirm/private-secret-token",
        "/openapi.json",
    ],
)
def test_dashboard_proxy_is_allowlisted_and_not_ssrf(dashboard, path):
    client, _, _ = dashboard
    data = call(client, "GET", path, status=400)
    assert "private-secret-token" not in json.dumps(data)


def test_parser_real_extraction_and_invalid_request(dashboard):
    client, _, _ = dashboard
    parsed = call(client, "POST", "/api/orders/parse", {"raw_text": RAW})
    assert parsed["address"]["phone_number"] == "09790000000"
    assert parsed["address"]["cod_amount"] == 25000
    assert parsed["confidence"] == "AMBER" and parsed["field_sources"]
    rejected = call(client, "POST", "/api/orders/parse", {"raw_text": ""}, 422)
    assert rejected["error"]["code"] == "VALIDATION_ERROR"


def test_editable_dashboard_examples_use_actual_parser_results(dashboard):
    client, _, _ = dashboard
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    for name, expected in (("unicode", "AMBER"), ("myanglish", "AMBER"), ("red", "RED")):
        raw = re.search(rf"{name}:'([^']+)'", script)[1]
        parsed = call(client, "POST", "/api/orders/parse", {"raw_text": raw})
        assert parsed["confidence"] == expected
        assert parsed["original_text"] == raw
        if name == "unicode":
            assert parsed["address"]["cod_amount"] == 25000
            assert parsed["address"]["phone_number"] == "09790000000"


def test_order_correction_persistence_events_and_invalid_transition(dashboard):
    client, box, boot = dashboard
    row = order(client, boot)
    corrected = call(
        client,
        "PATCH",
        f"/api/orders/{row['id']}",
        {"expected_version": row["version"], "street": "Updated Fictional Street"},
    )
    assert corrected["street"] == "Updated Fictional Street"
    assert corrected["field_sources"]["street"]["method"] == "manual_correction"
    call(
        client,
        "PATCH",
        f"/api/orders/{row['id']}/status",
        {"expected_version": corrected["version"], "status": "DELIVERED"},
        409,
    )
    assert call(client, "GET", "/api/orders")["total"] == 1
    events = call(client, "GET", f"/api/orders/{row['id']}/events")
    assert events["total"] == 2
    with box.database.sessions() as session:
        assert session.get(Order, UUID(row["id"])).street == "Updated Fictional Street"


def test_full_buyer_dispatcher_rider_cod_lifecycle(dashboard):
    client, box, boot = dashboard
    row = order(client, boot)
    identifier = row["id"]
    result = link(client, identifier)
    handle = result["buyer_handle"]
    assert "confirmation_url" not in result and "absolute_url" not in result
    card = buyer(client, handle)
    assert not any(k in card for k in ("customer_phone", "street", "latitude"))
    buyer(client, handle, suffix="/details", status=401)
    verified = buyer(client, handle, "POST", "/verify", {"last_four": "0000"})
    assert verified["verified"] and "access_token" not in verified
    details = buyer(client, handle, suffix="/details")
    assert details["initial_pin_requires_review"]
    proposal = buyer(
        client,
        handle,
        "PATCH",
        "/location",
        {
            "request_id": str(uuid4()),
            "latitude": "0",
            "longitude": "0",
            "initial_pin_acknowledged": True,
        },
    )
    assert proposal["decision"] == "REVIEW_REQUIRED"
    history = call(client, "GET", f"/api/orders/{identifier}/buyer-requests")
    current = call(client, "GET", f"/api/orders/{identifier}")
    assert current["latitude"] is None
    call(
        client,
        "PATCH",
        f"/api/orders/{identifier}/buyer-requests/{history['items'][0]['id']}",
        {
            "expected_version": current["version"],
            "decision": "APPROVE",
            "reason": "Synthetic operator approval only",
        },
    )
    buyer(client, handle, "PATCH", "/response", {"request_id": str(uuid4()), "action": "AVAILABLE"})
    current = call(client, "GET", f"/api/orders/{identifier}")
    assert current["status"] == "CONFIRMED"  # AVAILABLE uses the existing lifecycle.
    current = transition(client, identifier, "READY_FOR_DISPATCH")
    rider = call(client, "GET", "/api/riders")["items"][0]
    assignment = call(
        client,
        "POST",
        f"/api/orders/{identifier}/assign",
        {"expected_version": current["version"], "rider_id": rider["id"]},
        201,
    )
    queue = call(
        client, "GET", f"/api/riders/{rider['id']}/queue", actor="rider", rider_id=rider["id"]
    )
    assert len(queue["items"]) == 1 and queue["items"][0]["coordinate_status"] == "BUYER_CONFIRMED"
    path = f"/api/riders/{rider['id']}/deliveries/{identifier}/status"
    started = call(
        client,
        "PATCH",
        path,
        {
            "expected_version": assignment["order_version"],
            "request_id": str(uuid4()),
            "action": "START",
        },
        actor="rider",
        rider_id=rider["id"],
    )
    call(
        client,
        "PATCH",
        path,
        {
            "expected_version": started["order_version"],
            "request_id": str(uuid4()),
            "action": "DELIVERED",
        },
        409,
        actor="rider",
        rider_id=rider["id"],
    )
    completed = call(
        client,
        "PATCH",
        path,
        {
            "expected_version": started["order_version"],
            "request_id": str(uuid4()),
            "action": "DELIVERED",
            "cod_collected": True,
        },
        actor="rider",
        rider_id=rider["id"],
    )
    assert completed["status"] == "DELIVERED"
    with box.database.sessions() as session:
        assert session.get(Order, UUID(identifier)).status == "DELIVERED"
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(
                    DeliveryEvent.order_id == UUID(identifier),
                    DeliveryEvent.event_type == "DELIVERY_COMPLETED",
                )
            )
            == 1
        )
    assert not call(
        client, "GET", f"/api/riders/{rider['id']}/queue", actor="rider", rider_id=rider["id"]
    )["items"]
    all_visible = json.dumps([result, verified])
    private = box.buyers[handle]
    assert private["authorization"] not in all_visible
    assert private["path"].split("/")[-1] not in all_visible


def test_buyer_reschedule_rejection_and_invalid_coordinates(dashboard):
    client, _, boot = dashboard
    identifier = order(client, boot)["id"]
    handle = link(client, identifier)["buyer_handle"]
    buyer(client, handle, "POST", "/verify", {"last_four": "0000"})
    buyer(
        client,
        handle,
        "PATCH",
        "/location",
        {
            "request_id": str(uuid4()),
            "latitude": "91",
            "longitude": "0",
            "initial_pin_acknowledged": True,
        },
        422,
    )
    start = (datetime.now(UTC) + timedelta(days=1)).replace(
        hour=4, minute=0, second=0, microsecond=0
    )
    request = buyer(
        client,
        handle,
        "PATCH",
        "/response",
        {
            "request_id": str(uuid4()),
            "action": "RESCHEDULE",
            "time_window": {
                "start": start.isoformat(),
                "end": (start + timedelta(hours=1)).isoformat(),
            },
        },
    )
    assert request["decision"] == "REVIEW_REQUIRED"
    history = call(client, "GET", f"/api/orders/{identifier}/buyer-requests")
    row = call(client, "GET", f"/api/orders/{identifier}")
    call(
        client,
        "PATCH",
        f"/api/orders/{identifier}/buyer-requests/{history['items'][0]['id']}",
        {
            "expected_version": row["version"],
            "decision": "REJECT",
            "reason": "Fictional courier cannot reschedule",
        },
    )
    assert call(client, "GET", f"/api/orders/{identifier}")["delivery_time_window"] is None


def test_expired_link_session_and_real_lockout(dashboard):
    client, _, boot = dashboard
    identifier = order(client, boot)["id"]
    handle = link(client, identifier)["buyer_handle"]
    buyer(client, handle, "POST", "/verify", {"last_four": "0000"})
    assert client.post(
        "/dashboard/expire", json={"buyer_handle": handle, "kind": "SESSION"}
    ).json()["test_fixture_only"]
    buyer(client, handle, suffix="/details", status=401)
    assert (
        client.post("/dashboard/expire", json={"buyer_handle": handle, "kind": "LINK"}).status_code
        == 200
    )
    buyer(client, handle, status=410)
    handle = call(client, "POST", f"/api/orders/{identifier}/confirmation-link", status=201)[
        "buyer_handle"
    ]
    for expected in (403, 403, 403):
        buyer(client, handle, "POST", "/verify", {"last_four": "1111"}, expected)
    assert buyer(client, handle)["state"] == "LOCKED"
    buyer(client, handle, "POST", "/verify", {"last_four": "0000"}, 423)


def test_buyer_handle_cannot_cross_browser_sessions(dashboard):
    client, box, boot = dashboard
    handle = link(client, order(client, boot)["id"])["buyer_handle"]
    visible = client.get("/dashboard/bootstrap").json()
    assert visible["buyers"][0]["handle"] == handle
    assert box.buyers[handle]["path"] not in json.dumps(visible)
    buyer(client, handle, "POST", "/otp", {})
    demo = client.get("/dashboard/buyer-otp", params={"buyer_handle": handle})
    assert demo.status_code == 200 and demo.json()["simulation"] is True
    assert re.fullmatch(r"[0-9]{6}", demo.json()["code"])
    # A separate browser cookie in the SAME sandbox cannot reuse a leaked handle.
    saved = client.cookies.get("lp_dashboard")
    client.cookies.clear()
    client.get("/")
    fresh = client.get("/dashboard/bootstrap").json()
    assert fresh["buyers"] == []
    client.headers["X-Dashboard-CSRF"] = fresh["csrf"]
    buyer(client, handle, status=404)
    assert client.get("/dashboard/buyer-otp", params={"buyer_handle": handle}).status_code == 404
    assert client.cookies.get("lp_dashboard") != saved
    assert box.buyers[handle]["owner"] == saved


def test_internal_http_logs_never_include_buyer_capabilities(dashboard, caplog):
    client, box, boot = dashboard
    caplog.set_level(logging.INFO, logger="httpx2")
    handle = link(client, order(client, boot)["id"])["buyer_handle"]
    buyer(client, handle, "POST", "/verify", {"last_four": "0000"})
    buyer(client, handle, suffix="/details")
    private = box.buyers[handle]
    assert private["path"].split("/")[-1] not in caplog.text
    assert private["authorization"] not in caplog.text
    assert "09790000000" not in caplog.text


def test_rider_scope_wrong_assignment_and_failure_action(dashboard):
    client, _, boot = dashboard
    row = order(client, boot)
    for target in ("NEEDS_REVIEW", "CONFIRMED", "READY_FOR_DISPATCH"):
        row = transition(client, row["id"], target)
    riders = call(client, "GET", "/api/riders")["items"]
    other = call(
        client,
        "POST",
        "/api/riders",
        {"name": "Test Rider Two", "operational_status": "AVAILABLE"},
        201,
    )
    assigned = call(
        client,
        "POST",
        f"/api/orders/{row['id']}/assign",
        {"expected_version": row["version"], "rider_id": riders[0]["id"]},
        201,
    )
    call(
        client,
        "GET",
        f"/api/riders/{riders[0]['id']}/queue",
        status=403,
        actor="rider",
        rider_id=other["id"],
    )
    path = f"/api/riders/{other['id']}/deliveries/{row['id']}/status"
    call(
        client,
        "PATCH",
        path,
        {
            "expected_version": assigned["order_version"],
            "request_id": str(uuid4()),
            "action": "START",
        },
        404,
        actor="rider",
        rider_id=other["id"],
    )
    rider_id = riders[0]["id"]
    path = f"/api/riders/{rider_id}/deliveries/{row['id']}/status"
    started = call(
        client,
        "PATCH",
        path,
        {
            "expected_version": assigned["order_version"],
            "request_id": str(uuid4()),
            "action": "START",
        },
        actor="rider",
        rider_id=rider_id,
    )
    failed = call(
        client,
        "PATCH",
        path,
        {
            "expected_version": started["order_version"],
            "request_id": str(uuid4()),
            "action": "FAILED",
            "failure_reason": "CUSTOMER_UNAVAILABLE",
        },
        actor="rider",
        rider_id=rider_id,
    )
    assert failed["status"] == "FAILED"


def test_reset_only_owned_database_and_old_handles_rejected(dashboard):
    client, box, boot = dashboard
    normal = [p for p in (BACKEND_ROOT / "data").glob("*.sqlite3") if p.is_file()]
    normal += [BACKEND_ROOT / ".env"] if (BACKEND_ROOT / ".env").exists() else []
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in normal}
    identifier = order(client, boot)["id"]
    handle = link(client, identifier)["buyer_handle"]
    old_path = box.directory
    generation = box.generation
    assert client.post("/dashboard/reset", json={"confirm": "wrong"}).status_code == 422
    assert old_path.exists()
    assert (
        client.post("/dashboard/reset", json={"confirm": "RESET FICTIONAL DATA"}).status_code == 200
    )
    assert not old_path.exists() and box.generation != generation
    assert call(client, "GET", "/api/orders")["total"] == 0
    call(client, "GET", f"/api/orders/{identifier}", status=404)
    buyer(client, handle, status=404)
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in normal} == hashes


def test_safe_errors_do_not_echo_private_exceptions_or_input(dashboard, monkeypatch):
    client, box, _ = dashboard
    response = client.post(
        "/dashboard/api", json={"method": "DELETE", "path": "secret-value-in-input"}
    )
    assert response.status_code == 422 and "secret-value-in-input" not in response.text

    def fail(*args, **kwargs):
        raise OperationalError("private-db-secret", {}, Exception("customer-secret"))

    monkeypatch.setattr(box.dispatcher, "request", fail)
    response = client.post("/dashboard/api", json={"method": "GET", "path": "/health"})
    assert response.status_code == 500
    assert "private-db-secret" not in response.text and "customer-secret" not in response.text


def test_dashboard_ai_unavailable_preserves_deterministic_order(dashboard):
    client, box, boot = dashboard

    class UnavailableProbe(AddressExtractionProvider):
        is_external = False
        calls = 0

        @property
        def name(self):
            return "local_unavailable_probe"

        async def extract(self, payload, *, timeout_seconds):
            self.calls += 1
            assert "09790000000" not in str(payload)
            raise ExtractionUnavailableError("private test provider detail")

    provider = UnavailableProbe()
    box.dispatcher.app.state.extraction_provider = provider
    raw = "09790000000, Hlaing, COD 25000, address: behind fictional red gate"
    parsed = call(client, "POST", "/api/orders/parse", {"raw_text": raw})
    assert parsed["ai"]["status"] == "unavailable" and provider.calls == 1
    assert parsed["address"]["phone_number"] == "09790000000"
    assert parsed["address"]["cod_amount"] == 25000
    saved = call(
        client,
        "POST",
        "/api/orders",
        {
            "merchant_id": boot["merchant_id"],
            "raw_text": raw,
        },
        201,
    )
    assert saved["ai_availability_status"] == "unavailable"
    assert saved["customer_phone"] == "09790000000" and saved["cod_amount"] == "25000"
    assert saved["manual_review_required"] and saved["confidence_level"] == "AMBER"
    assert "private test provider detail" not in json.dumps([parsed, saved])


def test_dashboard_mid_transaction_failure_rolls_back_and_recovers(dashboard):
    client, box, boot = dashboard

    def reject_event_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO delivery_events"):
            raise OperationalError("private SQL marker", {}, Exception("private customer marker"))

    event.listen(box.database.engine, "before_cursor_execute", reject_event_insert)
    try:
        rejected = call(
            client,
            "POST",
            "/api/orders",
            {
                "merchant_id": boot["merchant_id"],
                "raw_text": RAW,
            },
            503,
        )
    finally:
        event.remove(box.database.engine, "before_cursor_execute", reject_event_insert)
    assert rejected["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "private SQL marker" not in json.dumps(rejected)
    assert "private customer marker" not in json.dumps(rejected)
    with box.database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(DeliveryEvent)) == 0
    # Same running sandbox and proxy must work after the aborted transaction.
    saved = order(client, boot)
    assert call(client, "GET", f"/api/orders/{saved['id']}/events")["total"] == 1


def test_dashboard_order_and_events_persist_through_independent_connection(dashboard):
    client, box, boot = dashboard
    saved = order(client, boot)
    updated = transition(client, saved["id"], "NEEDS_REVIEW")
    reopened = Database(box.database.engine.url.render_as_string(hide_password=False))
    try:
        with reopened.sessions() as session:
            row = session.get(Order, UUID(saved["id"]))
            assert row.status == "NEEDS_REVIEW" and row.version == updated["version"]
            assert row.original_message == RAW
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(DeliveryEvent)
                    .where(DeliveryEvent.order_id == row.id)
                )
                == 2
            )
    finally:
        reopened.dispose()


def test_dashboard_backend_rejects_private_changes_without_server_credential(dashboard):
    client, box, boot = dashboard
    saved = order(client, boot)
    with TestClient(box.dispatcher.app, client=("127.0.0.1", 55003)) as stranger:
        response = stranger.patch(
            f"/api/orders/{saved['id']}",
            json={
                "expected_version": saved["version"],
                "customer_name": "Unauthorized change",
            },
        )
        assert response.status_code == 401
    current = call(client, "GET", f"/api/orders/{saved['id']}")
    assert current["version"] == saved["version"] and current["customer_name"] is None
    assert call(client, "GET", f"/api/orders/{saved['id']}/events")["total"] == 1


def test_dashboard_shutdown_cleans_generated_directory():
    app = create_dashboard()
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 55000)):
        path = app.state.sandbox.directory
        assert path.exists()
    assert not path.exists()


def test_shutdown_requires_launcher_and_rejects_bad_confirmation(dashboard):
    client, _, _ = dashboard
    assert client.post("/dashboard/shutdown", json={"confirm": "wrong"}).status_code == 422
    assert (
        client.post("/dashboard/shutdown", json={"confirm": "STOP LOCAL TOOL"}).status_code == 409
    )


def test_real_http_launcher_connectivity_reset_and_graceful_shutdown():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "tools.backend_test_dashboard", "--port", str(port)],
        cwd=BACKEND_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
        ) as client:
            deadline = time.monotonic() + 20
            while True:
                assert process.poll() is None, "Dashboard exited before readiness"
                try:
                    response = client.get("/")
                    assert response.status_code == 200
                    break
                except httpx.ConnectError:
                    if time.monotonic() > deadline:
                        pytest.fail("Dashboard startup timed out")
                    time.sleep(0.05)
            boot = client.get("/dashboard/bootstrap").json()
            client.headers["X-Dashboard-CSRF"] = boot["csrf"]
            assert call(client, "GET", "/health")["status"] == "ok"
            assert order(client, boot)["status"] == "DRAFT"
            assert (
                client.post(
                    "/dashboard/reset", json={"confirm": "RESET FICTIONAL DATA"}
                ).status_code
                == 200
            )
            assert call(client, "GET", "/api/orders")["total"] == 0
            assert (
                client.post("/dashboard/shutdown", json={"confirm": "STOP LOCAL TOOL"}).status_code
                == 200
            )
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


def test_launcher_rejects_conflicting_port_without_stopping_owner():
    with socket.socket() as owned:
        owned.bind(("127.0.0.1", 0))
        owned.listen(1)
        port = owned.getsockname()[1]
        result = subprocess.run(
            [sys.executable, "-m", "tools.backend_test_dashboard", "--port", str(port)],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode != 0 and "port unavailable" in result.stderr
        assert owned.getsockname()[1] == port


@pytest.mark.parametrize(
    "origin",
    [
        "http://0.0.0.0:8765",
        "https://127.0.0.1:8765",
        "http://localhost:8765",
        "http://127.0.0.1:8765/path",
    ],
)
def test_unsafe_dashboard_origin_rejected(origin):
    with pytest.raises(ValueError):
        create_dashboard(origin)


def test_static_controls_exist_and_do_not_embed_credentials_or_persist_results():
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', html))
    refs = set(re.findall(r"\$\('([^']+)'\)", script)) | set(re.findall(r"\bon\('([^']+)'", script))
    assert refs <= ids
    assert not any(
        value in script
        for value in ["X-Dev-Access-Token", "localStorage", "sessionStorage", "innerHTML"]
    )
    assert "MOCKED" in html and "TEST MODE" in html
    assert Path(STATIC).is_relative_to(BACKEND_ROOT / "tools")
