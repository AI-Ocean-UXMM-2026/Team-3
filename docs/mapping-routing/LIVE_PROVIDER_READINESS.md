# Phase 23: live-provider readiness

## Preserved baseline

Work stayed in `C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI-mtt-integration`
on `feature/mtt-maps-database-integration`, based on MTT commit
`0e95c6a9970198a345622a145330749aaabca83f`. The initial index was clean, but 75
modified/untracked files contained both earlier MTT integration and Phase 22 work.
The required earlier integration was not an unrelated experiment: Phase 22's UI
depends on it. It was preserved separately before committing Phase 22:

- `74cd058`: verified MTT local integration prerequisite, 30 files.
- `fb8ceec`: Phase 22 GPS/routing MVP, 56 files, separate from the prerequisite.

[PHASE23_CHANGE_INVENTORY.json](PHASE23_CHANGE_INVENTORY.json) records every initial
path and checksum, prerequisite paths and full commit IDs. Test-generated
screenshots changed during verification; source bytes were preserved. No unrelated
modifications were identified or folded into the commits. Ignored environments,
SQLite databases, caches, private access files, logs and backups were excluded.
Credential-pattern and tracked-artifact checks found no exposure. These checks
are not a claim that arbitrary unknown credentials can always be detected.

The commits are local only. No remote branch was changed, merged, force-pushed or
deleted. The Phase 22 tree was clean after its preservation commit. Phase 23 adds
only an isolated evaluator, tests, documentation/example configuration and small
adapter safeguards; it changes no frontend feature, optimizer, endpoint schema
or migration.

## Provider review

| Area | Google Routes | openrouteservice |
|---|---|---|
| Readiness | REST adapter prepared; not live verified | Hosted v2 adapter prepared; not live verified |
| Route geometry | Requests GeoJSON LineString; validates coordinates | Requests GeoJSON directions; validates coordinates |
| Coordinate convention | Named latitude/longitude in `latLng` | `[longitude, latitude]` arrays |
| Distance / duration | Integer metres; protobuf seconds rounded up | Explicit metre units; duration seconds rounded up |
| Matrix | Index-based placement, shuffled streams supported, chunked 20x20 | All locations, origin rows/destination columns, null unreachable cells |
| Modes | DRIVE; separately enabled TWO_WHEELER | driving-car only |
| Traffic | TRAFFIC_UNAWARE, no live-traffic claim | Static estimate, no live-traffic claim |
| Errors | Safe credential/quota/rate/timeout/invalid-response errors | Same, plus typed missing-point/no-route errors |

Google masks remain explicit:

```text
routes.distanceMeters,routes.duration,routes.polyline.geoJsonLinestring,fallbackInfo
originIndex,destinationIndex,status,condition,distanceMeters,duration,fallbackInfo
```

No wildcard, alternate routes, toll calculation, traffic-aware features or provider
waypoint optimization are requested. Overview geometry and no alternative routes
are explicit. Unexpected encoded geometry is rejected rather than interpreted as
coordinates. Matrix indices, paired null cells and missing-cost validation remain.

The [current Compute Routes reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes)
supports the requested GeoJSON encoding. The [Compute Route Matrix reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix)
requires masks and emphasizes including status. Current two-wheeler country
coverage includes Myanmar, but actual Yangon street/vehicle suitability remains
unverified. TWO_WHEELER also has different pricing implications; see the cost controls.

