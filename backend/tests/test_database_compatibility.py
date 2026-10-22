"""Tests for PostgreSQL compatibility, Supabase configuration, and database integrity.

Tests URL normalization, dialect DDL compilation, Alembic migrations,
foreign key integrity, optimistic locking, and transaction rollbacks.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.config import Settings
from app.db import (
    buyer_models,
    routing_models,
)
from app.db.buyer_models import ConfirmationLink, LocationReference
from app.db.models import Base, DeliveryEvent, Order, User
from app.db.rider_models import (
    AllocationCoordinator,
    AllocationReceipt,
    AutomaticAllocation,
    DeliveryAssignment,
    RiderActionReceipt,
    RiderProfile,
)
from app.db.routing_models import RoutingPlan
from app.db.session import Database, normalize_database_url
from app.db.workflow_models import WorkflowRoute
from app.domain.lifecycle import OrderStatus, UserRole
from app.schemas.orders import Confidence

# ==============================================================================
# 1. URL Normalization & Settings Alias Tests
# ==============================================================================


def test_url_normalization_postgres_schemes():
    """Verify postgres:// and postgresql:// are normalized to postgresql+psycopg://."""
    pg1 = normalize_database_url("postgres://postgres:secret@db.supabase.co:5432/postgres")
    assert pg1.drivername == "postgresql+psycopg"
    assert pg1.username == "postgres"
    assert pg1.host == "db.supabase.co"
    assert pg1.port == 5432
    assert pg1.database == "postgres"

    pg2 = normalize_database_url(
        "postgresql://postgres.ref:secret@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    assert pg2.drivername == "postgresql+psycopg"
    assert pg2.port == 6543
    assert pg2.query.get("sslmode") == "require"

    pg3 = normalize_database_url("postgresql+psycopg://user:pass@localhost:5432/db")
    assert pg3.drivername == "postgresql+psycopg"


def test_url_normalization_sqlite():
    """Verify SQLite URLs are preserved without modification."""
    sq = normalize_database_url("sqlite+pysqlite:///./data/test.sqlite3")
    assert sq.drivername == "sqlite+pysqlite"
    assert sq.get_backend_name() == "sqlite"


def test_url_normalization_rejects_unsupported():
    """Verify non-SQLite/non-PostgreSQL URLs are explicitly rejected."""
    with pytest.raises(ValueError, match="Only SQLite and PostgreSQL"):
        normalize_database_url("mysql+pymysql://user:pass@host/db")

    with pytest.raises(ValueError, match="Only SQLite and PostgreSQL"):
        normalize_database_url("oracle+cx_oracle://user:pass@host/db")


def test_settings_database_url_aliases(monkeypatch):
    """Verify Settings recognizes both DATABASE_URL and LANNPYA_DATABASE_URL."""
    monkeypatch.delenv("LANNPYA_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass1@host/db1")
    s1 = Settings(_env_file=None)
    assert s1.database_url.get_secret_value() == "postgres://user:pass1@host/db1"

    # LANNPYA_DATABASE_URL takes precedence
    monkeypatch.setenv("LANNPYA_DATABASE_URL", "postgres://user:pass2@host/db2")
    s2 = Settings(_env_file=None)
    assert s2.database_url.get_secret_value() == "postgres://user:pass2@host/db2"


def test_credentials_masked_in_str():
    """Verify SecretStr prevents accidental credential leakage in logs or representations."""
    s = Settings(
        _env_file=None, database_url=SecretStr("postgres://postgres:SUPER_SECRET@host:5432/db")
    )
    assert "SUPER_SECRET" not in str(s.database_url)
    assert "SUPER_SECRET" not in repr(s.database_url)
    assert s.database_url.get_secret_value() == "postgres://postgres:SUPER_SECRET@host:5432/db"


# ==============================================================================
# 2. PostgreSQL DDL Compilation & Dialect Compatibility Tests
# ==============================================================================


@pytest.mark.parametrize(
    "model_cls",
    [
        User,
        Order,
        DeliveryEvent,
        ConfirmationLink,
        buyer_models.BuyerSession,
        LocationReference,
        buyer_models.BuyerRequest,
        buyer_models.BuyerRateLimit,
        RiderProfile,
        DeliveryAssignment,
        RiderActionReceipt,
        AllocationCoordinator,
        AutomaticAllocation,
        AllocationReceipt,
        WorkflowRoute,
        RoutingPlan,
        routing_models.RoutingRateLimit,
    ],
)
def test_all_models_compile_to_valid_postgresql_ddl(model_cls):
    """Verify that every SQLAlchemy model compiles cleanly to PostgreSQL DDL."""
    table = model_cls.__table__
    dialect = postgresql.dialect()
    ddl = str(CreateTable(table).compile(dialect=dialect))
    assert ddl.startswith(f"\nCREATE TABLE {table.name}")
    # Verify primary key is defined
    assert "PRIMARY KEY" in ddl


def test_postgresql_specific_types_compiled():
    """Verify UUID, JSONB, NUMERIC, and TIMESTAMP WITH TIME ZONE are used in PostgreSQL DDL."""
    dialect = postgresql.dialect()

    orders_ddl = str(CreateTable(Order.__table__).compile(dialect=dialect))
    assert "UUID" in orders_ddl
    assert "JSONB" in orders_ddl
    assert "NUMERIC(10, 7)" in orders_ddl
    assert "NUMERIC(12, 0)" in orders_ddl
    assert "TIMESTAMP WITH TIME ZONE" in orders_ddl

    # Check partial unique index on delivery_assignments
    assignment_indexes = [
        str(CreateIndex(idx).compile(dialect=dialect))
        for idx in DeliveryAssignment.__table__.indexes
    ]
    active_idx = [sql for sql in assignment_indexes if "ux_assignment_active_order" in sql]
    assert len(active_idx) == 1
    assert "WHERE status = 'ACTIVE'" in active_idx[0]


# ==============================================================================
# 3. Alembic Migration Chain Verification
# ==============================================================================


def test_alembic_migration_revisions_chain():
    """Verify that Alembic migration history has contiguous revisions leading to head."""
    from app.db.session import BACKEND_ROOT

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    assert head == "0007_buyer_otp"

    # Walk through revisions from head down to base
    revs = []
    curr = script.get_revision(head)
    while curr is not None:
        revs.append(curr.revision)
        curr = script.get_revision(curr.down_revision) if curr.down_revision else None

    assert revs == [
        "0007_buyer_otp",
        "0006_automatic_assignment",
        "0005_routing_plans",
        "0004_workflow_routes",
        "0003_rider_copilot",
        "0002_buyer_confirmation",
        "0001_order_management",
    ]


def test_alembic_offline_postgresql_generation(capsys):
    """Verify Alembic generates complete PostgreSQL SQL from revision None to head without error."""
    from alembic import command

    from app.db.session import BACKEND_ROOT

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    # Point to synthetic PostgreSQL target
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql+psycopg://postgres:dummy@localhost:5432/postgres",
    )

    command.upgrade(config, "head", sql=True)
    captured = capsys.readouterr()
    sql_text = captured.out

    assert "CREATE TABLE users (" in sql_text
    assert "CREATE TABLE orders (" in sql_text
    assert "CREATE TABLE confirmation_links (" in sql_text
    assert "CREATE TABLE delivery_assignments (" in sql_text
    assert "CREATE TABLE workflow_routes (" in sql_text
    assert "CREATE TABLE routing_plans (" in sql_text
    assert "ALTER TABLE delivery_events DROP CONSTRAINT ck_events_type" in sql_text
    assert "WHERE alembic_version.version_num = '0004_workflow_routes'" in sql_text


