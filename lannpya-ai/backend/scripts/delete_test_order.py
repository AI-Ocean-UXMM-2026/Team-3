"""Explicit, backed-up removal of one unassigned local test order.

Never deletes users, riders, routes or financial records. Not a production
retention/erasure API. The exact existing workspace database is the only target.
"""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

BACKEND = Path(__file__).resolve().parents[1]


def delete_test_order(database, order_id):
    identifier = UUID(str(order_id)).hex
    database = Path(database).resolve(strict=True)
    connection = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=10)
    connection.execute("PRAGMA foreign_keys=ON")
    backup = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status, parsing_metadata FROM orders WHERE id=?", (identifier,)
        ).fetchone()
        if not row:
            raise ValueError("Order not found; no records were changed.")
        if row[0] not in {"DRAFT", "NEEDS_REVIEW", "AWAITING_CONFIRMATION", "CONFIRMED", "READY_FOR_DISPATCH"}:
            raise ValueError("Only an undeparted test order can be removed by this tool.")
        metadata = json.loads(row[1])
        context = metadata.get("parcel", {})
        if context.get("route_id") or context.get("collection") or metadata.get("delivery_completion"):
            raise ValueError("Order has route/cash history; deletion refused.")
        for table in ("delivery_assignments", "rider_action_receipts"):
            if connection.execute(f"SELECT count(*) FROM {table} WHERE order_id=?", (identifier,)).fetchone()[0]:
                raise ValueError("Order has rider history; deletion refused.")
        for (data,) in connection.execute("SELECT data FROM workflow_routes"):
            route = json.loads(data)
            if identifier in {UUID(value).hex for value in route.get("order_ids", [])}:
                raise ValueError("Order is referenced by a route; deletion refused.")
        before = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("users", "rider_profiles", "workflow_routes", "orders")}
        backup_dir = database.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f"before-delete-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.sqlite3"
        # The reserved write lock stops competing mutations while a second,
        # read-only connection takes a consistent SQLite backup of the old state.
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
                if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed; deletion refused.")
        try:
            backup.chmod(0o600)
        except OSError:
            pass
        counts = {}
        counts["buyer_sessions"] = connection.execute(
            "DELETE FROM buyer_sessions WHERE link_id IN (SELECT id FROM confirmation_links WHERE order_id=?)",
            (identifier,),
        ).rowcount
        for table in ("buyer_requests", "location_references", "confirmation_links", "delivery_events", "orders"):
            column = "id" if table == "orders" else "order_id"
            counts[table] = connection.execute(f"DELETE FROM {table} WHERE {column}=?", (identifier,)).rowcount
        if counts["orders"] != 1:
            raise RuntimeError("Expected exactly one order; transaction rolled back.")
        for table in ("users", "rider_profiles", "workflow_routes"):
            if connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] != before[table]:
                raise RuntimeError("Protected profile/route counts changed; transaction rolled back.")
        if connection.execute("SELECT count(*) FROM orders").fetchone()[0] != before["orders"] - 1:
            raise RuntimeError("Unexpected order count; transaction rolled back.")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Foreign key check failed; transaction rolled back.")
        connection.commit()
        return {"deleted_order_id": str(UUID(identifier)), "deleted": counts, "backup": str(backup), "profiles_preserved": True}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order-id", type=UUID, required=True)
    parser.add_argument("--confirm-delete", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(delete_test_order(BACKEND / "data/workspace.sqlite3", args.order_id)))


if __name__ == "__main__":
    main()
