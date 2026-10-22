# PostgreSQL Migration & Compatibility Analysis — LannPya AI (လမ်းပြ)

This document provides a technical audit of PostgreSQL compatibility, dialect differences, and migration execution procedures for LannPya AI.

---

## 1. Dialect Compatibility Matrix

| Feature | SQLite (Local Dev / Test) | Supabase PostgreSQL (Cloud Runtime) | Compatibility Strategy |
| :--- | :--- | :--- | :--- |
| **Primary Keys** | `CHAR(32)` / Text | Native `UUID` | Handled automatically via `sa.Uuid()` |
| **JSON Data** | Text representation (`JSON`) | Binary JSON (`JSONB`) | `JSON().with_variant(JSONB(), "postgresql")` |
| **Timestamps** | ISO-8601 Strings without timezone | `TIMESTAMP WITH TIME ZONE` | Enforced via `UTCDateTime` TypeDecorator |
| **COD Currency** | `NUMERIC(12, 0)` | `NUMERIC(12, 0)` | Exact integer Kyat values; no float rounding |
| **Partial Indexes** | Supported via `sqlite_where` | Supported via `postgresql_where` | Declared on `DeliveryAssignment` index |
| **Constraint Alterations** | Requires Table Recreation (`batch_alter_table`) | Native `ALTER TABLE DROP/ADD CONSTRAINT` | Handled conditionally in Alembic revisions |
| **Upserts (ON CONFLICT)** | `sqlite_insert.on_conflict_do_update` | `postgres_insert.on_conflict_do_update` | Branching in `app/core/buyer_access.py` |

---

## 2. Alembic Migration Revisions

The migration directory [`backend/migrations/versions/`](file:///c:/Users/ZL_sht_H/Documents/Projects/lann_pya/backend/migrations/versions) contains 5 sequential revisions:

```text
base
 └── 0001_order_management.py (Initial tables: users, orders, delivery_events)
      └── 0002_buyer_confirmation.py (confirmation_links, buyer_sessions, location_references, buyer_requests, buyer_rate_limits)
           └── 0003_rider_copilot.py (rider_profiles, delivery_assignments, rider_action_receipts)
                └── 0004_workflow_routes.py (workflow_routes)
                     └── 0005_routing_plans.py (routing_plans, routing_rate_limits) [HEAD]
```

### Constraint Evolution on `delivery_events`
As new domain capabilities were introduced, the `ck_events_type` check constraint on `delivery_events` expanded:
* Revision 0001: `'ORDER_CREATED'`, `'ORDER_CORRECTED'`, `'STATUS_CHANGED'`
* Revision 0002: Added buyer verification and location proposal events.
* Revision 0003: Added rider assignment, delivery start, completion, and failure events.

In PostgreSQL, Alembic automatically executes:
```sql
ALTER TABLE delivery_events DROP CONSTRAINT ck_events_type;
ALTER TABLE delivery_events ADD CONSTRAINT ck_events_type CHECK (event_type IN (...));
```
Without requiring expensive table copy or data migration.

---

## 3. Migration Commands & Procedures

### Applying Migrations
To upgrade the connected database to the latest schema:
```bash
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

### Inspecting Offline PostgreSQL DDL
To preview all generated PostgreSQL DDL before applying:
```bash
.\.venv\Scripts\alembic.exe -x database_url="postgresql+psycopg://user:pass@host:5432/db" upgrade head --sql
```

### Verifying Migration Status
Execute the schema verifier to inspect the live database:
```bash
.\.venv\Scripts\python.exe scripts/verify_database.py
```
Outputs current revision, head comparison, table discovery, and connection health.

### Safe Rollback Procedure
To roll back one revision:
```bash
.\.venv\Scripts\alembic.exe downgrade -1
```

> [!CAUTION]
> Never execute downgrades on a populated production or hackathon demonstration database. All schema changes must be tested in an isolated sandbox first.