# ==============================================================================
# 4. Data Persistence & Transaction Integrity Tests (Isolated Sandbox)
# ==============================================================================


@pytest.fixture
def test_db(tmp_path):
    """Creates an isolated temporary SQLite database with all tables created."""
    db_file = tmp_path / "test_db.sqlite3"
    db = Database(f"sqlite+pysqlite:///{db_file}")
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_database_check_connection(test_db):
    """Verify check_connection returns connection status and engine details."""
    res = test_db.check_connection()
    assert res["connected"] is True
    assert res["backend"] == "sqlite"
    assert res["driver"] == "pysqlite"


def test_core_persistence_lifecycle(test_db):
    """Verify persistence of User -> Order -> ConfirmationLink -> Assignment -> Event."""
    with test_db.sessions.begin() as session:
        merchant = User(
            id=uuid4(),
            name="Test Merchant",
            email="merchant@test.local",
            role=UserRole.MERCHANT,
        )
        session.add(merchant)
        session.flush()

        order = Order(
            id=uuid4(),
            merchant_id=merchant.id,
            customer_name="Ko Aung",
            customer_phone="0912345678",
            original_message="Hlaing, Ward 3, 2 shirts COD 25000",
            township="Hlaing",
            street="Insein Road",
            latitude=Decimal("16.8250000"),
            longitude=Decimal("96.1300000"),
            cod_amount=Decimal("25000"),
            confidence_level=Confidence.GREEN,
            confidence_reasons=["EXACT_TOWNSHIP_MATCH"],
            parsing_mode="rules",
            ai_availability_status="not_requested",
            field_sources={"township": "rules"},
            parsing_metadata={},
            status=OrderStatus.NEEDS_REVIEW,
            version=1,
        )
        session.add(order)
        session.flush()

        # Buyer confirmation link
        link = ConfirmationLink(
            id=uuid4(),
            order_id=order.id,
            token_hash="a" * 64,
            phone_binding="0912345678",
            expires_at=order.created_at,
            generation=0,
            nonce=0,
        )
        session.add(link)

        # Rider profile and assignment
        rider_user = User(
            id=uuid4(),
            name="Mg Ba",
            email="rider@test.local",
            role=UserRole.RIDER,
        )
        session.add(rider_user)
        session.flush()

        profile = RiderProfile(
            id=rider_user.id,
            operational_status="AVAILABLE",
            contact_phone="0998765432",
        )
        session.add(profile)
        session.flush()

        assignment = DeliveryAssignment(
            id=uuid4(),
            order_id=order.id,
            rider_id=profile.id,
            dispatcher_id=merchant.id,
            status="ACTIVE",
            stop_sequence=1,
        )
        session.add(assignment)

        # Audit delivery event
        event = DeliveryEvent(
            id=uuid4(),
            order_id=order.id,
            event_type="RIDER_ASSIGNED",
            previous_status=OrderStatus.NEEDS_REVIEW,
            new_status=OrderStatus.ASSIGNED,
            event_metadata={"rider_id": str(profile.id)},
        )
        session.add(event)

    # Query back in a new session to verify true disk persistence
    with test_db.sessions() as session:
        queried_order = session.get(Order, order.id)
        assert queried_order is not None
        assert queried_order.customer_name == "Ko Aung"
        assert queried_order.cod_amount == Decimal("25000")
        assert queried_order.latitude == Decimal("16.8250000")

        queried_assignment = session.query(DeliveryAssignment).filter_by(order_id=order.id).first()
        assert queried_assignment is not None
        assert queried_assignment.rider_id == profile.id
        assert queried_assignment.status == "ACTIVE"

        queried_event = session.query(DeliveryEvent).filter_by(order_id=order.id).first()
        assert queried_event is not None
        assert queried_event.event_type == "RIDER_ASSIGNED"


