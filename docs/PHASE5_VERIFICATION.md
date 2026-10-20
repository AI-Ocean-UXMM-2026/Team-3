# Phase 5: buyer confirmation verification

Verified on 2026-10-21 in the existing Windows/Python 3.14.7 workspace. Backend only;
no frontend edits, messaging, external account, cloud database, deployment or Git push.

## Audit and reuse

The Phase 4 architecture, README, API contract, verification report, database migration,
status transitions and development-only actor checks were reviewed before development.
Baseline: **288 tests passed in 11.93 seconds**. The existing SQLAlchemy sessions,
order ownership, validation, source metadata, deterministic confidence and lifecycle were
reused. The only changed existing test expectations are the migration's new table set and
head revision; the previous regression cases remain in the full suite.

## Implemented features

- Protected link generation and revocation; 256-bit unpredictable URL-safe capabilities,
  with SHA-256 token hashes stored instead of plaintext.
- Minimal public card without name, phone, address, pin, COD or private instructions.
  Shop/item branding remains null/unavailable rather than invented from user profiles.
- Last-four verification with exact ASCII format, constant-time comparison, persistent
  three-failure lockout and generic error messages. Successful checks do not reset failures.
- Separate hashed 15-minute buyer authorization bound to the link/order and generation;
  repeat verification rotates sessions. Headers only, no cookies or frontend-trusted flag.
- Persistent atomic per-peer fixed-window rate limiting; forwarded headers are not trusted.
- Initial pin proposals, Haversine distance calculation, immutable attested anchors and
  server-owned township resolver. No client parameters can select zone or claim verification.
- Availability, rescheduling, instructions and leave-with-security requests with validated
  timezone-aware windows, courier enable flags, notice/horizon rules and Yangon cutoff.
- Private proposal/previous-value audit, buyer field provenance, dispatcher approve/reject,
  optimistic version checks, idempotent retries, lifecycle events and atomic rollback.
- Unresolved buyer reviews block protected CONFIRMED/READY_FOR_DISPATCH transitions.
  Buyer AVAILABLE can set CONFIRMED only when critical validation/review does not block it.
- No-store/no-referrer/noindex/nosniff buyer responses. Uvicorn token paths/query strings
  are redacted; unexpected exceptions are caught before Uvicorn can print private details.

## Schema and migration

Alembic **0002_buyer_confirmation** extends the delivery-event type CHECK and creates:

| Table | Purpose |
| --- | --- |
| confirmation_links | Order FK, unique token hash, phone binding, UTC expiry/revocation/lock/verification times, bounded failure counter, session generation, lock nonce |
| buyer_sessions | Link FK, unique authorization hash, generation and UTC expiration |
| location_references | One immutable dispatcher-attested coordinate/township anchor per order, source reference and actor; buyer pins cannot create this |
| buyer_requests | Link/order/request UUIDs, payload hash, applied/review decision, proposed/previous values, reasons, timestamps and dispatcher resolution |
| buyer_rate_limits | Pseudonymous salted peer/window key, atomic count, cleanup expiration |

UUID, JSON/JSONB, exact coordinate numerics, timezone-aware timestamps and restrictive FKs
remain PostgreSQL-compatible. SQLite batch alteration preserves delivery history. Tests
include a Phase 4 database with existing users/order/event upgraded to the new revision,
metadata drift detection, isolated downgrade/re-upgrade and offline PostgreSQL DDL.
Migration applied successfully to isolated databases and the existing local development
database; local `.env` was not rewritten. No live PostgreSQL server was contacted.

New files: app/db/buyer_models.py, app/schemas/buyer.py, app/core/buyer_access.py,
app/services/buyer_policy.py, app/services/buyer_confirmation.py,
app/api/buyer_confirmation.py, migrations/versions/0002_buyer_confirmation.py,
tests/test_buyer_confirmation.py and scripts/smoke_buyer.py. Updated models/event checks,
configuration, main app/CORS/errors, access-log filter, order lifecycle hooks, migration
environment, smoke_orders revision label, version, README, .env.example and API contract.

## API endpoints

Protected local actor access:

- POST /api/orders/{id}/confirmation-link
- POST /api/orders/{id}/confirmation-link/revoke
- POST /api/orders/{id}/location-reference (Dispatcher/Admin)
- GET /api/orders/{id}/buyer-requests (ownership scoped, paginated)
- PATCH /api/orders/{id}/buyer-requests/{internal_request_id} (Dispatcher/Admin review)

Buyer capability access:

- GET /api/confirm/{token} (minimal card)
- POST /api/confirm/{token}/verify (last-four check, returns separate authorization)
- GET /api/confirm/{token}/details (Bearer required)
- PATCH /api/confirm/{token}/location (Bearer required)
- PATCH /api/confirm/{token}/response (Bearer required)

The existing health, parsing and order APIs remain available under their prior contracts.
All schemas, security/error states, time limits and JavaScript calls are documented in
[API_CONTRACT.md](API_CONTRACT.md). Actual HTTP output with every capability redacted is
in [PHASE5_SAMPLE_RESPONSES.json](PHASE5_SAMPLE_RESPONSES.json).

## Actual verification

- Final full run: **359 tests passed in 29.80 seconds**: all 288 prior cases plus 71 Phase 5 cases.
- Ruff lint: all checks passed; formatting: **61 files already formatted**.
- Local Alembic current: **0002_buyer_confirmation (head)**.
- Editable package updated to **0.5.0**; `pip check` reported no broken requirements.
- Phase 4 HTTP lifecycle rechecked: 2 orders / 10 events persisted through DELIVERED.
  Health/parsing smoke checks passed in both hybrid and rules modes, with valid inputs
  returning 200 and empty input returning 422. OpenAPI includes every buyer route.
