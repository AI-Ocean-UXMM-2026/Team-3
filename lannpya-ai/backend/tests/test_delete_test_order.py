import json
import sqlite3
from uuid import UUID, uuid4

import pytest

from scripts.delete_test_order import delete_test_order


def fixture_database(tmp_path):
    path = tmp_path / "workspace.sqlite3"
    target, other = uuid4().hex, uuid4().hex
    with sqlite3.connect(path) as c:
        c.executescript("""
            CREATE TABLE orders (id TEXT PRIMARY KEY, status TEXT, parsing_metadata TEXT);
            CREATE TABLE users (id TEXT PRIMARY KEY);
            CREATE TABLE rider_profiles (id TEXT PRIMARY KEY);
            CREATE TABLE workflow_routes (data TEXT);
            CREATE TABLE confirmation_links (id TEXT PRIMARY KEY, order_id TEXT REFERENCES orders(id));
            CREATE TABLE buyer_requests (order_id TEXT REFERENCES orders(id));
            CREATE TABLE buyer_sessions (link_id TEXT REFERENCES confirmation_links(id));
            CREATE TABLE location_references (order_id TEXT REFERENCES orders(id));
            CREATE TABLE delivery_events (order_id TEXT REFERENCES orders(id));
            CREATE TABLE delivery_assignments (order_id TEXT REFERENCES orders(id));
            CREATE TABLE rider_action_receipts (order_id TEXT REFERENCES orders(id));
            INSERT INTO users VALUES ('admin');
            INSERT INTO rider_profiles VALUES ('rider');
        """)
        for identifier in (target, other):
            c.execute("INSERT INTO orders VALUES (?, 'NEEDS_REVIEW', '{}')", (identifier,))
            c.execute("INSERT INTO confirmation_links VALUES (?, ?)", (identifier, identifier))
            c.execute("INSERT INTO buyer_sessions VALUES (?)", (identifier,))
            c.execute("INSERT INTO buyer_requests VALUES (?)", (identifier,))
            c.execute("INSERT INTO delivery_events VALUES (?)", (identifier,))
    return path, target, other


def test_removes_only_exact_order_with_recoverable_backup_and_preserved_profiles(tmp_path):
    path, target, other = fixture_database(tmp_path)
    result = delete_test_order(path, target)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT id FROM orders").fetchall() == [(other,)]
        assert c.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM rider_profiles").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM buyer_requests").fetchone()[0] == 1
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
    with sqlite3.connect(result["backup"]) as c:
        assert c.execute("SELECT count(*) FROM orders").fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM buyer_sessions").fetchone()[0] == 2


@pytest.mark.parametrize("history", ["rider", "route", "cash"])
def test_refuses_order_with_route_rider_or_cash_history(tmp_path, history):
    path, target, other = fixture_database(tmp_path)
    with sqlite3.connect(path) as c:
        if history == "rider":
            c.execute("INSERT INTO delivery_assignments VALUES (?)", (target,))
        elif history == "route":
            c.execute("INSERT INTO workflow_routes VALUES (?)", (json.dumps({"order_ids":[str(UUID(target))]}),))
        else:
            c.execute("UPDATE orders SET parsing_metadata=? WHERE id=?", (json.dumps({"parcel":{"collection":{"actual":100}}}), target))
    with pytest.raises(ValueError):
        delete_test_order(path, target)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT count(*) FROM orders").fetchone()[0] == 2
    assert not (tmp_path / "backups").exists()
