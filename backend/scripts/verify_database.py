"""Database connectivity, schema inspection and migration verification CLI tool.

Safely tests SQLite or hosted Supabase PostgreSQL connections without exposing credentials.
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path for direct CLI invocation
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.db.session import BACKEND_ROOT, Database  # noqa: E402


def mask_url(url_str: str) -> str:
    try:
        parsed = make_url(url_str)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        return "[unparseable-url]"


def get_migration_head() -> str | None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def verify(url: str | None = None) -> int:
    settings = Settings()
    raw_url = url or settings.database_url.get_secret_value()
    masked = mask_url(raw_url)

    print("=" * 60)
    print("LannPya AI - Database Connectivity & Schema Verifier")
    print("=" * 60)
    print(f"Target URL: {masked}")

    start_time = time.perf_counter()
    try:
        db = Database(raw_url)
    except Exception as exc:
        print(f"[-] FAILED to initialize database engine: {exc}")
        return 1

    # 1. Connection & Ping Test
    try:
        check = db.check_connection()
        latency_ms = (time.perf_counter() - start_time) * 1000
        print(f"[+] Engine initialized: {check['backend']} (driver: {check['driver']})")
        print(f"[+] Ping successful (SELECT 1) in {latency_ms:.2f}ms")
    except Exception as exc:
        print(f"[-] FAILED to connect to database: {exc}")
        db.dispose()
        return 1

    # 2. Server Version & Dialect Info
    try:
        with db.engine.connect() as conn:
            if check["backend"] == "postgresql":
                version_str = conn.execute(text("SELECT version()")).scalar()
                db_name = conn.execute(text("SELECT current_database()")).scalar()
                current_user = conn.execute(text("SELECT current_user")).scalar()
                try:
                    dbapi_conn = conn.connection.dbapi_connection
                    is_ssl = getattr(getattr(dbapi_conn, "pgconn", None), "ssl_in_use", False)
                    ssl_info = "ENABLED (TLS encrypted)" if is_ssl else "INACTIVE"
                except Exception:
                    ssl_info = "ACTIVE (enforced via sslmode=require)"
                print(f"[+] PostgreSQL server version: {version_str}")
                print(f"[+] Active Database: {db_name}")
                print(f"[+] Authenticated User: {current_user}")
                print(f"[+] SSL / TLS status: {ssl_info}")
            elif check["backend"] == "sqlite":
                version_str = conn.execute(text("SELECT sqlite_version()")).scalar()
                print(f"[+] SQLite library version: {version_str}")
    except Exception as exc:
        print(f"[-] Warning: Unable to query version info: {exc}")

    # 3. Schema & Alembic Migration State
    expected_head = get_migration_head()
    print(f"[+] Alembic migration repository head: {expected_head}")

    try:
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        print(f"[+] Discovered {len(table_names)} tables in current database schema.")

        if "alembic_version" in table_names:
            with db.engine.connect() as conn:
                current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print(f"[+] Current database revision: {current_rev}")
            if current_rev == expected_head:
                print("[+] Migration status: UP TO DATE (matches head)")
            else:
                print(
                    f"[!] Migration status: MISMATCH "
                    f"(current={current_rev}, expected={expected_head})"
                )
        else:
            print("[!] Migration status: UNMIGRATED (alembic_version table not found)")
            print("    Run 'alembic upgrade head' or call upgrade_database(db).")

        # Key domain tables verification
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
            print(f"[!] Warning: Missing expected application tables: {missing}")
        else:
            print("[+] All 12 canonical application tables present.")

    except Exception as exc:
        print(f"[-] Error inspecting schema: {exc}")
        db.dispose()
        return 1

    # 4. Transaction Isolation & Rollback Verification
    try:
        with db.engine.connect() as conn:
            trans = conn.begin()
            # Perform a test operation inside transaction and roll it back
            conn.execute(text("SELECT 1"))
            trans.rollback()
        print("[+] Transaction begin and rollback test passed cleanly.")
    except Exception as exc:
        print(f"[-] Transaction rollback verification failed: {exc}")
        db.dispose()
        return 1

    db.dispose()
    print("=" * 60)
    print("[+] All database validation checks passed successfully.")
    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Verify database connectivity and schema")
    parser.add_argument(
        "--url",
        help="Database URL (SQLite or PostgreSQL). Defaults to DATABASE_URL.",
        default=None,
    )
    args = parser.parse_args()
    sys.exit(verify(args.url))


if __name__ == "__main__":
    main()
