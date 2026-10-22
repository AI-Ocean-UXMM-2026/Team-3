# Phase 19 verification — MTT maps/database integration

Completed locally on 2026-10-21. Parent `origin/mtt`:
`0e95c6a9970198a345622a145330749aaabca83f`.
Remote head was checked again at final review and remained at that commit.
Branch: `feature/mtt-maps-database-integration`.
Worktree: `C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI-mtt-integration`.
Changes are local and uncommitted for review. No push, merge, reset, deployment or
teammate branch modification occurred.

## Implemented and preserved

- Preserved MTT's Signboard design, vanilla JS architecture and standalone demo domain.
- Added an isolated live-store view adapter using existing protected APIs and SQLite.
  Root under the local launcher is LIVE_BACKEND; `/prototype.html` is DEMO_SIMULATION;
  missing configuration/backend/write acceptance is an explicit error, never demo success.
- Connected real chat parsing/import, structured creation, saved order retrieval/correction,
  link issue/revocation, private buyer verification/details, location submission/review,
  route assignment/departure, rider queue/status/COD and persisted chronological history.
- Loaded existing vendored Leaflet for customer click/drag, coordinate entry, device GPS
  and read-only dispatcher/rider pins. No location is selected from the browsing centre.
  GPS is click-only; denial/unavailable/timeout retain manual controls.
- Retained immutable trusted-reference/Haversine/500 m server policy. Initial untrusted
  pins require review. Approval does not make coordinates independently verified or GREEN.
- Optional street tiles are opt-in with attribution/failure feedback. No new paid maps,
  geocoder, AI model or route optimization service was activated.
- Navigation uses only the backend's ready URL. Missing/unconfirmed coordinates do not
  produce an `undefined` destination. Approved availability/landmark/floor fields reach riders.
- Retained all business API schemas, ORM models and migrations. The only new Python
  server behavior is explicit runtime configuration on the protected local BFF.

## Actual verification results

Windows, Python 3.14.7, Node 24.20.0, Playwright 1.64.1 Chromium; local SQLite only.
The existing pinned worktree Python environment was reused; current code was imported
from this worktree. No ordinary development or production database was selected.

| Command/check | Result |
| --- | --- |
| Baseline `python -m pytest -q` | 870 passed, 91.10 s |
| Final backend `python -m pytest -q` | **873 passed**, 100.39 s |
| `npm.cmd run test:frontend` | **107 passed** (99 existing + 8 adapter tests) |
| `npm.cmd run test:dashboard` | **17 passed**, including isolated real HTTP subtests |
| `npm.cmd run test:integration` | **1 passed**, HTTP native buyer/dispatcher/rider/COD/closeout |
| `order-parser`: `npm.cmd test` | **141 passed**, nine files |
| `order-parser`: `npm.cmd run typecheck` | Passed |
| Full `npx.cmd playwright test --reporter=line` | **42 passed**, 3.5 min; real Chromium |
| Affected MTT browser rerun after final adapter safeguards | **8 passed**, 38.8 s |
| Backend Ruff lint / format | Passed; 106 Python files formatted |
| `python -m pip check` | No broken requirements |
| `npm.cmd run build` | Passed, 26 validated static assets; JavaScript syntax/dependency paths checked |
| Fresh isolated migrations; repeated upgrade | Passed, head `0004_workflow_routes` |
| `npm.cmd run verify:mtt-restart` | Passed: real HTTP process restart, 1 delivered order, COD 25000 and 11 events preserved |
| PostgreSQL SQLAlchemy DDL compilation | Passed for 12 application tables; no live PostgreSQL connection claimed |
| `git diff --check` / secret filename-pattern review | Passed; no tracked real `.env`, DB or credential files found |

20 new test cases: three Python, eight Node adapter and nine browser (eight MTT plus
one developer-navigation regression). There are no remaining failing checks in the
relevant final suites. Historical results were not used as substitutes for execution.

An exploratory Ruff command at repository root also considered historical Markdown
Python examples and flagged one formatting-only example in `docs/logistics_lab/README.md`.
It was left untouched; the actual backend/CI Ruff scope passes.

## Browser/API evidence

The MTT browser journey created a fictional order with no coordinates, reloaded it,
generated a native buyer capability, verified synthetic digits, clicked and dragged a
real Leaflet marker, submitted the request, and proved the canonical order still had
null coordinates before review. It explicitly approved location and any separate
availability request, received/assigned the parcel, dispatched, loaded the rider queue,
checked navigation and availability, required COD acknowledgement and delivered.
The refreshed order remained DELIVERED and history contained persisted events.

Other MTT browser cases prove raw Burmese digits/actual message preservation; GPS
permission and manual recovery; unavailable GPS/timeout/missing map library; input
coordinate limits; real three-failure lockout and pre-verification privacy; separate
reschedule review/rejection; runtime failure; and rejected live writes without fake storage.

Existing browser cases cover expired/revoked links and expired authorization, mocked
tile loading, unauthorized reads/CSRF, failed deliveries/returns, actual cash closeout,
safe error rendering, and five responsive sizes. These existing cases exercise the
preserved `/api.html` developer UI, not a claim that every old screen is Signboard.
The MTT customer was also checked at 390 × 844 with no horizontal overflow.

