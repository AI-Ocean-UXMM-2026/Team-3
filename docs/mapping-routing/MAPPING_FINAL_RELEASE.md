# Mapping release candidate — Phase 30

Date: 2026-10-22. Branch: `feature/mtt-maps-database-integration`.
Worktree: `C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI-mtt-integration`.
Starting HEAD: `650e040`; MTT remains the upstream reference. Existing Phase 26–28
uncommitted work was inventoried and preserved. No branch switch, merge, push,
deployment, Supabase integration or database schema/provider change occurred.

## Release scope and classifications

| Capability | Classification | Evidence and boundary |
|---|---|---|
| Interactive customer map, click and mouse/touch dragging | COMPLETE_AND_VERIFIED | Vendored Leaflet 1.9.4; real Chromium at five sizes |
| Click-only device GPS and denial/unavailable/timeout handling | COMPLETE_AND_VERIFIED | Browser permission/sensor emulation, no physical GPS accuracy measurement |
| Coordinate submission, review and persistence | COMPLETE_AND_VERIFIED | Actual local HTTP/SQLite and browser workflows; no invented pins |
| Server-side authorization, 500 m and immutable trusted reference policy | COMPLETE_AND_VERIFIED | Existing buyer/geofence/security regressions passed; initial untrusted pins require review |
| Single-stop Google road estimate integration | COMPLETE_AND_VERIFIED | One historical Phase 27 live response; Phase 30 integration uses mocks, live budget stays zero |
| Google embedded route renderer | BLOCKED_BY_PROVIDER | Renderer and markers tested with stub Google SDK; no separately authorized/restricted browser credential supplied |
| Key-free external navigation | COMPLETE_AND_VERIFIED | URLs use approved coordinates only; browser navigation intercepted in tests, no external Google request |
| Real Google matrix under Demo Key | BLOCKED_BY_PROVIDER | Not included in the published Demo Key feature list; not attempted |
| Alternative road-matrix boundary | COMPLETE_AND_VERIFIED | Existing ORS adapter normalized with mock HTTP and fed into OR-Tools; no real road data fetched |
| Operational real-road matrix optimization | BLOCKED_BY_PROVIDER | No configured/authorized road-matrix service or reviewed live entitlement |
| OR-Tools multi-rider planning | COMPLETE_BUT_SIMULATED | Working solver, capacities, windows, services, priorities, assignments and return-to-hub using explicit fixture matrices |
| Dispatcher preview, commit, stop order, unassigned reasons | COMPLETE_BUT_SIMULATED | Actual persisted plans/assignments; underlying route costs/geometry are simulated |
| Rider queue, approved pins, notes, delivery/COD and history | COMPLETE_AND_VERIFIED | Actual browser/API delivery workflow, own-assignment scope and restart persistence |
| Versioned safe replanning | COMPLETE_AND_VERIFIED | Stale previews rejected, explicit commit, assignment preservation and terminal-stop exclusion |
| Manual REST refresh and disconnect recovery | COMPLETE_AND_VERIFIED | Visible Refresh approved stops action; no instantaneous/push claims |
| Automatic background queue polling / WebSockets | NOT_IMPLEMENTED | Explicit manual refresh meets current local workflow; no background tracking introduced |
| Live traffic ETA, independently verified doorstep accuracy | NOT_IMPLEMENTED | Static provider durations and buyer-approved points do not establish either |
| Arbitrary stop precedence / guaranteed global optimum | NOT_IMPLEMENTED | Priority is weighted selection, not guaranteed visit order; solver is bounded heuristic |

## Concrete improvements made

1. Added per-order optimization `priority` (integer 0–5, default 0). Higher values
   increase the cost of leaving a parcel unassigned. Capacity, service-time,
   time-window and assignment constraints remain hard. Default behavior is preserved.
2. Added compatible saved-plan fields: vehicle `capacity`/`load`, stop `priority`
   and `delivery_window`. Dispatcher and rider cards show capacity use and resolved
   windows. Historical plans remain readable and missing capacity is not invented.
3. Google map renderer now marks road-route start/end and approved stops, and fits
   all approved points in view even when they differ from road-snapped geometry. Google
   geometry remains prohibited on Leaflet; no private Routes key enters browser code.
4. Added an explicit Google Maps navigation link to single-stop estimates, using
   origin/destination coordinates only. It works without a browser API key and is
   offered independently of the blocked embedded map viewer.
5. Fixed an actual read-only-map bug: empty coordinate attributes could coerce to
   a false `(0,0)` pin. Empty attributes are now rejected before conversion.
6. Fixed stale GPS feedback confirmed visually: a permission-denied error remained
   after a subsequent successful sensor reading. Success now clears that old error.
7. Moved the existing live rider refresh action out of collapsed Demo tools and
   labelled it **Refresh approved stops**, keeping the established styling/handler.
   The new disconnect regression exposed insertion after action wiring; live rider
   actions are now bound after dynamic controls are inserted, without duplicate listeners.
8. Added reusable release browser tests, priority/boundary/API tests, and a real HTTP
   optimized-plan restart verification tool. Refreshed both OpenAPI snapshots.

