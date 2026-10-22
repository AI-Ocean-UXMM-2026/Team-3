# Phase 22 verification

Verified locally on the MTT-based `feature/mtt-maps-database-integration` worktree;
base commit `0e95c6a9970198a345622a145330749aaabca83f`. Historical test figures were
not treated as proof. Before implementation, the actual baseline was 873 Python
tests and 107 frontend Node tests passing; the frontend build passed.

## Final checks

| Check | Observed result |
|---|---|
| Full backend `pytest -q` | **910 passed, 0 failed**, 118.53 seconds |
| New routing backend cases | **37** including parametrized cases |
| `npm.cmd run test:frontend` | **112 passed, 0 failed**; five new planner cases |
| `npm.cmd run test:dashboard` | **17 passed, 0 failed** |
| `npm.cmd run test:integration` | **1 real HTTP workflow passed** |
| `npm.cmd --prefix order-parser test` | **141 passed, 0 failed** |
| Full Playwright Chromium suite | **45 passed, 0 failed**, about four minutes; three new routing scenarios |
| Final affected Chromium rerun | **5 passed, 0 failed** after GPS freshness/accuracy and assignment-marker fixes |
| Ruff lint / formatting | Passed; 119 Python files formatted |
| TypeScript type-check | Passed |
| Frontend production build | Passed; 27 validated assets |
| Python dependency check | Passed; no broken requirements |
| JavaScript syntax checks | Passed for changed map/planner/app and restart utility |
| Git whitespace check | Passed; Git emitted normal CRLF-to-LF notices |

The full Chromium pass preceded the final small GPS/assignment-marker refinements;
the five directly affected Chromium scenarios were then rerun successfully. The
final full Python pass includes the assignment-lifetime regression. No failing
tests remain. OR-Tools emits three upstream SWIG `DeprecationWarning` messages on
Windows/Python 3.14 (`SwigPyPacked`, `SwigPyObject`, `swigvarlink`); these remain
visible. Node's NO_COLOR/FORCE_COLOR warning is an environment warning.

An initial full run had two OpenAPI snapshot failures (907 passed, 2 failed).
Snapshots were regenerated from the actual application, the published operation
count updated from 35 to 43 for eight additive endpoints, and the handoff updated.
The 21 targeted contract tests and subsequent full suites passed. Earlier targeted
development failures also exposed the Windows OR-Tools Span binding issue and
incorrect test assumptions about UTC window serialization, route lookup and buyer
request IDs. Tests were corrected against implemented contracts; access/lifecycle
rules were not bypassed.

## Functional evidence

- Real Chromium: existing MTT order creation, buyer verification, map click/drag,
  dispatcher location/availability review, denied/unavailable/timed-out GPS,
  rescheduling, route preview, geometry, explicit assignment commit, rider queue,
  navigation link, COD completion, history and remaining-stop replanning.
- Preview leaves order assignments unchanged. Commit persists assignments and
  stop sequence. Page reload retains saved plans; correction marks previews stale
  and removes the commit control. Missing pins and routing failures remain errors.
- New backend tests cover Google/ORS normalization and failure responses using
  **MockTransport only**, explicit simulation gates, malformed coordinates,
  unavailable providers, multiple riders/different capacities, hard time windows,
  unreachable costs, overload, expired previews, rider unavailability, explicit
  reassignment, stale snapshots, competing concurrent commits, idempotency,
  transaction rollback and rider coordinate scoping.
- Native MTT clock windows are anchored to the parcel date. A separately verified
  buyer reschedule requires dispatcher approval, updates the canonical parcel
  date/window, invalidates the old preview and constrains the next solver result.
- A past plan cannot change the queue priority of a new legacy assignment.
- Existing regression tests cover the trusted-reference 500-metre policy, buyer
  lockout/expiry and unauthorized location access. No real GPS hardware accuracy
  or external map/routing reliability was measured.

Screenshots inspected: [desktop preview](screenshots/dispatcher-preview-desktop.png)
and [mobile planner](screenshots/dispatcher-planning-mobile.png). Existing browser
responsive coverage passed at desktop, laptop, tablet and both mobile sizes.
Street tiles remain opt-in; synthetic route lines work without external tiles.

## Persistence and migrations

Fresh isolated Alembic upgrades reached `0005_routing_plans`; ORM/migration metadata
comparison passed, foreign keys remained enabled and idempotent upgrades retained
existing users. Empty disposable database downgrade/re-upgrade and PostgreSQL
**offline SQL compilation** passed. A live PostgreSQL server was not contacted.

