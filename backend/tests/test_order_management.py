import io
import json
import logging
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError

from app.core.access_logging import HideQueryString
from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import Base, DeliveryEvent, Order, User
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import OrderStatus, UserRole
from app.main import create_app

TOKEN = "local-test-only-token-" + "x" * 32


@pytest.fixture
def store(tmp_path):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'isolated.sqlite3'}")
    upgrade_database(database)
    ids = {key: uuid4() for key in ("merchant", "other", "dispatcher", "rider", "admin")}
    with database.sessions.begin() as session:
        for key, role in (
            ("merchant", UserRole.MERCHANT),
            ("other", UserRole.MERCHANT),
            ("dispatcher", UserRole.DISPATCHER),
            ("rider", UserRole.RIDER),
            ("admin", UserRole.ADMIN),
        ):
            session.add(User(id=ids[key], name=key, email=f"{key}@example.test", role=role))
    yield database, ids
    database.dispose()


def app_for(store, actor="dispatcher", **changes):
    database, ids = store
    settings = Settings(
        _env_file=None,
        environment="test",
        order_management_enabled=True,
        dev_access_token=TOKEN,
        dev_actor_id=ids[actor],
        **changes,
    )
    return create_app(settings, database=database)


@pytest.fixture
def client(store):
    with TestClient(
        app_for(store), client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}
    ) as client:
        yield client


