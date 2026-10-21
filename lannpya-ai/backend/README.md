# LannPya AI backend — Phase 7

## Connected three-role workspace

The frontend in `D:/Zero_Lag/api.html` now calls these APIs directly. Local startup:
` .venv/Scripts/python.exe -m scripts.run_workspace ` from this backend directory.
See [API integration guide](../../API_INTEGRATION.md) for runtime credentials,
customer/rider walkthrough, new route/cash extensions and remaining limits.
The starter is loopback-only and creates Admin/Ko Aung/Ko Wai without a merchant.
It uses its own persistent database; no old records are reset or auto-imported.
`--check` verifies real HTTP startup/identities and stops all processes afterward.

FastAPI REST backend, independent of frontend technology. Deterministic local address
extraction with encoding normalization, Myanmar phone validation, contextual COD parsing,
controlled Yangon township aliases, field evidence, and explainable triage. Default hybrid
mode adds a sanitized, strictly validated provider boundary with graceful degradation.
SQLAlchemy 2.x and Alembic add persistent order management, manual corrections, provenance,
status transitions and delivery events. PostgreSQL is the production target; SQLite supports
local development and isolated tests. AI remains a local mock; no external calls are made.
Buyer confirmation adds private links, three-failure lockout, short-lived buyer Bearer
authorization, auditable location/availability requests and dispatcher review. No frontend,
messaging integration or production authentication is included.
Rider Copilot adds User-backed operational profiles, persistent assignments, scoped
delivery queues, snapshot polling, navigation links and idempotent delivery/COD actions.

Frontend starting point: [handoff](../docs/FRONTEND_HANDOFF.md),
[safe demo](../docs/DEMO_GUIDE.md), [OpenAPI export](../docs/OPENAPI.json),
and [public-demo blockers](../docs/PRODUCTION_BLOCKERS.md).

## Run locally (PowerShell)

From `C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI\backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

The virtual environment and development dependencies have been installed locally.
Activation is optional. Open `http://127.0.0.1:8000/docs` for interactive API docs,
or `/openapi.json` for the machine-readable contract.