Three local screenshots were captured and visually inspected for the buyer map:
`screenshots/buyer-mobile-map.png`, `screenshots/dispatcher-approved.png`,
`screenshots/rider-approved-pin.png`. They use synthetic locations/people and are ignored
generated artifacts. New browser cases stub optional Google Fonts; street-tile delivery
and paid Google/AI services were not externally verified.

The separate `test_mtt_cod_delivery_pin_and_audit_persist_after_application_restart`
closes and reopens FastAPI/TestClient and SQLite, verifying approved coordinates,
DELIVERED, exact collected COD 25000, AMBER and identical event count. Browser refresh
and real HTTP subprocess startup/shutdown were also executed. In addition,
`scripts/verify_mtt_restart.cjs` executed a complete native API delivery, gracefully
stopped the actual Uvicorn process, started a new process on the same owned temporary
SQLite database, and verified DELIVERED, the approved pin, COD 25000, 11 identical
events and rejected direct private reads. It cleaned only its verified temporary directory.
No production restart or live PostgreSQL persistence is claimed.

## Confirmed issues corrected

| Finding | Small correction / evidence |
| --- | --- |
| Root product writes only browser state | Separate live adapter, protected existing API calls, real persistence browser test |
| Root did not load actual map helper | Load vendored Leaflet/helper; click/drag/GPS tests; unselected initial view |
| Same-day creation blocked by demo preparation minimum | Keep unsupported prep controls out of live mode; backend day rules remain authoritative |
| Inline board style rejected by strict BFF CSP | Use dataset plus DOM style property; do not relax script/style CSP |
| New rider form rendered while developer action lock remained held | Defer navigation load until lock release; reproduce responsive failure and add navigation regression |
| Old test treated root as a simulation | Test the actual explicit `/prototype.html` entry and assert no backend writes |
| Location review could accidentally include separate preference proposals in draft adapter | Filter location reviews and present separate review controls; browser asserts reschedule remains unresolved |
| Rider selector could replace the first rider's profile with another selected identity | Preserve profile choices, use server-connected rider identity; adapter regression assertions |
| Live field/provenance/nav names differ from browser domain | Explicit projection from server schemas; unknown values remain unknown |
| Reloaded link secret could be misrepresented as nonexistent | Explain one-time plaintext retrieval; show not-loaded state, never reconstruct from hashes |
| Private buyer endpoint lacks collected-COD totals | Do not render a fabricated zero payment amount in live delivered view |
| Cross-day review can update time without a parcel/route day contract | Live adapter retains request and blocks cross-day approval pending operational replanning; browser regression |

Early failures caused by incomplete draft wiring, an incorrect Playwright context fixture
and the stale root-page expectation were investigated and corrected. Tests were not
removed and security was not weakened to make them pass.

## Security and remaining limitations

- **Public release blocker:** production login, ownership/role authorization and secure
  deployment are absent. The loopback BFF is developer-only, including role switching.
- Credentials stay server-side; buyer capabilities still need careful handling in shared
  URLs/browser history. No bearer/dev token is placed in frontend source, storage or headers.
- SQLite is verified. PostgreSQL connection, live migrations, SSL/pool behavior and
  deployment remain unverified because no approved server/credentials exist.
- AI is mock; optional adapters are prepared, not activated or accuracy-evaluated here.
- Trusted township boundaries/geocoding are absent. Approved pins do not prove township
  identity; automatic GREEN remains restricted. Navigation is not route optimization.
- Cross-day parcel/route replanning, live shop-preparation policy, parcel metadata/day
  editing, offline replay and same-day retry planning need explicit server contracts.
  Existing demo features remain available only as simulation; unsupported writes fail.
- Local imports are individual transactions; uncertain/partial outcomes require refreshing
  before retry. No bulk-create idempotency or production offline sync was invented.
- Buyer location/preferences use two transactions; partial acceptance is reported. Native
  request IDs/version checks remain in use. No guaranteed exactly-once network delivery.

## Files and next phase

New implementation: `frontend/js/live-store.mjs`, `live-bootstrap.js`, `frontend/css/live.css`,
`runtime-config.js`, `demo-config.js`. Updated Signboard wiring, map helper, demo service
worker/entry, local runtime route and developer-page lock handling; no business service or
database model/migration edits. Tests: `test_mtt_runtime.py`, `live-store.test.mjs`,
`mtt-live.spec.cjs`, existing browser fixture/website regression and demo DOM fixture.
Root test command, README, `.gitignore`, `.env.example` and API handoff were updated.
The restart-verification script provides a repeatable real-HTTP persistence check.

Reports: baseline audit, service/key inventory, database architecture, workflows/startup,
generated 35-operation OpenAPI and machine audit evidence in this directory.

Next: review this local branch; decide cross-day replanning/preparation contracts;
implement production authentication/authorization before shared/public use; verify an
isolated PostgreSQL instance; then evaluate an explicitly approved AI provider and trusted
geospatial data. No external account, key, paid resource, push or merge was required here.
