"""End-to-end hosted database persistence verification CLI tool.

Safely tests PostgreSQL (Supabase) or SQLite:
1. Verifies connectivity & engine ping.
2. Applies or verifies Alembic migrations up to head.
3. Tests synthetic data persistence across:
   - User accounts (Dispatcher, Merchant, Rider)
   - Orders & COD amounts
   - LocationReferences (lat/long coordinates)
   - ConfirmationLinks
   - Rider profiles & Delivery assignments
   - Routing plans & stop sequences
   - Delivery event audit trails
4. Tests optimistic concurrency (version_id_col conflict).
5. Tests foreign key constraints (orphan rejection).
6. Tests transaction rollback guarantee.
7. Tests backend restart persistence (dispose & re-instantiate engine).
8. Safely cleans up all synthetic test data.
"""

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm.exc import StaleDataError  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.db.buyer_models import ConfirmationLink, LocationReference  # noqa: E402
from app.db.migrations import upgrade_database  # noqa: E402
from app.db.models import DeliveryEvent, Order, User  # noqa: E402
from app.db.rider_models import DeliveryAssignment, RiderProfile  # noqa: E402
from app.db.routing_models import RoutingPlan  # noqa: E402
from app.db.session import BACKEND_ROOT, Database  # noqa: E402
from app.domain.lifecycle import OrderStatus, UserRole  # noqa: E402
from app.schemas.orders import Confidence  # noqa: E402


def mask_url(url_str: str) -> str:
    try:
        parsed = make_url(url_str)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        return "[unparseable-url]"


