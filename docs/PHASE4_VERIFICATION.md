# Phase 4 verification

Verified locally on 2026-10-20 using Windows, Python 3.14.7, SQLAlchemy 2.0.55 and
Alembic 1.20.0. No cloud database, paid API, deployment, or Git push was used.

## Audit and implementation

Before changes, the complete existing suite passed: **203 tests**. README, API contract,
Phase 3 verification, schemas, configuration, and deterministic/hybrid services were read.
The existing parser, normalization, provider boundary, privacy protections, and triage
were reused. Existing regression tests were retained unchanged.

The backend now saves raw parsed orders or explicitly structured orders, lists and searches
them, corrects fields with provenance, enforces status transitions, and records delivery
events. AI failure retains deterministic results and does not prevent saving a draft.
Legacy fixed mock parsing is never used to create persisted orders. The original parse
endpoint remains stateless and backward compatible.

## Architecture and changed files

- `backend/app/db/{models,session,migrations}.py`: SQLAlchemy models, session/engine
  management and Alembic upgrade helper; no automatic table creation at app startup.
- `backend/alembic.ini`, `backend/migrations/`: explicit initial migration and environment.
- `backend/app/domain/lifecycle.py`: roles, statuses, allowed transitions and edit policy.
- `backend/app/schemas/management.py`: validated requests and stable stored-order responses.
- `backend/app/services/order_management.py`: scoped queries, parsing persistence,
  manual correction, confidence recalculation and atomic events.
- `backend/app/api/order_management.py`: protected order routes and local user lookup.
- `backend/app/core/{dev_access,order_errors,access_logging}.py`: local access checks,
  sanitized errors and access-log query stripping.
- Updated `app/main.py`, `app/core/config.py`, dependency definitions, lock file,
  `.env.example`, repository `.gitignore`, README and frontend API contract.
- `backend/scripts/init_local.py`: idempotent local-only bootstrap; creates ignored
  configuration only when absent, generates a private token, and seeds synthetic profiles.
- `backend/scripts/smoke_orders.py`: real HTTP lifecycle against a fresh isolated database.
- `backend/tests/test_order_management.py`: 85 additional tests including parametrizations.
- `backend/MANIFEST.in`: includes migration sources in source distributions; migration
  commands are documented for a source checkout, not a standalone wheel installation.

## Database schema and migration

`0001_order_management` creates three tables:

| Table | Main data and constraints |
| --- | --- |
| users | UUID id, name, unique email, checked Merchant/Dispatcher/Rider/Admin role, UTC timestamps |
| orders | UUID id/merchant FK, all requested customer/address/message fields, nullable coordinates, exact whole-MMK COD, confidence/reasons, parsing and AI status, field source JSON, parsing metadata JSON, lifecycle status, UTC timestamps, optimistic version |
| delivery_events | UUID id/order FK, checked event type, previous/new status, minimal metadata, UTC creation time |

COD uses `Numeric(12,0)` with range 0..1,000,000,000; API returns an exact digit string.
Coordinates use `Numeric(10,7)`, paired-null/range constraints, and are never generated.
UUID and JSON types compile to PostgreSQL UUID/JSONB; timestamps are timezone aware.
SQLite restores UTC awareness on reads, enables foreign keys for every connection, and
uses isolated file databases in tests. Status/role enums have portable CHECK constraints.
Foreign keys restrict deletion. Query indexes cover merchant/date, status/confidence and
event order/date. `building_floor_unit` additionally preserves unsplit parser output;
building, floor and unit stay null until supplied explicitly.

Order plus event writes commit atomically before success. Failed operations roll back;
SQL/credentials/customer data are excluded from public errors and application error logs.
PATCH requires `expected_version`; stale or concurrently changed rows return 409.

The initial migration was applied to a fresh isolated SQLite database and to the private
local development database. Migration tests cover idempotence, metadata drift, constraints,
foreign keys, downgrade/re-upgrade on an empty isolated database, and offline PostgreSQL DDL.
**A live PostgreSQL server was not available or contacted.** PostgreSQL execution remains
a verification task before production use; the optional psycopg dependency is not installed.

## Endpoints

Existing: `GET /health`, `POST /api/orders/parse`.

Protected local endpoints:

- `POST /api/orders` (201), `GET /api/orders` (paginated, status/confidence/search filters).
- `GET /api/orders/{id}`, `PATCH /api/orders/{id}`.
- `PATCH /api/orders/{id}/status`, `GET /api/orders/{id}/events` (paginated).
- `GET /api/users?role=Merchant` for local merchant selection; no user-write HTTP API.