def test_optimistic_concurrency_version_locking(test_db):
    """Verify that concurrent edits on stale order versions fail with StaleDataError."""
    from sqlalchemy.orm.exc import StaleDataError

    with test_db.sessions.begin() as session:
        user = User(id=uuid4(), name="Merchant", email="m@test.local", role=UserRole.MERCHANT)
        session.add(user)
        session.flush()
        order = Order(
            id=uuid4(),
            merchant_id=user.id,
            customer_name="First Version",
            confidence_level=Confidence.GREEN,
            confidence_reasons=[],
            parsing_mode="rules",
            ai_availability_status="mock",
            field_sources={},
            parsing_metadata={},
            version=1,
        )
        session.add(order)

    # Session 1 updates order
    with test_db.sessions() as s1:
        o1 = s1.get(Order, order.id)

        # Session 2 updates order concurrently and commits
        with test_db.sessions.begin() as s2:
            o2 = s2.get(Order, order.id)
            o2.customer_name = "Session 2 Name"

        # Session 1 tries to commit with stale version -> must fail
        o1.customer_name = "Session 1 Stale Name"
        with pytest.raises(StaleDataError):
            s1.commit()


def test_foreign_key_restrict_enforcement(test_db):
    """Verify that deleting a User with associated Orders is blocked by ON DELETE RESTRICT."""
    with test_db.sessions.begin() as session:
        user = User(id=uuid4(), name="Merchant", email="m2@test.local", role=UserRole.MERCHANT)
        session.add(user)
        session.flush()
        order = Order(
            id=uuid4(),
            merchant_id=user.id,
            confidence_level=Confidence.GREEN,
            confidence_reasons=[],
            parsing_mode="rules",
            ai_availability_status="mock",
            field_sources={},
            parsing_metadata={},
        )
        session.add(order)

    with test_db.sessions.begin() as session:
        u = session.get(User, user.id)
        session.delete(u)
        with pytest.raises(IntegrityError):
            session.flush()


def test_transaction_rollback_guarantee(test_db):
    """Verify that failed transactions roll back cleanly leaving no partial state."""
    user_id = uuid4()
    with pytest.raises(RuntimeError):
        with test_db.sessions.begin() as session:
            user = User(id=user_id, name="Temp User", email="temp@test.local", role=UserRole.ADMIN)
            session.add(user)
            session.flush()
            raise RuntimeError("Simulated crash mid-transaction")

    with test_db.sessions() as session:
        assert session.get(User, user_id) is None


# ==============================================================================
# 5. Optional Live Supabase Connectivity Test
# ==============================================================================


@pytest.mark.skipif(
    not os.environ.get("TEST_SUPABASE_DATABASE_URL"),
    reason="Live Supabase testing requires TEST_SUPABASE_DATABASE_URL environment variable",
)
def test_live_supabase_connectivity():
    """Live verification against user-provided Supabase PostgreSQL instance."""
    url = os.environ["TEST_SUPABASE_DATABASE_URL"]
    db = Database(url)
    try:
        check = db.check_connection()
        assert check["connected"] is True
        assert check["backend"] == "postgresql"
        with db.engine.connect() as conn:
            ver = conn.execute(text("SELECT version()")).scalar()
            assert "PostgreSQL" in ver
    finally:
        db.dispose()