For another checkout (Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe scripts\init_local.py
```

`pyproject.toml` defines supported dependency ranges; `requirements-dev.lock` records
the exact versions verified in this workspace (Python 3.14 on Windows).

Local setup has already been completed here: ignored `backend/.env` contains a generated
private access token and server-side actor ID; `backend/data/lannpya_dev.sqlite3` is migrated
with synthetic dispatcher and merchant profiles. No orders were seeded. `init_local.py`
is idempotent, never overwrites an existing `.env`, and prints no token. For a fresh checkout
it generates missing local configuration and migrates SQLite. Existing custom configuration
is validated rather than silently replaced. Get merchant IDs through the protected
`GET /api/users?role=Merchant` lookup.

Apply later migrations from this source checkout using:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

The application never creates tables or migrates on startup. PostgreSQL needs the optional
`postgres` dependency extra and an explicitly configured connection; none was contacted
in this phase. The default local SQLite URL resolves relative to this backend directory.

## Configuration

Defaults work without `.env`. Optional settings go in `backend/.env` (ignored by Git)
or environment variables; `.env.example` contains no secrets. Environment variables
override `.env`. The `.env` location is resolved relative to the backend package.

- `LANNPYA_AI_PROVIDER=mock`: local enrichment mock; `disabled` disables assistance.
  Unknown/unregistered providers fail startup; no external provider is installed.
- `LANNPYA_PARSER_MODE=hybrid`: default rules-first parsing with optional AI enrichment.
  `rules` keeps the Phase 2 path; `mock` retains the Phase 1 fixed demo/regression path.
- `LANNPYA_AI_TIMEOUT_SECONDS=3.0`: positive seconds, at most 30; supplied to the adapter
  and enforced around its cancellable async invocation.
- `LANNPYA_AI_MAX_INPUT_CHARS=2000`: 128–4,000 sanitized address-fragment characters;
  at most eight fragments, each at most 512 characters. Oversized clauses are omitted.
- `LANNPYA_CORS_ORIGINS`: JSON array of exact HTTP(S) origins, without trailing slash.
  Defaults include localhost ports 5173, 3000, 5500 and 127.0.0.1:5500.
  Empty array disables cross-origin access. Credentials are disabled.
- `LANNPYA_ENVIRONMENT=local`: `local`, `test` or `production`. Production order APIs
  always fail closed until authenticated authorization is implemented.
- `LANNPYA_ORDER_MANAGEMENT_ENABLED=false`: safe default in a fresh environment;
  bootstrap enables local order management explicitly.
- `LANNPYA_DATABASE_URL`: SQLAlchemy connection URL; default
  `sqlite+pysqlite:///./data/lannpya_dev.sqlite3`. Never commit database credentials.
- `LANNPYA_DEV_ACCESS_TOKEN`, `LANNPYA_DEV_ACTOR_ID`: private local token (minimum 32
  characters) and existing server-side user UUID. Clients cannot select identity or role.

Never put provider credentials in frontend code. CORS is a browser policy, not authentication.
Saved-order APIs require `X-Dev-Access-Token` and a loopback socket peer. Merchants are scoped
to their own records, dispatchers/admins can manage local orders, and riders are denied.
Health and stateless parsing remain token-free. This is a single-actor development mechanism,
not production authentication. Do not expose the server through tunnels or reverse proxies.
Never bundle the local token into a public frontend. See the API contract for runtime local
JavaScript integration and the verification report for the complete security boundaries.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe scripts\smoke_http.py
.\.venv\Scripts\python.exe scripts\smoke_http.py --mode rules
.\.venv\Scripts\python.exe scripts\smoke_orders.py
.\.venv\Scripts\python.exe scripts\smoke_buyer.py
.\.venv\Scripts\python.exe scripts\smoke_delivery.py
.\.venv\Scripts\python.exe scripts\demo_mvp.py
.\.venv\Scripts\python.exe scripts\export_contract.py
node --test ..\docs\examples\lannpya-client.test.mjs
```

Tests cover the original 30 Phase 1 regressions (explicit mock mode), actual Burmese and
English extraction, normalized digit/phone formats, COD/time separation, ambiguity,
Zawgyi warnings/failures, trusted-catalog gating, privacy, request validation, and CORS.
Phase 3 tests additionally cover strict AI JSON/grounding, field protections, provider
switching, timeout/cancellation, rate limits, private errors, and graceful degradation.
Phase 4 adds database migration/constraint, order CRUD, actor scope, lifecycle/event,
transaction rollback, concurrent version conflict and invalid-input tests. All database
tests use isolated temporary databases; the HTTP order script uses a new ignored database
under `data/verification` and writes actual synthetic samples to the repository docs.

## Structure

```text
backend/
  app/
    main.py                 # application factory, CORS, error handlers
    api/routes.py           # stable endpoints; rules/mock selection
    schemas/orders.py       # validated request, address, confidence, response
    schemas/errors.py       # public error contract
    services/orders.py      # orchestration and conservative mock classification
    services/deterministic.py # default real parsing orchestration
    services/hybrid.py        # sanitized enrichment, grounded merge, final rules triage
    parsing/normalization.py # local Zawgyi handling + Unicode digits
    parsing/rules.py         # deterministic field extraction and evidence
    parsing/places.py        # alias matching + server-only trusted catalog seam
    parsing/triage.py        # explainable GREEN/AMBER/RED checks
    data/yangon_townships.json # initial curated dictionary (33 names, partial coverage)
    ai/base.py              # abstract async provider + validated I/O + error type
    ai/mock.py              # deterministic null-field mock, no network calls
    ai/factory.py           # configured provider selection
    ai/privacy.py           # allowlisted minimal future AI context; never called remotely
    ai/extraction.py        # new sanitized enrichment interface and strict response schema
    ai/adapters/mock.py     # local mock and disabled adapters, no generated sample values
    ai/sanitization.py      # fragment allowlist and character-preserving PII masking
    ai/gateway.py           # timeout, typed failures, bounded/strict JSON validation
    core/config.py          # validated environment settings
    core/dev_access.py      # fail-closed local token and actor checks
    core/access_logging.py  # strips private queries from Uvicorn access logs
    db/models.py            # User, Order, DeliveryEvent; portable SQLAlchemy types
    db/session.py           # engine, sessions, SQLite FK enforcement
    db/migrations.py        # explicit Alembic upgrade helper
    domain/lifecycle.py     # status transitions and role policy
    schemas/management.py   # create, correction, status and stored-order contracts
    services/order_management.py # persistence, provenance, confidence and events
    api/order_management.py # protected order APIs and local merchant lookup
  tests/test_api.py
  tests/test_rules_parser.py
  tests/test_hybrid.py
  scripts/smoke_http.py      # real HTTP smoke check, cleans up its server
  scripts/init_local.py      # private local bootstrap, no seeded orders
  scripts/smoke_orders.py    # isolated real HTTP order lifecycle verification
  migrations/versions/0001_order_management.py
  alembic.ini
  .env.example
  pyproject.toml
  requirements-dev.lock
  README.md
docs/
  API_CONTRACT.md            # located in the repository-level docs directory
  PHASE1_DECISIONS.md
  PRD_ALIGNMENT.md
  PHASE2_VERIFICATION.md
  PHASE3_VERIFICATION.md
  PHASE4_VERIFICATION.md
  PHASE4_SAMPLE_RESPONSES.json
  PHASE5_VERIFICATION.md
  PHASE5_SAMPLE_RESPONSES.json
  PHASE6_VERIFICATION.md
  PHASE6_SAMPLE_RESPONSES.json
```

## Extending the provider later

New adapters implement `AddressExtractionProvider.extract(SanitizedAddressInput,
timeout_seconds=...)`, returning JSON matching `AIExtractionResponse`. That schema permits
only nullable landmark/floor-unit/instruction suggestions with input fragment IDs and
quotes; it forbids all other fields and implicit type coercion. `ExtractionGateway`
validates responses, handles availability, and enforces the configured async deadline.
Expected adapter errors map to `ExtractionTimeoutError`, `ExtractionRateLimitError`, or
`ExtractionUnavailableError`; exception details never enter logs/API availability messages.
No retries are performed. Real HTTP adapters must also enforce transport timeouts and
response size limits and must cooperate with cancellation.

`ai/factory.py` and the settings allowlist are the only provider-selection wiring.
Tests inject an adapter using `create_app(extraction_provider=...)` or override
`api.routes.get_extraction_provider`. Business rules and frontend endpoints do not
depend on the vendor. External adapters are deliberately blocked at the gateway in
Phase 3 even if injected. Adding a real provider later requires explicit authorization,
a reviewed server-side secret configuration, an adapter, approved privacy policy,
and an authorized change to that external-call gate. No real API key is used or needed now.

The Phase 1 `AddressProvider`/`ProviderInput.raw_text` interface remains only for the
fixed demo and its regression tests; it must never be wired to external AI. The older
`build_minimal_ai_input` township-only helper is preserved for compatibility. Hybrid mode
instead uses `prepare_ai_request`: mask phone/name/COD evidence and other known sensitive
patterns, drop sensitive/unnecessary clauses, retain useful bounded address fragments,
and keep source-offset mappings only on the server. Real orders are not sent wholesale.
This cannot reliably identify every unlabelled person name or sensitive address detail.

The installed mock returns null enrichment fields and explicitly reports `ai.status=mock`.
No simulated landmark is merged. Parsing AI failures return HTTP 200 with deterministic
results and an explicit `ai` status; order creation persists the results as a draft (201),
and dispatchers can correct saved fields through the protected PATCH endpoint.
Grounded suggestions can fill missing enrichment fields only; ambiguity remains unresolved
with a review-only suggestion. Any AI field needs human review and cannot grant GREEN.

## Location and encoding limitations

No trusted street/landmark dataset was supplied. The default catalog is empty, so the
running backend intentionally never labels an order GREEN. The GREEN rule is implemented
and tested with an isolated synthetic catalog. Later, reviewed entries with township,
field, aliases, dataset and source URL can be injected using
`create_app(location_catalog=LocationCatalog(...))`. Never accept this evidence from clients.
The township alias dictionary is not a map, and a dataset name match is not a verified pin.

Encoding uses Google's local Myanmar Tools detector plus python-myanmar conversion.
Detection is heuristic; converted text requires review and is never automatically GREEN.
Ambiguous encoding or failed conversion is explicitly flagged RED. This is not a guarantee
of normalization for every mixed-font, Shan, Mon, or malformed input.

See [API contract](../docs/API_CONTRACT.md), [PRD alignment](../docs/PRD_ALIGNMENT.md),
and [Phase 6 verification](../docs/PHASE6_VERIFICATION.md).
Earlier phase documents remain historical records. Phase 2 was re-audited successfully
with all 131 previous tests before Phase 3 development began.

## Buyer confirmation (Phase 5)

The new migration `0002_buyer_confirmation` adds confirmation_links, buyer_sessions,
location_references, buyer_requests and buyer_rate_limits. It preserves existing orders,
users and delivery events. This checkout's local DB is migrated; `.env` was preserved.

Protected merchants/dispatchers generate `/confirm/<token>` frontend links through
`POST /api/orders/{id}/confirmation-link`. A public minimal card contains no address,
phone or pin. The buyer verifies four ASCII phone digits via `/api/confirm/{token}/verify`
and receives a separate 15-minute Bearer credential for details/location/response actions.
Tokens are stored as hashes, and three failed checks lock the link across sessions and
concurrent requests. Four digits plus a private link are limited knowledge verification,
not proof of phone ownership. All buyer APIs also fail closed in production configuration.

Default link lifetime is 72 hours. At delivery, an active eligible link becomes minimal
view-only for 24 hours; sensitive actions close immediately. Revocation, cancellation,
phone corrections, session rotation and expiry invalidate capabilities. The database-backed
rate limiter defaults to 60 public and 10 verification requests per socket peer/minute.
Access logs redact capability paths and queries; no request bodies or headers are logged.
Buyer credentials use Authorization headers only, without cookies or frontend storage.

Initial pins are stored for review and do not silently replace dispatch coordinates.
An independently checked dispatcher anchor **plus reviewed township boundaries** is needed
for automatic <=500m same-township adjustments. Default `TownshipBoundaryResolver` returns
unknown, so no automatic geofence approval occurs here. Tests inject synthetic boundaries;
they are never used by the running application. Buyer pins never become reference anchors,
and coordinates never grant GREEN. Larger/cross-township moves require dispatcher review.
The protected buyer-requests endpoints expose proposals, previous values and resolutions.

`.env.example` documents `LANNPYA_BUYER_*` settings: frontend base URL, lifetimes, limits,
rescheduling/security-delivery policy, Yangon cutoff, notice, scheduling horizon and optional
indicative cross-township fee. Rescheduling and leave-with-security are disabled by default:
requests are saved for review, without promising courier acceptance or collecting fees.
No paid service, real AI provider or additional runtime dependency is needed.

See the [buyer API contract](../docs/API_CONTRACT.md#phase-5-buyer-confirmation-flow-and-security-boundary)
for full JavaScript integration, errors, UTC-offset time windows and credential handling.

## Rider Copilot (Phase 6)

Migration `0003_rider_copilot` adds rider_profiles (one per Rider user),
delivery_assignments (retained history, one active assignment/order) and
rider_action_receipts (idempotent action results). Existing Rider users receive OFFLINE
profiles, and existing orders/buyer records are preserved. The local DB is migrated;
the private `.env` was not rewritten. No new runtime dependency is required.

Dispatcher/Admin can create/list riders, set availability, assign ready orders, unassign
before start, and set stop sequences. Rider actors can retrieve/update only their own
operational profile and read/act on their own assigned deliveries. Order-management and
buyer-audit APIs remain unavailable to Rider actors. Every route uses the existing
loopback-only development token and server-bound identity; production stays fail-closed.

Each local backend instance represents one configured actor. `scripts/smoke_delivery.py`
creates its own isolated database and launches three short-lived loopback instances with
separate merchant/dispatcher/rider identities and secrets. It verifies the full real HTTP
workflow and stops its servers automatically. It never changes the normal local database
or `.env`, and its JSON samples redact all capabilities. No public login/switch-actor API
was introduced, and no deployment or messaging is performed.

`GET /api/riders/{id}/queue` returns a bounded full active snapshot with an opaque cursor.
Poll every five seconds; unchanged:true preserves the displayed list, otherwise replace
it, including empty results after removal/completion. Order is on-road status, confirmed
time window, dispatcher sequence and stable tie-breakers. This is not route optimization.
Only approved canonical buyer updates appear; late pre-start changes require unassigning,
returning to review, approving, confirming readiness and reassigning under Phase 5 rules.

Navigation URLs contain only explicitly buyer-confirmed coordinates and mode, never phone
or notes. Missing/unconfirmed pins return navigation_ready:false. Buyer-confirmed does not
mean independently geospatially verified; AMBER remains AMBER. The backend calls no maps API.

START/DELIVERED/FAILED rider actions enforce assignment ownership, lifecycle, latest order
version and request UUID idempotency. Positive COD requires explicit cod_collected:true
by default; unknown COD must be corrected, and prepaid must be explicit zero. Failure
requires a reason code; optional private notes stay off event metadata and navigation URLs.
Completion atomically closes assignment, records actor/event/receipt, removes the queue
item and applies the buyer link's 24-hour delivered view-only policy. No payment is processed.

Real assigned deliveries cannot bypass these rules through generic status updates. Legacy
status-only lifecycle remains for earlier records but does not invent a rider/assignment;
its positive-COD completion also now requires explicit collection confirmation. See the
[API contract](../docs/API_CONTRACT.md#phase-6-rider-access-and-delivery-workflow) for the
new completion precondition and every request/response/error.

Configuration: `LANNPYA_RIDER_MAX_ACTIVE_ASSIGNMENTS=100` (1..200) and
`LANNPYA_RIDER_REQUIRE_COD_CONFIRMATION=true`. Courier policy may explicitly disable COD
confirmation; collection is never silently asserted. Optional rider contact values remain
null when absent. A reserved internal email identifier satisfies the older required User
email field when contact email is omitted; it is not exposed as actual rider contact.

## Frontend integration readiness (Phase 7)

All dispatcher, buyer and rider workflows have documented endpoints. This phase adds
typed OpenAPI outputs for the remaining buyer management responses, exposes Retry-After
to allowed browser origins, and ensures sanitized 500 responses receive CORS headers.
Request/response fields, business rules and security restrictions remain compatible.
No migration or new runtime dependency was needed; application/package version is 0.7.0.

`scripts/demo_mvp.py` creates a fresh ignored SQLite run directory, fictional Burmese data,
three independent local actor servers, migrations and credentials; verifies real HTTP
workflows/preflights; stops servers and reopens storage. Repeat runs preserve normal data
and `.env`. --serve keeps these isolated instances alive until Ctrl+C for UI integration:

```powershell
.\.venv\Scripts\python.exe scripts\demo_mvp.py --serve --frontend-origin http://localhost:5173
```

The private run directory contains base URLs/IDs/credentials and a fresh buyer link.
Do not expose it through a static frontend, commit it, or publish its tokens. Shareable
samples redact capabilities and complete constructed fixture phone strings. No real
customer data is imported; no real phone ownership/unassignment, AI result, location or
GREEN proof is claimed. The synthetic (0,0) pin tests manual review only.

The API snapshot and dependency-free vanilla JS helper live under repository docs, not
frontend source. React usage is documented without installing/selecting a framework.
Real browser/mobile UI remains unimplemented/unverified. A public shared-browser demo
requires proper authentication and secure deployment; the private development token is
not a substitute, and production stays fail-closed.

See [Phase 7 verification](../docs/PHASE7_VERIFICATION.md) for actual results and limitations.