See [API_CONTRACT.md](API_CONTRACT.md) for complete requests, response fields, transitions,
errors, limits and JavaScript examples. Full actual HTTP requests/responses with synthetic
test values are in [PHASE4_SAMPLE_RESPONSES.json](PHASE4_SAMPLE_RESPONSES.json).

## Actual verification results

- Full suite: **288 passed in 13.09 seconds** (203 existing + 85 new cases).
- Real HTTP smoke: health 200, unauthenticated orders 401, raw and structured creation
  201, get/list/search/correction 200, stale update 409, invalid raw input 422.
- Lifecycle exercised: DRAFT -> NEEDS_REVIEW -> AWAITING_CONFIRMATION -> CONFIRMED ->
  READY_FOR_DISPATCH -> ASSIGNED -> OUT_FOR_DELIVERY -> DELIVERED.
- Reopened the isolated database after stopping Uvicorn: **2 orders and 10 events**
  persisted. The delivered order remained **AMBER**, with null coordinates.
- Example raw request used Burmese digits, a Hlaing address, and COD 25000; actual output
  normalized phone to `09791234567`, township to `Hlaing`, COD to `"25000"`, and retained
  original input and field provenance. The mock AI returned no fabricated enrichment.
- Tests also cover merchant ownership, rider denial, production fail-closed behavior,
  remote denial despite forwarded headers, rollback after commit failure, concurrent
  sessions, literal search, invalid coordinates/money/IDs/pagination, manual source changes,
  confidence invalidation after township edits, AI unavailability and test isolation.

Final checks also passed:

- `python -m ruff check .`: all checks passed.
- `python -m ruff format --check .`: 52 files already formatted.
- `python -m alembic current`: `0001_order_management (head)` on local development storage.
- `python -m pip check`: no broken requirements.
- Repeated `scripts/smoke_orders.py`: 2 persisted orders / 10 events in a fresh isolated DB.
- `scripts/smoke_http.py` in both hybrid and rules modes: health and parsing 200,
  missing-phone RED, valid phone/township AMBER, COD 25000, empty request 422.
- `python -m pip wheel --no-deps . --wheel-dir dist`: built
  `lannpya_backend-0.4.0-py3-none-any.whl`. An initial optional build attempt with
  `--no-build-isolation` failed because setuptools was absent from the runtime venv;
  the normal isolated build installed its declared build dependency and succeeded.

No remaining automated test, lint, formatting, migration or HTTP verification failure
was observed. Live PostgreSQL execution remains unverified as described above.

## Security boundaries and limitations

Fresh settings disable order management. `scripts/init_local.py` configured this checkout's
ignored `.env` and local SQLite database, with one synthetic dispatcher and merchant and
no seeded orders. The secret is never printed or committed; existing `.env` is not overwritten.

Order management requires local/test environment, explicit enablement, an actual loopback
socket peer, a strong configured `X-Dev-Access-Token`, and a configured server-side actor
that exists in the database. Production fails closed even if enablement is requested.
Merchant access is scoped to its own records; dispatchers/admins can manage local records;
riders are denied. Client-supplied identity headers have no effect. Responses use no-store.

This is a single-actor local development gate, **not production authentication or tenant
authorization**. Do not expose through tunnels/reverse proxies or deploy with real customer
data. CORS is not authentication. Local processes/administrators can read local files;
Windows file ACLs, encryption, backup and retention are not provided by this phase.

No trusted location dataset is configured, so GREEN remains disabled. Explicit dispatcher
acknowledgement permits operational dispatch of AMBER orders but does not verify their
location or change confidence. CONFIRMED records an operator assertion, not buyer identity
verification. Corrections reset active pre-dispatch states to NEEDS_REVIEW; assigned,
out-for-delivery and terminal orders cannot be edited. AI availability metadata records the
creation parse and is not refreshed by manual correction. Encoding warnings remain visible.
Events store changed field names and actor IDs, not old/new customer values; this is not a
complete immutable field-value audit trail. ASSIGNED is status bookkeeping only: no rider
assignment system was added. There is no deletion endpoint, database encryption, production
authentication, buyer flow, tracking, routing, billing or real AI provider.

## Phase 5 decisions

Choose production authentication and tenant membership/authorization before public access.
Select and verify a PostgreSQL hosting/environment, then run migrations and integration
tests against a disposable PostgreSQL instance. Review trusted location data licensing and
verification semantics before enabling GREEN. Define buyer verification and rider assignment
workflows, privacy retention, audit requirements and backup policy before implementing them.
No decision blocks local frontend integration in Phase 4.