The [current ORS directions documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/)
and [matrix documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/)
were reviewed. Directions now explicitly request metres and omit instructions.
The adapter consumes GeoJSON, not the separate encoded-polyline representation.
Using the [published error codes](https://giscience.github.io/openrouteservice/api-reference/error-codes),
bounded ORS errors 2009 normalize to `ROUTE_NOT_FOUND`; 2010/6010 normalize to
`ROUTING_POINT_NOT_FOUND`. Provider messages and keys are never returned.

Outbound transport now explicitly uses zero retries, no redirects and no
environment proxy inheritance. Existing configurable deadlines and a 2 MB response
cap apply to success/error bodies. Account/quota/rate/malformed/timeout errors
stop an evaluation; known no-route cases are recorded without simulated success.

## Credentials and deliberate activation

| Credential/config | Required use | Storage |
|---|---|---|
| `LANNPYA_GOOGLE_ROUTES_API_KEY` | Approved Google project with Routes API access, billing/quota configuration | Server process secret only |
| `LANNPYA_ORS_API_KEY` | Approved ORS account/plan and applicable hosted quotas | Server process secret only |
| `LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED` | Independent native outbound opt-in | False by default |
| `LANNPYA_ROUTING_TWO_WHEELER_ENABLED` | Google TWO_WHEELER opt-in | False by default |
| `LANNPYA_ROUTING_EVAL_LIVE_ENABLED` | Independent evaluation opt-in | False by default |
| `LANNPYA_GOOGLE_MAPS_BROWSER_KEY` | Optional Google-map display, separate from server routing | Public browser key, referrer/API restricted |

No browser map key is required to evaluate routes or use external Google Maps
navigation links. Server routing keys must never be reused as browser keys or
placed in frontend environment files. The CLI ignores `.env`; approved secrets
belong in its process environment/secret manager. No real provider credentials were requested,
retrieved, printed, generated or configured in this phase. No cloud account or
billing was activated.

Live evaluation additionally requires a reviewed private pricing configuration,
explicit request/element/stop/cost caps, a new evaluation ledger and the deliberate
CLI live flag. All supplied examples remain disabled/unpriced. The application
can remain offline throughout a later separately authorized evaluation. See
[evaluation plan](YANGON_ROUTE_EVALUATION_PLAN.md) and
[cost controls](ROUTING_COST_CONTROLS.md).

## Actual verification

| Check | Result this phase |
|---|---|
| Phase 22 baseline Python rerun | 910 passed, 0 failed, 129.65 seconds |
| Final complete Python suite | **948 passed, 0 failed**, 119.86 seconds |
| New evaluation cases | **38**, including parameterized cases |
| Routing + initial evaluation target run | 67 passed; later cases included in full suite |
| Frontend Node regression | **112 passed**, no frontend source changes |
| Dashboard tests | **17 passed** |
| Actual loopback HTTP integration | **1 passed** |
| TypeScript tests / type-check | **141 passed**, type-check passed |
| Chromium | **5 relevant scenarios passed**; the three routing scenarios also passed a final rerun |
| Production frontend build | Passed, 27 validated assets |
| Ruff lint / formatting / dependency check | Passed |
| Google DRIVE, Google both modes, ORS dry runs | PLAN_ONLY; **0 external attempts each** |

The historical full 45-browser figure is not presented as a new full-browser run.
This phase ran five relevant real Chromium scenarios (routing preview/commit/COD/
replan, stale preview, unavailable routing, GPS failures and GPS permission/selection).
Synthetic browser GPS is not a measurement of physical device accuracy.

New tests use **MockTransport only** for provider traffic, explicitly label mocked
observations, verify exact decimal/unit accounting, caps before every HTTP attempt,
whole-evaluation timeout, missing/stale pricing, key/production gates, failed
requests, no retries, ledger write failure/reuse/concurrent exclusion, missing
roads, shuffled matrices, chunk boundaries and sanitized CLI errors. Simulated
baseline data never replaces a failed provider result. Three existing upstream
OR-Tools SWIG deprecation warnings remain visible on Windows/Python 3.14.

Run Python tool/test commands from `backend`, matching the existing repository/CI
convention. An ad hoc repository-root invocation could not resolve the backend
`tools` namespace; the corrected backend invocation passed all 38 evaluation
cases. It required no application change. Git's CRLF-to-LF notices are line-ending
normalization notices, not merge conflicts.

Baseline regression tests use their existing isolated temporary databases. No
regular database, production record, migration file or configured data source was
changed by Phase 23. The evaluator itself uses no database. No real provider
request, real road measurement, live latency test or provider-key verification
was performed. Production authentication and public deployment remain unresolved.

## Files prepared

- `backend/tools/routing_evaluation/`: evaluator, fictional points, three disabled
  examples and generated configuration schema.
- `backend/tests/test_routing_evaluation.py`: 38 new cases.
- `backend/app/routing/http.py`: explicit retry/response-size controls, minimal
  request options and typed ORS nonroutable-point errors.
- `backend/.env.example`: zero-call evaluation configuration.
- This report, evaluation plan, cost controls, initial change inventory and three
  actual dry-run JSON reports under `docs/mapping-routing/`.

Next decision: obtain separately approved account credentials and reviewed pricing,
then authorize one small live DRIVE evaluation. TWO_WHEELER comparison is a
separate, potentially more expensive choice. Until that happens, both real-road
adapters remain **prepared but unverified**, and the demo remains simulated.