- Real Uvicorn HTTP smoke on a new isolated SQLite database passed: raw Burmese order
  parsing/creation, link generation, minimal card, unauthorized location 401, failed
  verification 403, valid verification 200, details, initial-pin review, duplicate retry,
  dispatcher approval, AVAILABLE/instructions, protected retrieval and revoked-link 404.
- After stopping the server and reopening the database: **1 order, 1 hashed link,
  1 hashed authorization, 2 buyer requests and 9 delivery events** persisted. Coordinates
  came from the synthetic buyer input, instructions persisted, source was buyer_confirmation,
  lifecycle was CONFIRMED and confidence remained **AMBER**.
- Six concurrent failed guesses produced exactly three failed-verification responses and
  three locked responses, with stored failure count exactly three. Four concurrent identical
  pin submissions created one request/event. Session rotation, link expiry/revocation,
  phone changes/backtracking and 24-hour delivered viewing were checked.
- Tests exercise initial/near/far/cross-township pins, missing boundaries, anchor hopping,
  invalid coordinates, cutoff boundary, invalid/past/overnight windows, policy-disabled
  requests, protected approval/rejection/scoping, database rollback and privacy/logging.

An initial full run found one test expectation using the alias Kamayut instead of the
existing dictionary's canonical Kamaryut. The test fixture/expectation was corrected;
the parser dictionary was preserved. No failure remains in the reported full suite.

## Security and product decisions

Initial link lifetime is 72 hours (configurable 1..168). An active unlocked link changes
to minimal view-only for exactly 24 hours following DELIVERED. Expired/revoked/locked links
are never revived. Sensitive edits stop at READY_FOR_DISPATCH and stay closed through
assigned/on-road/completed states. CANCELLED revokes links. A phone correction permanently
revokes old links, so restoring the old phone does not restore capabilities.

All writes lock order then link using database UPDATEs, which acquire write locks in both
SQLite and PostgreSQL. Failed counts, generation, order state, idempotency key and event
writes stay in one transaction; a failed check commits only its security counter/event
before returning an error. Rate counters commit separately so failed requests still count.
No raw tokens, submitted digits or plaintext IPs are stored in request audit/event metadata.
Audit coordinate/instruction values are sensitive and available only through protected APIs.

Four digits are low entropy: this is limited knowledge verification combined with possession
of a private link delivered through a trusted existing conversation. It does not prove phone
ownership. Three guesses per link, rotation, revocation, short authorization and rate limits
reduce exposure; production threat review remains necessary. Security approach references
[OWASP token guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
and [session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

Automatic <=500m adjustment requires BOTH an independently checked anchor and independently
resolved matching township. The installed resolver returns unknown. Default initial pins,
larger moves and cross-township moves are therefore review proposals; dispatch coordinates
do not change until explicit approval. Approved pins never become trusted anchors or grant
GREEN. Dispatcher attestation is a human assertion, not a geocoding service. Tests use only
injected synthetic geometry; no map dataset or coordinates were fabricated for application use.

Rescheduling/security delivery are disabled by default. Valid requests are recorded for
review without changing dispatch plans. If enabled, automatic time selection requires two
hours' notice, within seven days, before the 15:00 Yangon cutoff, a 30-minute..8-hour window
on one local date and no unresolved review. Dispatcher approval explicitly overrides courier
review requirements; past windows are still rejected. Optional configured cross-township fee
is indicative only; no quotation engine, automatic fee application or payment exists.

## Limitations and frontend requirements

- Production remains fail-closed. This is a local/test backend foundation, not publicly
  deployable authentication. No public tunnel, proxy or production resource was created.
- Live PostgreSQL execution/concurrency is unverified; offline SQL compiles. Test with a
  disposable PostgreSQL database before selecting a production deployment.
- No trusted township boundary file/service is supplied. Supply reviewed server-side
  resolver data before enabling automatic geofence decisions. Anchors are immutable in
  this MVP; re-anchoring/relocation requires later policy work, not buyer requests.
- Courier policy is globally configured for this local MVP, not per-courier database
  contracts; merchants must supply trustworthy shop/item information later.
- The mobile card is not built. Frontend must display review decisions honestly, use future
  timezone-offset windows, retain request IDs for network retries, keep authorization only
  in memory, use no-referrer/no-store, avoid third-party analytics/token logging and never
  include the development token in the buyer flow. GET details requires verification.
- Fixed-window per-peer limits can burst across a minute boundary and users on one shared
  network share a budget. Forwarding proxies require a reviewed client-IP strategy and
  their own redacted logs. No distributed external rate-limit service is required locally.
- Existing local database files/audits are not encrypted; retention, pruning, backups,
  production edge limits, privacy access and stronger identity verification need design.
  A future frontend must also protect tokens from link previews, browser history and referrers.
- No messaging, production auth, real AI, rider tracking, routes, billing or spatial memory.

## Phase 6 recommendations

Select tenant-aware authenticated dispatcher access before public use; test PostgreSQL
migrations/concurrency; choose trustworthy boundary data and anchor attestation policy;
define per-courier cutoff/fee and rescheduling agreements; build the buyer card against the
contract; then review secure hosting, token delivery, retention and identity threat model.
No product decision blocks local frontend development using this completed foundation.