def create(client, store, raw="၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀", **body):
    response = client.post(
        "/api/orders", json={"merchant_id": str(store[1]["merchant"]), "raw_text": raw, **body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def status(client, row, target, **extra):
    return client.patch(
        f"/api/orders/{row['id']}/status",
        json={
            "status": target,
            "expected_version": row["version"],
            **({"cod_collected": True} if target == "DELIVERED" else {}),
            **extra,
        },
    )


def test_migrated_schema_and_no_drift(store):
    database, _ = store
    assert set(inspect(database.engine).get_table_names()) == {
        "alembic_version",
        "users",
        "orders",
        "delivery_events",
        "confirmation_links",
        "buyer_sessions",
        "location_references",
        "buyer_requests",
        "buyer_rate_limits",
        "rider_profiles",
        "delivery_assignments",
        "rider_action_receipts",
        "workflow_routes",
        "routing_plans",
        "routing_rate_limits",
    }
    with database.engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert (
            connection.scalar(text("select version_num from alembic_version"))
            == "0005_routing_plans"
        )
        assert (
            compare_metadata(
                MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata
            )
            == []
        )
    upgrade_database(database)  # Idempotent upgrade; must not alter existing users.
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 5


def test_migration_round_trip_only_isolated_empty_database(tmp_path):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'roundtrip.sqlite3'}")
    upgrade_database(database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert inspect(database.engine).get_table_names() == ["alembic_version"]
    upgrade_database(database)
    assert "orders" in inspect(database.engine).get_table_names()
    database.dispose()


def test_postgres_offline_migration_compiles_without_connecting():
    output = io.StringIO()
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output)
    config.attributes["database_url"] = "postgresql+psycopg://unused@localhost/unused"
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for expected in (
        "UUID",
        "JSONB",
        "NUMERIC(12, 0)",
        "TIMESTAMP WITH TIME ZONE",
        "CREATE TABLE orders",
    ):
        assert expected in sql
    assert "unused@localhost" not in sql


def test_create_raw_preserves_parser_and_original_provenance(client, store):
    row = create(client, store)
    assert row["customer_phone"] == "09791234567" and row["cod_amount"] == "25000"
    assert row["township"] == "Hlaing" and row["street"] == "ဗဟိုလမ်း"
    assert row["status"] == "DRAFT" and row["confidence_level"] == "AMBER"
    assert row["latitude"] is None and row["longitude"] is None
    assert row["field_sources"]["customer_phone"]["method"] == "rule"
    assert row["field_sources"]["township"]["method"] == "dictionary"
    assert row["original_message"].startswith("၀၉") and "09791234567" in row["normalized_message"]
    assert row["created_at"].endswith("Z") and row["version"] == 1
    assert client.get(f"/api/orders/{row['id']}").json() == row
    events = client.get(f"/api/orders/{row['id']}/events").json()
    assert events["total"] == 1 and events["items"][0]["event_type"] == "ORDER_CREATED"
    assert "25000" not in json.dumps(events) and "09791234567" not in json.dumps(events)


def test_data_persists_across_new_app_instances(client, store):
    row = create(client, store)
    with TestClient(
        app_for(store), client=("127.0.0.1", 50001), headers={"X-Dev-Access-Token": TOKEN}
    ) as other:
        assert other.get(f"/api/orders/{row['id']}").json()["id"] == row["id"]


def test_structured_create_and_exact_money(client, store):
    response = client.post(
        "/api/orders",
        json={
            "merchant_id": str(store[1]["merchant"]),
            "structured": {
                "customer_name": "Example recipient",
                "customer_phone": "+959791234567",
                "township": "Kamayut",
                "cod_amount": "25000",
                "building": "A",
                "floor": "4",
                "unit": "301",
                "latitude": "16.8000000",
                "longitude": "96.1000000",
            },
        },
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["customer_phone"] == "09791234567" and row["township"] == "Kamaryut"
    assert row["cod_amount"] == "25000" and row["original_message"] is None
    assert row["floor"] == "4" and row["unit"] == "301"
    assert row["field_sources"]["latitude"]["method"] == "manual_correction"
    assert row["confidence_level"] == "AMBER"  # A supplied coordinate is not trusted verification.


def test_incomplete_raw_order_can_be_saved_for_review(client, store):
    row = create(client, store, raw="Unknown area, no contact")
    assert row["confidence_level"] == "RED" and row["customer_phone"] is None
    assert status(client, row, "NEEDS_REVIEW").status_code == 200


def test_order_creation_survives_ai_failure(store):
    from test_hybrid import TestAdapter

    app = app_for(store)
    app.state.extraction_provider = TestAdapter(error=RuntimeError("private upstream"))
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        row = create(c, store, raw="09791234567, Hlaing, COD 25000, address: behind school")
    assert row["ai_availability_status"] == "unavailable" and row["cod_amount"] == "25000"
    assert row["confidence_level"] == "AMBER"


def test_mock_parse_mode_never_persists_fixed_demo_results(store):
    with TestClient(
        app_for(store, parser_mode="mock"),
        client=("127.0.0.1", 50000),
        headers={"X-Dev-Access-Token": TOKEN},
    ) as c:
        row = create(c, store)
    assert row["parsing_mode"] == "rules" and row["customer_phone"] == "09791234567"


def test_pagination_filters_and_literal_search(client, store):
    first = create(client, store, raw="name: Sample Alpha, 09791234567, Hlaing, COD 12000")
    second = create(client, store, raw="name: Sample Beta, 09951234567, Bahan, COD 56000")
    third = create(client, store, raw="No contact here")
    assert status(client, first, "NEEDS_REVIEW").status_code == 200
    page = client.get("/api/orders", params={"page": 1, "page_size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    next_page = client.get("/api/orders", params={"page": 2, "page_size": 2}).json()
    assert len(next_page["items"]) == 1
    assert set(r["id"] for r in page["items"]).isdisjoint(r["id"] for r in next_page["items"])
    assert (
        client.get("/api/orders", params={"confidence": "RED"}).json()["items"][0]["id"]
        == third["id"]
    )
    assert (
        client.get("/api/orders", params={"status": "NEEDS_REVIEW", "q": "alpha"}).json()["total"]
        == 1
    )
    assert (
        client.get("/api/orders", params={"q": "09951234567"}).json()["items"][0]["id"]
        == second["id"]
    )
    assert client.get("/api/orders", params={"q": "%"}).json()["total"] == 0
    assert client.get("/api/orders", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/orders", params={"page": 100}).json()["items"] == []


def test_corrections_validate_retriage_and_preserve_original_sources(client, store):
    row = create(client, store, raw="Hlaing, Baho Road")
    assert row["confidence_level"] == "RED"
    response = client.patch(
        f"/api/orders/{row['id']}",
        json={"expected_version": 1, "customer_phone": "၀၉၇၉၁၂၃၄၅၆၇", "floor": "4", "unit": "A3"},
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["confidence_level"] == "AMBER" and changed["version"] == 2
    assert changed["original_message"] == row["original_message"]
    assert changed["updated_at"] >= row["updated_at"]
    source = changed["field_sources"]["customer_phone"]
    assert (
        source["method"] == "manual_correction" and source["original_source"]["status"] == "missing"
    )
    assert source["evidence"] == [] and source["actor_id"] == str(store[1]["dispatcher"])
    assert changed["building_floor_unit"] == "floor: 4; unit: A3"
    assert (
        client.patch(
            f"/api/orders/{row['id']}", json={"expected_version": 1, "street": "Changed Road"}
        ).status_code
        == 409
    )
    events = client.get(f"/api/orders/{row['id']}/events").json()["items"]
    assert events[-1]["metadata"]["changed_fields"] == ["customer_phone", "floor", "unit"]
    assert "09791234567" not in json.dumps(events)


def test_null_correction_reduces_confidence_and_noop_does_not_add_event(client, store):
    row = create(client, store)
    noop = client.patch(
        f"/api/orders/{row['id']}", json={"expected_version": 1, "customer_phone": "09791234567"}
    ).json()
    assert noop["version"] == 1
    cleared = client.patch(
        f"/api/orders/{row['id']}", json={"expected_version": 1, "customer_phone": None}
    ).json()
    assert cleared["confidence_level"] == "RED" and cleared["customer_phone"] is None
    assert client.get(f"/api/orders/{row['id']}/events").json()["total"] == 2


def test_full_delivery_lifecycle_with_explicit_unverified_acknowledgement(client, store):
    row = create(client, store)
    for target in ("NEEDS_REVIEW", "AWAITING_CONFIRMATION", "CONFIRMED"):
        result = status(client, row, target)
        assert result.status_code == 200, result.text
        row = result.json()
    assert (
        status(client, row, "READY_FOR_DISPATCH").json()["error"]["code"]
        == "LOCATION_ACKNOWLEDGEMENT_REQUIRED"
    )
    row = status(client, row, "READY_FOR_DISPATCH", acknowledge_unverified_location=True).json()
    assert (
        row["confidence_level"] == "AMBER"
    )  # Operational acknowledgement is not geographic proof.
    for target in ("ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED"):
        result = status(client, row, target)
        assert result.status_code == 200, result.text
        row = result.json()
    assert status(client, row, "CANCELLED").status_code == 409
    assert (
        client.patch(
            f"/api/orders/{row['id']}", json={"expected_version": row["version"], "unit": "B"}
        ).status_code
        == 409
    )
    history = client.get(f"/api/orders/{row['id']}/events").json()
    assert history["total"] == 8
    assert any(e["metadata"].get("unverified_location_acknowledged") for e in history["items"])


def test_invalid_transitions_red_confirmation_and_failed_retry(client, store):
    row = create(client, store, raw="Missing contact")
    assert status(client, row, "DELIVERED").status_code == 409
    row = status(client, row, "NEEDS_REVIEW").json()
    assert status(client, row, "CONFIRMED").json()["error"]["code"] == "ORDER_VALIDATION_REQUIRED"
    assert status(client, row, "DRAFT").status_code == 409
    assert status(client, row, "AMBER").status_code == 422


def test_correction_invalidates_confirmed_status(client, store):
    row = create(client, store)
    row = status(client, row, "NEEDS_REVIEW").json()
    row = status(client, row, "CONFIRMED").json()
    changed = client.patch(
        f"/api/orders/{row['id']}",
        json={"expected_version": row["version"], "landmark": "New landmark"},
    ).json()
    assert changed["status"] == "NEEDS_REVIEW" and changed["confidence_level"] == "AMBER"
    event = client.get(f"/api/orders/{row['id']}/events").json()["items"][-1]
    assert event["previous_status"] == "CONFIRMED" and event["new_status"] == "NEEDS_REVIEW"


@pytest.mark.parametrize(
    "structured",
    [
        {},
        {"customer_phone": "123"},
        {"customer_phone": True},
        {"township": "Unknown"},
        {"cod_amount": -1},
        {"cod_amount": True},
        {"cod_amount": 25.5},
        {"cod_amount": "25.5"},
        {"cod_amount": "1,000"},
        {"cod_amount": 1000000001},
        {"customer_name": " "},
        {"street": "x" * 1001},
        {"latitude": 91, "longitude": 96},
        {"latitude": 16, "longitude": 181},
        {"latitude": 16},
        {"latitude": None, "longitude": 96},
        {"latitude": "NaN", "longitude": 96},
        {"latitude": "16.12345678", "longitude": 96},
        {"latitude": True, "longitude": 96},
        {"confidence_level": "GREEN"},
        {"field_sources": {}},
    ],
)
def test_invalid_structured_requests(client, store, structured):
    response = client.post(
        "/api/orders", json={"merchant_id": str(store[1]["merchant"]), "structured": structured}
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"raw_text": ""},
        {"raw_text": " "},
        {"raw_text": "x" * 10001},
        {"raw_text": 123},
        {"structured": {"street": "A"}, "raw_text": "hello"},
        {"raw_text": "hello", "status": "DELIVERED"},
    ],
)
def test_invalid_create_requests(client, store, body):
    assert (
        client.post(
            "/api/orders", json={"merchant_id": str(store[1]["merchant"]), **body}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=-1",
        "page_size=0",
        "page_size=101",
        "page=x",
        "status=AMBER",
        "confidence=unknown",
        "q=",
        "q=" + "x" * 101,
    ],
)
def test_invalid_list_requests(client, query):
    assert client.get("/api/orders?" + query).status_code == 422


def test_missing_and_invalid_ids(client):
    for path in ("not-a-uuid", str(uuid4())):
        assert client.get(f"/api/orders/{path}").status_code == 404
        assert client.get(f"/api/orders/{path}/events").status_code == 404
    assert client.get("/api/orders/parse").status_code == 405


def test_database_records_are_isolated(client):
    assert client.get("/api/orders").json()["total"] == 0


def test_unauthorized_and_remote_access(store):
    app = app_for(store)
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        assert c.get("/api/orders").status_code == 401
        assert c.get("/api/users").status_code == 401
        assert c.get("/api/orders", headers={"X-Dev-Access-Token": "wrong"}).status_code == 401
        assert c.get("/health").status_code == 200
    with TestClient(app, client=("203.0.113.8", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        assert c.get("/api/orders").status_code == 403
        assert c.get("/api/orders", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


def test_production_and_disabled_configuration_fail_closed(store):
    settings = Settings(
        _env_file=None,
        environment="production",
        order_management_enabled=True,
        database_url="postgresql+psycopg://not-used/never-connect",
        dev_access_token=TOKEN,
        dev_actor_id=store[1]["dispatcher"],
    )
    app = create_app(settings, database=store[0])
    assert app.state.database is None
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        assert c.get("/api/orders").status_code == 503 and c.get("/health").status_code == 200
    with TestClient(create_app(Settings(_env_file=None)), client=("127.0.0.1", 50000)) as c:
        assert c.get("/api/orders").status_code == 503


def test_merchant_scoping_and_role_permissions(client, store):
    mine = create(client, store)
    other = create(client, store, merchant_id=str(store[1]["other"]))
    with TestClient(
        app_for(store, "merchant"),
        client=("127.0.0.1", 50000),
        headers={"X-Dev-Access-Token": TOKEN},
    ) as c:
        assert c.get("/api/orders").json()["total"] == 1
        assert c.get(f"/api/orders/{other['id']}").status_code == 404
        assert c.get(f"/api/orders/{other['id']}/events").status_code == 404
        assert (
            c.patch(
                f"/api/orders/{other['id']}", json={"expected_version": 1, "unit": "B"}
            ).status_code
            == 404
        )
        assert (
            c.patch(
                f"/api/orders/{other['id']}/status",
                json={"expected_version": 1, "status": "CANCELLED"},
            ).status_code
            == 404
        )
        assert (
            c.post(
                "/api/orders", json={"merchant_id": str(store[1]["other"]), "raw_text": "anything"}
            ).status_code
            == 403
        )
        assert len(c.get("/api/users").json()) == 1
        row = status(c, mine, "NEEDS_REVIEW").json()
        row = status(c, row, "CONFIRMED").json()
        assert (
            status(c, row, "READY_FOR_DISPATCH", acknowledge_unverified_location=True).status_code
            == 403
        )
    with TestClient(
        app_for(store, "rider"), client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}
    ) as c:
        assert c.get("/api/orders").status_code == 403


def test_users_lookup_and_invalid_merchant(client, store):
    assert len(client.get("/api/users?role=Merchant").json()) == 2
    for merchant_id in (store[1]["dispatcher"], uuid4()):
        assert (
            client.post(
                "/api/orders", json={"merchant_id": str(merchant_id), "raw_text": "hello"}
            ).status_code
            == 422
        )


def test_database_commit_failure_rolls_back_order_and_event(client, store, monkeypatch, caplog):
    def fail(session):
        raise OperationalError("private SQL phone 09791234567", {}, Exception("secret"))

    monkeypatch.setattr(store[0].sessions.class_, "commit", fail)
    response = client.post(
        "/api/orders",
        json={"merchant_id": str(store[1]["merchant"]), "raw_text": "09791234567, Hlaing"},
    )
    assert response.status_code == 503
    assert "secret" not in response.text and "09791234567" not in response.text + caplog.text
    with store[0].sessions() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(DeliveryEvent)) == 0


def test_database_status_failure_is_atomic(client, store, monkeypatch):
    row = create(client, store)

    def fail(session):
        raise OperationalError("private", {}, Exception("private"))

    monkeypatch.setattr(store[0].sessions.class_, "commit", fail)
    assert status(client, row, "NEEDS_REVIEW").status_code == 503
    assert client.get(f"/api/orders/{row['id']}").json()["status"] == "DRAFT"
    assert client.get(f"/api/orders/{row['id']}/events").json()["total"] == 1


def test_optimistic_lock_detects_simultaneous_sessions(client, store):
    row = create(client, store)
    with store[0].sessions() as first, store[0].sessions() as second:
        a = first.get(Order, UUID(row["id"]))
        b = second.get(Order, a.id)
        a.unit = "A"
        first.commit()
        b.unit = "B"
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()


def test_foreign_key_and_amount_constraints_on_database(client, store):
    row = create(client, store)
    with store[0].engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE orders SET cod_amount=-1 WHERE id=:id"),
                {"id": row["id"].replace("-", "")},
            )
    with store[0].sessions() as session:
        session.add(
            DeliveryEvent(
                order_id=uuid4(),
                event_type="STATUS_CHANGED",
                previous_status=None,
                new_status=OrderStatus.DRAFT,
                event_metadata={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_search_terms_are_stripped_from_access_logs():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("local", "GET", "/api/orders?q=09791234567", "1.1", 200),
        None,
    )
    assert HideQueryString().filter(record)
    assert "09791234567" not in record.getMessage()


def test_order_frontend_cors_header_and_patch(client):
    response = client.options(
        "/api/orders",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,x-dev-access-token",
        },
    )
    assert response.status_code == 200


def test_raw_extracted_fields_obey_same_storage_limits_as_postgres(client, store):
    response = client.post(
        "/api/orders",
        json={
            "merchant_id": str(store[1]["merchant"]),
            "raw_text": "name: " + "n" * 201 + ", 09791234567, Hlaing",
        },
    )
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "ORDER_FIELD_TOO_LONG"
    )
    assert client.get("/api/orders").json()["total"] == 0


def test_manual_confirmation_of_same_ai_value_changes_provenance(store):
    from test_hybrid import TestAdapter, suggestion

    app = app_for(store)
    app.state.extraction_provider = TestAdapter(json.dumps({"landmark": suggestion()}))
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        row = create(c, store, raw="09791234567, Hlaing, address: behind red gate")
        assert row["field_sources"]["landmark"]["method"] == "ai"
        corrected = c.patch(
            f"/api/orders/{row['id']}", json={"expected_version": 1, "landmark": "red gate"}
        )
        assert corrected.status_code == 200, corrected.text
        changed = corrected.json()
        source = changed["field_sources"]["landmark"]
        assert (
            source["method"] == "manual_correction" and source["original_source"]["method"] == "ai"
        )
        assert not source["verified"] and changed["confidence_level"] == "AMBER"
        assert changed["version"] == 2


def test_trusted_verification_is_invalidated_when_township_changes(store):
    from test_rules_parser import trusted_fixture

    app = app_for(store)
    app.state.location_catalog = trusted_fixture()
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        row = create(c, store, raw="09791234567, Hlaing, Fixture Road")
        assert row["confidence_level"] == "GREEN"
        changed = c.patch(
            f"/api/orders/{row['id']}", json={"expected_version": 1, "township": "Bahan"}
        ).json()
        assert changed["confidence_level"] == "AMBER"
        assert changed["field_sources"]["street"]["verified"] is False
        assert changed["field_sources"]["street"]["dataset"] is None


def test_failed_delivery_can_return_to_review_and_cancel(client, store):
    row = create(client, store)
    for target in (
        "NEEDS_REVIEW",
        "CONFIRMED",
        "READY_FOR_DISPATCH",
        "ASSIGNED",
        "OUT_FOR_DELIVERY",
        "FAILED",
        "NEEDS_REVIEW",
        "CANCELLED",
    ):
        response = status(
            client, row, target, acknowledge_unverified_location=target == "READY_FOR_DISPATCH"
        )
        assert response.status_code == 200, response.text
        row = response.json()
    assert row["status"] == "CANCELLED"
    assert status(client, row, "NEEDS_REVIEW").status_code == 409


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"expected_version": 1},
        {"unit": "A"},
        {"expected_version": True, "unit": "A"},
        {"expected_version": 1, "merchant_id": str(uuid4())},
        {"expected_version": 1, "status": "DELIVERED"},
        {"expected_version": 1, "confidence_level": "GREEN"},
        {"expected_version": 1, "field_sources": {}},
        {"expected_version": 1, "customer_phone": "12345"},
        {"expected_version": 1, "latitude": 16},
        {"expected_version": 1, "original_message": "replace evidence"},
    ],
)
def test_correction_whitelist_and_validation(client, store, patch):
    row = create(client, store)
    response = client.patch(f"/api/orders/{row['id']}", json=patch)
    assert response.status_code == 422, response.text
    assert client.get(f"/api/orders/{row['id']}").json()["version"] == 1


def test_coordinate_pair_can_be_cleared_without_changing_confidence(client, store):
    row = create(client, store)
    response = client.patch(
        f"/api/orders/{row['id']}",
        json={"expected_version": 1, "latitude": "16.8", "longitude": "96.1"},
    )
    assert response.status_code == 200, response.text
    with_pin = response.json()
    assert with_pin["confidence_level"] == "AMBER"
    cleared = client.patch(
        f"/api/orders/{row['id']}",
        json={"expected_version": with_pin["version"], "latitude": None, "longitude": None},
    ).json()
    assert cleared["latitude"] is None and cleared["longitude"] is None
    assert cleared["confidence_level"] == "AMBER"


def test_event_pagination_and_no_store_headers(client, store):
    row = create(client, store)
    row = status(client, row, "NEEDS_REVIEW").json()
    row = status(client, row, "AWAITING_CONFIRMATION").json()
    first = client.get(f"/api/orders/{row['id']}/events?page_size=2")
    second = client.get(f"/api/orders/{row['id']}/events?page_size=2&page=2")
    assert first.json()["total"] == 3 and len(second.json()["items"]) == 1
    assert first.headers["cache-control"] == "no-store"
    assert client.get("/api/orders").headers["cache-control"] == "no-store"


def test_unmigrated_database_failure_does_not_leak_schema_or_connection(tmp_path, caplog):
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'unmigrated.sqlite3'}")
    settings = Settings(
        _env_file=None,
        environment="test",
        order_management_enabled=True,
        dev_actor_id=uuid4(),
        dev_access_token=TOKEN,
    )
    try:
        with TestClient(
            create_app(settings, database=database),
            client=("127.0.0.1", 50000),
            headers={"X-Dev-Access-Token": TOKEN},
        ) as c:
            response = c.get("/api/orders")
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
            assert "no such table" not in response.text + caplog.text
            assert "unmigrated.sqlite3" not in response.text + caplog.text
    finally:
        database.dispose()


def test_missing_token_or_actor_configuration_is_closed(store):
    app = app_for(store)
    app.state.settings.dev_access_token = None
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        assert c.get("/api/orders").status_code == 503
    app = app_for(store)
    app.state.settings.dev_actor_id = uuid4()
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-Dev-Access-Token": TOKEN}) as c:
        assert c.get("/api/orders").status_code == 403


def test_client_identity_headers_cannot_change_bound_merchant(client, store):
    other = create(client, store, merchant_id=str(store[1]["other"]))
    with TestClient(
        app_for(store, "merchant"),
        client=("127.0.0.1", 50000),
        headers={
            "X-Dev-Access-Token": TOKEN,
            "X-Dev-User-ID": str(store[1]["dispatcher"]),
            "X-Role": "Admin",
        },
    ) as c:
        assert c.get(f"/api/orders/{other['id']}").status_code == 404


def test_unknown_database_dialect_is_rejected():
    with pytest.raises(ValueError):
        Database("mysql://unused/unused")