No application redesign, database migration, new provider SDK, paid API activation,
AI-provider change, continuous geolocation watcher or automatic assignment change occurred.

## Technology, estimates and provider terms

The current stack remains vanilla JavaScript, Leaflet, optional existing Google Maps
renderer, FastAPI/Pydantic, SQLAlchemy/SQLite, Alembic history and Google OR-Tools.
Haversine is used for independent geographic policy distances, not road driving costs.
The offline provider uses its explicit invented fixture graph; it is not a multiplied
straight-line estimate marketed as a real Yangon road matrix.

[Google Demo Key documentation](https://developers.google.com/maps/demo-key), reviewed
for this release, lists Compute Routes and Maps JavaScript rendering, but not Compute
Route Matrix. The Demo Key is for prototyping and has provider-controlled quotas;
no numeric daily allowance or paid-project entitlement is inferred here.

[Google Routes policy](https://developers.google.com/maps/documentation/routes/policies)
requires Google route content displayed on a map to use a Google map and appropriate
attribution. The existing Google-map path is retained, including its attribution;
Leaflet is used only for independent pins and non-Google route content. The private
backend key is never reused as a browser key. No authorized renderer credential or
new Maps JavaScript load was configured. A real embedded Google map remains blocked,
although its rendering contract and markers are tested with a stub SDK.

No Google route cache was introduced. Estimates live only in page/process memory;
refresh/input changes clear them. No unsupported caching exception is assumed.
Any public release also needs appropriate provider terms/privacy notices and proper
production authentication; this loopback tool must not be published as an admin site.

[ORS matrix technical documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/)
confirms location tuples, seconds for durations and selectable distance units. The
existing adapter requests meters and normalizes its output to the same RoadMatrix
interface used by OR-Tools. This release verifies that boundary using an asymmetric
mock response. No ORS account/key was created or used. The hosted plans/restrictions
URLs returned 404 during review, so current free-plan entitlements/quotas were not
independently verified or hardcoded. An owner-reviewed key/plan and a separately
authorized bounded live evaluation are required before claiming real-road optimization.
No synthetic Google matrix is assembled from single-route responses.

## Real Google status and safety

Historical Phase 27 result: one authorized Compute Routes request, HTTP 200,
1.741 km, 405 seconds (6.75 minutes), valid encoded geometry decoded into 31 points.
This is evidence of that request only, not live traffic, all-Yangon coverage,
current quota, matrix access or renderer authorization.

**This phase made zero external routing/AI/Maps SDK/tile calls in acceptance tests.**
Provider tests use MockTransport. Browser fixtures force offline routing, disable
both live flags, set the Google budget to zero and suppress a real browser map key.
External navigation and optional tile cases are intercepted by Chromium test routes.
Official documentation pages were read separately; no provider data endpoint was probed.

Normal defaults remain:

```dotenv
LANNPYA_ROUTING_PROVIDER=offline
LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED=false
LANNPYA_GOOGLE_DEMO_ENABLED=false
LANNPYA_GOOGLE_DEMO_MAX_REQUESTS=0
```

The dedicated single-order Google action still needs explicit role-bound consent,
canonical reviewed coordinates, a unique request ID, and a server-approved durable
budget. Reservations occur before HTTP, cover all actors/workers, survive restart
and database reset, and consume budget even on provider failure. No automatic retry
or simulated-success fallback exists. The historical one-call ledger was not reset.

## Dispatcher, rider and update contract

The dispatcher selects eligible orders, riders/capacities, a deliberate origin and
operating period, service time and priority. Preview does not assign anything. The
operator sees stop sequence, selected windows, arrival/departure, capacity use and
unassigned explanations, explicitly acknowledges simulated costs/unverified pins,
then commits. Route departure remains a separate action.

Active assignments remain fixed. Unavailable-rider transfer requires the existing
permitted unassignment flow; departed deliveries cannot be silently transferred.
Order/rider/queue version changes mark previews stale. Buyer reschedule, approved
pin changes, rider availability, cancellation and delivery completion/failure are
covered by existing and new regressions. A fresh preview and explicit commit are
required; completed-stop history is preserved and excluded from new dispatch work.

Riders see their own approved coordinates, landmark/instruction notes, stop sequence
and labelled estimates. **Refresh approved stops** performs a REST read and renders
the latest approved state. There is no automatic refresh deadline: updates appear
on explicit refresh or navigation/reload, not instant push. A failed refresh reports
an error; reconnecting does not replay delivery writes or create new orders. A stale
plan warns the rider to use the current queue/approved pin instead of old estimates.

## Verification evidence

| Check | Actual result |
|---|---|
| Baseline full backend | 997 passed, 121.10 seconds |
| Final full backend | **1,003 passed**, zero failed, 135.80 seconds |
| New backend release cases | 6; priority/capacity, normalized mock ORS boundary, cancellation/replan, metadata and historical compatibility |
| Frontend Node | **117 passed** (5 new priority-request cases) |
| Dashboard Node | **17 passed** |
| Existing local HTTP integration | **1 passed** |
| TypeScript | **141 passed**, type-check passed |
| Initial full Chromium pass | 58 passed; visual QA then identified stale GPS feedback |
| Final full Chromium | **59 passed**, zero failed, approximately 5.0 minutes, after all fixes |
| Build | 27 validated assets; JavaScript syntax checks passed |
| Ruff / formatting | Passed; 106 Python files formatted |
| Python/Node dependencies | `pip check` and both direct npm dependency trees passed |
| Optimized-plan real HTTP restart | PASS; 1 delivered order, 1 committed plan, 1 saved stop/priority, 12 events, COD 25,000, confidence AMBER |

The restart tool starts/stops two actual loopback backend processes against one owned
temporary SQLite directory and checks persisted plan/order/events after reopening.
It rejects direct private reads and cleans up only its verified test directory.
An initial tool variable-name collision was fixed before its successful run; no normal
project database was touched.

The five viewport journeys cover 1440×900, 1366×768, 768×1024, 390×844 and 360×740.
They use real Chromium GPS emulation, permission denial, map clicks/taps, mouse/touch
marker dragging, server review, saved coordinates, simulated preview, commit, scoped
rider route/navigation, COD completion and stale-plan/replan feedback. Overflow checks
passed; 15 current release screenshots are generated under ignored
`.tmp/mapping-release/screenshots/`. Desktop/mobile images were also visually inspected.
These tests do not measure physical GPS accuracy, live tile reliability, Google live
rendering, real road travel savings or production scalability.

Three upstream OR-Tools SWIG deprecation warnings and Node NO_COLOR/FORCE_COLOR
environment warnings remain visible. No test failure was hidden or removed.
An intermediate full browser run had 58 passes and the refresh-wiring regression;
that defect was fixed and its targeted test passed before the final full run.

## Run and reproduce (Windows PowerShell)

From the worktree root, the existing local launcher remains:

```powershell
npm.cmd start -- --port 8780 --state mapping-review
# Open http://127.0.0.1:8780 — loopback only, isolated named local workspace.
```

Choose another port if occupied; do not stop unrelated services. The launcher retains
the existing schema and does not change the ordinary development database. It uses
mock AI and the default simulated routing provider. External services remain disabled.

```powershell
npm.cmd run test:mapping
npm.cmd run verify:mapping-restart
npx.cmd playwright test
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_mapping_release.py -q
# For all Python tests, run from backend/: .\.venv\Scripts\python.exe -m pytest -q
```

For review in this session, a separate temporary-data instance was started and checked
at **http://127.0.0.1:8790** (HTTP 200). It is loopback-only, uses an owned temporary
SQLite database, mock AI and simulated routing, and cleans its test database on stop.
It does not replace or modify the ordinary development instance/database. Use only
fictional information in this developer review instance.

No secret entry is required for this simulation-backed acceptance/demo sequence.
Additional Google/ORS live calls and a browser renderer require separate explicit
authorization/configuration; there is no request for that approval in this release.

## Explicit acceptance answers

1. Doorstep pinning: **yes**, UI/GPS permission/manual selection/drag/submission tested;
   sensor coordinates are not a guarantee of physical doorstep accuracy.
2. Location validation: **yes within the tested local access/review model**; server
   authorization, coordinate bounds, trusted-reference/500 m and expiry rules hold.
3. Google estimates: **supported and historically verified once**; current live budget
   is zero. The integrated current workflow is verified with recorded/synthetic mocks.
4. Compliant route map: Google renderer boundary exists and is stub-tested; **real
   embedded Google display remains blocked**. Key-free navigation is available.
5. OR-Tools: **complete for this bounded single-hub MVP**, including multi-rider hard
   constraints and weighted priority; no global-optimum guarantee.
6. Real road matrix: **not operationally available/authorized**; adapter boundary exists.
7. Simulation labels: **yes**, API/UI retain SIMULATED versus ROAD_STATIC/Google labels.
8. Dispatcher-to-rider delivery workflow: **yes**, actual browser/API/SQLite/COD/history.
9. Replanning: **yes**, explicit versioned previews/commits preserve assignments/history.
10. Desktop/mobile: **yes**, all five requested viewport sizes, including touch dragging.
11. Demo Key blockers: matrix not listed; browser credential/authorization and broader
    road coverage/quotas remain unverified. No billing workaround was attempted.
12. Hackathon readiness: **ready as a clearly labelled local simulated-routing MVP**;
    not a public production deployment or an authorized live-road optimization demo.

## Release preparation

Changes remain local for review; no commit/push/merge was performed. The release manifest
`MAPPING_RELEASE_MANIFEST.json` lists source/document checksums and excludes private environments, databases, caches,
generated browser reports and credentials. Existing unrelated work is preserved.
Generated changes to pre-existing screenshot assets are restored only where the initial
inventory confirmed those files were clean; release screenshots remain in `.tmp`.
Tracked-artifact review found no private environments, virtual environments, node_modules,
database files or logs. Changed-source credential-pattern scanning found zero matches;
this is a bounded source/artifact review, not proof that all possible secret formats
can be recognized. The private environment remains ignored and was not read or modified.
Suggested local commit title: `Finish local mapping MVP and release acceptance suite`.
