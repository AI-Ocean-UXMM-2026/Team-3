# MTT database architecture

The authoritative live store is the existing Python SQLAlchemy database. The MTT
browser domain remains an explicitly separate DEMO_SIMULATION; its fixture coordinates,
township rectangles, localStorage and offline replay never become live records.

## Preserved schema

Fresh isolated SQLite migration produced 12 application tables and `alembic_version`:

- `users`, `orders`, `delivery_events`.
- `confirmation_links`, `buyer_sessions`, `buyer_requests`, `buyer_rate_limits`.
- `location_references`.
- `rider_profiles`, `delivery_assignments`, `rider_action_receipts`.
- `workflow_routes`.

Head remains `0004_workflow_routes`; migrations 0001–0004 were preserved. No new
schema migration was needed. Running upgrade twice on the fresh temporary database
succeeded. SQLAlchemy PostgreSQL DDL compiled for all 12 application tables;
this is an offline compatibility check, not a live PostgreSQL migration test.
Machine evidence: [AUDIT_EVIDENCE.json](AUDIT_EVIDENCE.json).

Orders retain merchant ownership, original/normalized text, provenance, exact
`Numeric(12,0)` COD, paired `Numeric(10,7)` coordinates, status, confidence and
timestamps. Parcel context, collection/incident history and route linkage remain JSON
(JSONB on PostgreSQL). Order, rider and route versions protect concurrent writes.
Foreign keys and SQLite foreign-key enforcement remain enabled.

Link and session records retain token hashes, expiry, phone binding and lockout.
Buyer requests preserve proposed and prior values independently of the canonical order.
Dispatcher review applies approved changes transactionally. An approved buyer pin is
not inserted as an immutable trusted location reference or independently verified GREEN.

## Storage isolation and persistence

`npm.cmd start -- --state mtt-local --port 8781` owns:
`backend/data/integrated-workspaces/mtt-local/sandbox.sqlite3` in this worktree.
It never selects the regular development database. Normal shutdown preserves that file.
`--temporary` instead owns and cleans a generated temporary directory.
Persistent workspace reset remains disabled. No user database was deleted or downgraded.

The adapter reads saved records, sends existing versioned API mutations and refreshes
after acceptance. It never mirrors failed writes into localStorage. Batch order imports
are separate transactions: partial acceptance is reported with the accepted count;
review the board before retrying to prevent duplicate creation.

An actual Chromium lifecycle verifies database-backed creation, buyer review, rider
delivery and page refresh. A separate API lifecycle closes/reopens the application and
database, then verifies DELIVERED, exact COD collection, approved pin and unchanged event
count. That test uses FastAPI TestClient lifespans. The additional
`npm.cmd run verify:mtt-restart` utility also restarted an actual local Uvicorn process
and verified one delivered COD order and all 11 events over real HTTP after reopening
the same owned temporary database. Neither is a production-database restart claim.

## PostgreSQL preparation and remaining work

`Database` already supports `postgresql+psycopg`, `pool_pre_ping`, hidden SQL parameters,
UTC-aware timestamps, UUIDs, exact numerics and PostgreSQL JSONB. Install the existing
optional `postgres` extra only in an approved PostgreSQL environment. Set a server-side
URL with provider-required TLS, for example the placeholder in `.env.example` using
`sslmode=require`; certificate policy/pooling must match the selected database host.

No PostgreSQL URL, server or Supabase project was configured. Live connections,
Alembic execution on PostgreSQL, lock contention, TLS certificates and connection-pool
limits remain unverified. Test these on an isolated database after provisioning is
approved; never migrate existing customer data as part of this local integration.
Production authorization and deployment configuration remain separate release blockers.