`node scripts/verify_routing_restart.cjs` passed against a separate temporary
SQLite database and two actual loopback server processes: one order, one committed
route plan, synthetic geometry, DELIVERED state, 25,000 MMK recorded COD and **12
events** survived restart. Confidence remained AMBER; direct private reads were
rejected. The script validates directory ownership before cleaning up its own
temporary data. It never reads the regular project database.

The benchmark separately reopened its database and found all **12 previews**.
An isolated second-assignment fault and two concurrent commits verified rollback
and duplicate prevention on SQLite. PostgreSQL concurrency is still unverified.

## Bounded benchmark

Actual results from [BENCHMARK.json](BENCHMARK.json): Python 3.14.7, Windows 11,
Intel64 Family 6 Model 165, SQLite, in-process FastAPI TestClient, OR-Tools
9.15.6755, three riders with capacity 20 each, one-second solver budget,
three samples per size. Every sample assigned all selected stops and passed
capacity/operating-period assertions.

| Stops | Matrix cells | Matrix median ms | Solver median ms | API median ms | API p95 ms |
|---:|---:|---:|---:|---:|---:|
| 5 | 36 | 1.214 | 1001.774 | 1034.971 | 1068.229 |
| 10 | 121 | 4.014 | 1000.956 | 1046.507 | 1046.905 |
| 20 | 441 | 15.288 | 1001.698 | 1080.828 | 1081.240 |
| 50 | 2601 | 106.819 | 1002.700 | 1234.225 | 1281.372 |

p95 is nearest-rank of only three observations, hence the maximum; this is a
bounded smoke benchmark, not a robust production percentile. Solver runtime
largely reflects the deliberate search budget. Matrices and travel times are
**SIMULATED / TEST DATA**, not measured Yangon road or traffic improvements.
The normal configuration remains capped at 25 stops; this isolated benchmark
explicitly raised the limit to 50. No load was sent to external providers.

## Files and boundaries

New implementation: `backend/app/routing/`, `schemas/routing.py`, `api/routing.py`,
`db/routing_models.py`, `services/route_planning.py`, `data/routing_fixture.json`,
migration `0005_routing_plans.py`, `tests/test_routing.py`,
`tools/routing_benchmark.py`, `frontend/js/routing-ui.mjs`,
`frontend/tests/routing-ui.test.mjs`, `tests/browser/routing.spec.cjs`,
`scripts/verify_routing_restart.cjs`, and this documentation directory.

Small integration changes: configuration, main router/error registration,
migration imports, optional atomic `prepare_assignment` commit flag, optimized
queue ordering scoped to assignment ID, BFF route allowlist, existing MTT live
adapter/map/bootstrap/styles/app, local request timeout for bounded solver work,
dependency declarations, package test command, contract snapshots/tests and
existing reschedule browser coverage. The UI design and AI boundary were preserved.
Existing Phase 19 uncommitted work was not overwritten or misattributed.

The final safety review found no tracked `.env`, database, virtual environment or
private-key artifacts and no Google/GitHub/private-key-pattern matches in changed
source/documents. Test databases, environments and backups remain ignored. No
push, merge, external resource, paid request, production-data change or deployment
occurred. Line-ending notices are not merge conflicts.

## Local review workspace

A separate loopback-only server was left running at
**http://127.0.0.1:8782/#/routes**, with state name `phase22-review`. It contains
five explicitly FICTIONAL synthetic orders and a five-stop SIMULATED **PREVIEW**;
no assignments were committed for this review workspace. Its manually supplied
fixture pins remain unverified and are not real customer homes. Open the saved
plan to inspect it; previews expire after 15 minutes and can be recalculated.

To reopen that workspace after stopping the server:

```powershell
npm.cmd start -- --port 8782 --state phase22-review
```

Only the new isolated workspace was initialized. The server's provider is offline
and its external-request gate is false. Normal project databases remain untouched.

## Acceptance status

GPS selection, persistence/review, multi-rider capacity/time-window optimization,
dispatcher preview/commit, rider stop sequences and explicit safe replanning are
implemented and locally verified. Google/ORS road adapters are prepared and mock
contract-tested; **real road routing is not active**. Live credentials, approval
for metered calls, provider/regional validation and safe production authorization
are required for a live/public demonstration. Real AI also remains disabled.