def get_expected_migration_head() -> str | None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def run_hosted_verification(url: str | None = None, auto_migrate: bool = True) -> int:
    settings = Settings()
    raw_url = url or settings.database_url.get_secret_value()
    masked = mask_url(raw_url)

    print("=" * 70)
    print(" LannPya AI — Database Persistence & Integration Test Suite")
    print("=" * 70)
    print(f"Target Database URL: {masked}")

    # 1. Connectivity & Engine Initialization
    print("\n--- 1. Testing Connectivity & Engine ---")
    start = time.perf_counter()
    try:
        db = Database(raw_url)
        check = db.check_connection()
        latency_ms = (time.perf_counter() - start) * 1000
        print(f"[PASS] Connected to backend: {check['backend']} (driver: {check['driver']})")
        print(f"[PASS] Round-trip latency: {latency_ms:.2f}ms")
    except Exception as exc:
        print(f"[FAIL] Unable to connect: {exc}")
        return 1

    # Print version info
    with db.engine.connect() as conn:
        if check["backend"] == "postgresql":
            version = conn.execute(text("SELECT version()")).scalar()
            print(f"[INFO] PostgreSQL version: {version}")
        else:
            version = conn.execute(text("SELECT sqlite_version()")).scalar()
            print(f"[INFO] SQLite version: {version}")

    # 2. Migration Status & Upgrade
    print("\n--- 2. Checking Alembic Migrations ---")
    expected_head = get_expected_migration_head()
    print(f"[INFO] Alembic repository target head: {expected_head}")

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    current_rev = None
    if "alembic_version" in table_names:
        with db.engine.connect() as conn:
            current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"[INFO] Current database revision: {current_rev}")

    if current_rev != expected_head:
        if auto_migrate:
            print(f"[INFO] Applying Alembic migrations up to head ({expected_head})...")
            try:
                upgrade_database(db)
                with db.engine.connect() as conn:
                    current_rev = conn.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar()
                print(f"[PASS] Migrations applied successfully. Current revision: {current_rev}")
            except Exception as exc:
                print(f"[FAIL] Migration upgrade failed: {exc}")
                db.dispose()
                return 1
        else:
            print(f"[FAIL] Database is at revision {current_rev}, expected {expected_head}.")
            db.dispose()
            return 1
    else:
        print("[PASS] Database schema is already up to date.")

    # Verify all 12 domain tables
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    required_tables = [
        "users",
        "orders",
        "delivery_events",
        "confirmation_links",
        "buyer_sessions",
        "location_references",
        "buyer_requests",
        "rider_profiles",
        "delivery_assignments",
        "rider_action_receipts",
        "workflow_routes",
        "routing_plans",
    ]
    missing = [t for t in required_tables if t not in table_names]
    if missing:
        print(f"[FAIL] Missing required domain tables: {missing}")
        db.dispose()
        return 1
    print(f"[PASS] All {len(required_tables)} canonical application tables verified.")

    # 3. Synthetic Data Persistence Test Suite
    print("\n--- 3. Running Synthetic Persistence Tests ---")

    # Generate unique test fixtures
    test_run_id = uuid4().hex[:8]
    dispatcher_id = uuid4()
    merchant_id = uuid4()
    rider_user_id = uuid4()
    order_id = uuid4()
    link_id = uuid4()
    assignment_id = uuid4()
    routing_plan_id = uuid4()
    event_id = uuid4()

    try:
        # A. Create Users
        with db.sessions.begin() as session:
            dispatcher = User(
                id=dispatcher_id,
                name=f"Dispatcher Test {test_run_id}",
                email=f"dispatcher_{test_run_id}@test.lannpya.local",
                role=UserRole.DISPATCHER,
            )
            merchant = User(
                id=merchant_id,
                name=f"Merchant Test {test_run_id}",
                email=f"merchant_{test_run_id}@test.lannpya.local",
                role=UserRole.MERCHANT,
            )
            rider_user = User(
                id=rider_user_id,
                name=f"Rider Test {test_run_id}",
                email=f"rider_{test_run_id}@test.lannpya.local",
                role=UserRole.RIDER,
            )
            session.add_all([dispatcher, merchant, rider_user])
        print("[PASS] User records created (Dispatcher, Merchant, Rider).")

        # B. Create Order & Location & Link
        with db.sessions.begin() as session:
            order = Order(
                id=order_id,
                merchant_id=merchant_id,
                customer_name=f"Customer {test_run_id}",
                customer_phone="09123456789",
                original_message="Bahan, Shwe Gon Daing, COD 15,000 MMK",
                township="Bahan",
                street="Shwe Gon Daing Rd",
                latitude=Decimal("16.8052145"),
                longitude=Decimal("96.1558231"),
                cod_amount=Decimal("15000"),
                confidence_level=Confidence.GREEN,
                confidence_reasons=["exact_match", "valid_phone"],
                parsing_mode="rules",
                ai_availability_status="mock",
                field_sources={"township": "rules", "cod": "rules"},
                parsing_metadata={"duration_ms": 1.2},
                status=OrderStatus.DRAFT,
                version=1,
            )
            session.add(order)
            session.flush()

            location_ref = LocationReference(
                order_id=order_id,
                latitude=Decimal("16.8052145"),
                longitude=Decimal("96.1558231"),
                township="Bahan",
                source_reference="dispatcher_verified_gps",
                actor_id=dispatcher_id,
            )
            link = ConfirmationLink(
                id=link_id,
                order_id=order_id,
                token_hash=f"token_hash_{test_run_id}_{uuid4().hex[:16]}",
                phone_binding="hash_of_phone_09123456789",
                expires_at=datetime.now(UTC) + timedelta(hours=72),
                failed_attempts=0,
                generation=0,
                nonce=0,
            )
            session.add_all([location_ref, link])
        print("[PASS] Order, LocationReference, and ConfirmationLink persisted.")

        # C. Create Rider Profile & Assignment
        with db.sessions.begin() as session:
            rider_profile = RiderProfile(
                id=rider_user_id,
                operational_status="AVAILABLE",
                contact_phone="09987654321",
                version=1,
                queue_version=0,
            )
            session.add(rider_profile)
            session.flush()

            assignment = DeliveryAssignment(
                id=assignment_id,
                order_id=order_id,
                rider_id=rider_user_id,
                dispatcher_id=dispatcher_id,
                status="ACTIVE",
                stop_sequence=1,
            )
            session.add(assignment)
        print("[PASS] RiderProfile and DeliveryAssignment persisted.")

        # D. Create Routing Plan & Delivery Event
        with db.sessions.begin() as session:
            plan = RoutingPlan(
                id=routing_plan_id,
                actor_id=dispatcher_id,
                state="OPTIMIZED",
                data={
                    "stops": [
                        {
                            "order_id": str(order_id),
                            "sequence": 1,
                            "lat": 16.8052145,
                            "lng": 96.1558231,
                            "cod": 15000,
                        }
                    ],
                    "total_distance_km": 4.2,
                    "estimated_minutes": 15,
                },
                version=1,
            )
            event = DeliveryEvent(
                id=event_id,
                order_id=order_id,
                event_type="RIDER_ASSIGNED",
                previous_status=OrderStatus.DRAFT,
                new_status=OrderStatus.ASSIGNED,
                event_metadata={
                    "rider_id": str(rider_user_id),
                    "dispatcher_id": str(dispatcher_id),
                },
            )
            session.add_all([plan, event])
        print("[PASS] RoutingPlan (JSON payload) and DeliveryEvent audit record persisted.")

        # 4. Optimistic Concurrency Test
        print("\n--- 4. Testing Optimistic Concurrency Locking ---")
        sess1 = db.sessions()
        sess2 = db.sessions()
        try:
            ord_s1 = sess1.get(Order, order_id)
            ord_s2 = sess2.get(Order, order_id)
            ord_s1.customer_name = f"Customer Updated S1 {test_run_id}"
            sess1.commit()

            ord_s2.customer_name = f"Customer Updated S2 {test_run_id}"
            try:
                sess2.commit()
                print("[FAIL] Optimistic locking failed to reject stale version update!")
                return 1
            except StaleDataError:
                sess2.rollback()
                print(
                    "[PASS] Optimistic locking correctly rejected stale version update."
                )
        finally:
            sess1.close()
            sess2.close()

        # 5. Foreign Key Integrity Constraint Test
        print("\n--- 5. Testing Foreign Key Integrity ---")
        try:
            with db.sessions.begin() as session:
                orphan_order = Order(
                    id=uuid4(),
                    merchant_id=uuid4(),  # non-existent user
                    customer_name="Orphan Customer",
                    confidence_level=Confidence.RED,
                    confidence_reasons=[],
                    parsing_mode="rules",
                    ai_availability_status="mock",
                    field_sources={},
                    parsing_metadata={},
                )
                session.add(orphan_order)
                session.flush()
            print("[FAIL] Database allowed orphan record with invalid foreign key!")
            return 1
        except IntegrityError:
            print("[PASS] Database strictly rejected invalid foreign key (IntegrityError).")

        # 6. Transaction Rollback Guarantee Test
        print("\n--- 6. Testing Transaction Rollback Guarantee ---")
        dummy_user_id = uuid4()
        try:
            with db.sessions.begin() as session:
                dummy_user = User(
                    id=dummy_user_id,
                    name="Rollback Test User",
                    email=f"rollback_{test_run_id}@test.local",
                    role=UserRole.MERCHANT,
                )
                session.add(dummy_user)
                session.flush()
                # Deliberate failure inside transaction
                raise RuntimeError("Deliberate failure to test rollback")
        except RuntimeError:
            pass

        with db.sessions() as session:
            rolled_back = session.get(User, dummy_user_id)
            if rolled_back is not None:
                print("[FAIL] Rollback failed, uncommitted record persisted!")
                return 1
            print("[PASS] Transaction rolled back cleanly without leaving uncommitted records.")

        # 7. Backend Restart Persistence Simulation
        print("\n--- 7. Testing Persistence Across Backend Restart ---")
        print("[INFO] Disposing database connection pool...")
        db.dispose()

        print("[INFO] Re-initializing completely new database engine instance...")
        db_restarted = Database(raw_url)

        with db_restarted.sessions() as session:
            # Query order
            persisted_order = session.get(Order, order_id)
            assert persisted_order is not None, "Order was not persisted across restart!"
            assert persisted_order.cod_amount == Decimal("15000")
            assert persisted_order.latitude == Decimal("16.8052145")
            assert persisted_order.township == "Bahan"

            # Query location reference
            loc = session.get(LocationReference, order_id)
            assert loc is not None, "Location reference lost after restart!"
            assert loc.latitude == Decimal("16.8052145")

            # Query assignment
            assign = session.get(DeliveryAssignment, assignment_id)
            assert assign is not None, "Assignment lost after restart!"
            assert assign.status == "ACTIVE"

            # Query routing plan
            routing = session.get(RoutingPlan, routing_plan_id)
            assert routing is not None, "Routing plan lost after restart!"
            assert routing.data["total_distance_km"] == 4.2

            # Query event
            ev = session.get(DeliveryEvent, event_id)
            assert ev is not None, "Delivery event lost after restart!"
            assert ev.event_type == "RIDER_ASSIGNED"

        print("[PASS] All synthetic records verified intact after engine recreation.")

        # 8. Clean Up Synthetic Test Fixtures
        print("\n--- 8. Cleaning Up Synthetic Test Data ---")
        with db_restarted.sessions.begin() as session:
            # Remove in reverse dependency order
            session.execute(text(f"DELETE FROM delivery_events WHERE id = '{event_id}'"))
            session.execute(text(f"DELETE FROM routing_plans WHERE id = '{routing_plan_id}'"))
            session.execute(text(f"DELETE FROM delivery_assignments WHERE id = '{assignment_id}'"))
            session.execute(text(f"DELETE FROM rider_profiles WHERE id = '{rider_user_id}'"))
            session.execute(text(f"DELETE FROM confirmation_links WHERE id = '{link_id}'"))
            session.execute(text(f"DELETE FROM location_references WHERE order_id = '{order_id}'"))
            session.execute(text(f"DELETE FROM orders WHERE id = '{order_id}'"))
            ids = f"'{dispatcher_id}', '{merchant_id}', '{rider_user_id}'"
            session.execute(text(f"DELETE FROM users WHERE id IN ({ids})"))
        print("[PASS] Synthetic test fixtures cleaned up cleanly (zero database pollution).")

        db_restarted.dispose()

    except Exception as exc:
        print(f"[FAIL] Unexpected error during persistence verification: {exc}")
        db.dispose()
        return 1

    print("\n" + "=" * 70)
    print(" ALL DATABASE PERSISTENCE & INTEGRATION TESTS PASSED")
    print("=" * 70)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Verify database persistence and compatibility on hosted PostgreSQL or SQLite"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Database URL to verify (defaults to DATABASE_URL or LANNPYA_DATABASE_URL in .env)",
    )
    parser.add_argument(
        "--no-migrate",
        action="store_true",
        help="Do not automatically run alembic upgrade head if schema is behind",
    )
    args = parser.parse_args()

    exit_code = run_hosted_verification(url=args.url, auto_migrate=not args.no_migrate)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
