# Google Demo Key verification — Phase 26

Date: 2026-10-22. Worktree: `LannPya-AI-mtt-integration`.
Branch: `feature/mtt-maps-database-integration`; starting commit `650e040`.

## Current result

**LOCAL PREPARATION COMPLETE; LIVE GOOGLE RESPONSE NOT YET VERIFIED.**

No Google routing request has been sent in this phase. The owner explicitly requires a
separate authorization after reviewing the bounded plan below. Supplying a key does
not override that requirement. No billing, account, deployment, migration, push or merge
was performed. Application provider selection remains unchanged.

The process environment had neither `LANNPYA_GOOGLE_ROUTES_API_KEY` nor
`GOOGLE_ROUTES_API_KEY` configured. `backend/.env` did not exist. A dedicated,
Git-ignored `backend/.env.google-demo.local` template was created **with an empty key**.
No key value from chat was copied into code, shell history, browser configuration,
reports or command arguments. Treat a credential shared in chat as exposed and replace it.

## Provider support checked against official documentation

Google's [Maps Demo Key documentation](https://developers.google.com/maps/demo-key)
lists Compute Routes among supported web services. It describes the Demo Key as
no-cost prototyping without billing information, with usage paused at its daily limit.
The published page does not provide a numeric daily allowance; none is invented here.
This confirms **service eligibility**, not whether this particular key is valid,
unexpired, actually a Demo Key, correctly restricted, or has remaining quota.

The [Compute Routes reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes)
confirms the endpoint, field-mask header and GeoJSON polyline encoding used here.
No request was sent to check key validity because that would itself consume the
bounded live attempt and requires authorization.

## Exact proposed live request

| Item | Planned value |
|---|---|
| Endpoint | `POST https://routes.googleapis.com/directions/v2:computeRoutes` |
| Maximum | **ONE HTTP attempt**, including failures/timeouts |
| Origin | Latitude `16.825`, longitude `96.130` |
| Destination | Latitude `16.815`, longitude `96.125` |
| Points | Fictional Yangon test points, not verified customer addresses |
| Mode | `DRIVE` |
| Routing preference | `TRAFFIC_UNAWARE` |
| Geometry | `GEO_JSON_LINESTRING`, overview quality |
| Response mask | `routes.distanceMeters,routes.duration,routes.polyline.geoJsonLinestring` |
| Quota estimate | One Compute Routes query; zero matrix elements |
| Timeout | 10 seconds; existing bounded response-size/deadline validation retained |
| Retries / redirects | Zero retries; redirects not followed |
| Excluded | Matrix, traffic model, two-wheeler, waypoints, optimization, extra computations |
| Cost | Demo Key allowance only; no billing activation. Do not substitute a billable key. |

The runner overrides only the field mask for this single controlled request. The shared
application adapter retains its existing defensive `fallbackInfo` mask and contracts.
No global routing configuration is written or enabled by preparation/key entry.

## Secure private key entry

In a local interactive PowerShell terminal, from the worktree root:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m tools.google_demo_route --store-key
```

The command prompts with hidden input and writes only the dedicated ignored environment
file. It refuses piped/non-interactive entry and refuses storage unless Git confirms the
file is ignored. The key is never an argument or printed output. This file is local secret
storage, not an encrypted vault; protect the Windows account and filesystem permissions.
Do not enter the private Routes key into frontend settings, a `VITE_*` variable, or
`LANNPYA_GOOGLE_MAPS_BROWSER_KEY`.

The dedicated runner also accepts the existing server-side
`LANNPYA_GOOGLE_ROUTES_API_KEY` process variable, or unprefixed
`GOOGLE_ROUTES_API_KEY`. Its private file is deliberately **not** loaded by the ordinary
application. Native prefixed credentials take precedence. No dotenv values are printed.

To inspect the plan without making any request:

```powershell
.\.venv\Scripts\python.exe -m tools.google_demo_route
```

### After explicit owner authorization only

Confirm that the replacement key is genuinely a Demo Key rather than a paid project key.
The following is prepared for the authorized execution step; **it has not been run**:

```powershell
# From backend/, only after the owner approves the exact plan above.
$env:LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED = 'true'
try {
  .\.venv\Scripts\python.exe -m tools.google_demo_route --execute-live --confirm-demo-key
} finally {
  Remove-Item Env:LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED -ErrorAction SilentlyContinue
}
```

This process-scoped gate does not change any already-running backend. The CLI reserves
`.tmp/google-demo/prompt26-attempt.json` using exclusive file creation and fsync before
connecting. A second invocation is refused even after a failure or process restart.
Do not delete/recreate that ledger to retry; another attempt needs separate approval.
The test runner uses isolated temporary ledger paths and mock HTTP transports.

## Response validation and labels

The shared Google adapter validates distance, protobuf duration and GeoJSON positions.
`[longitude, latitude]` ordering is preserved; duration is rounded up to whole seconds.
Negative, missing, malformed, oversized and out-of-range values cannot become success.
No encoded-polyline decoder is necessary: the request explicitly selects GeoJSON.

Only successful validation after a real HTTP transport can produce the observation
`GOOGLE_LIVE`. Mock transports produce `MOCK_HTTP`; dry plans produce `NOT_EXECUTED`;
errors produce `NOT_VERIFIED`. The established API quality remains `ROAD_STATIC`,
with `traffic_aware=false`; this is not a live-traffic ETA or an accuracy guarantee.
The CLI prints validated distance/duration/geometry count, not raw geometry or keys.

On rejection it reports the actual HTTP status and safe canonical Google status/code
and recognized ErrorInfo reasons. Free-form error messages and metadata are excluded
because they can echo credentials or request information. It stops without retries,
provider switching or simulated success. No rejection was observed yet: no live call ran.

## Frontend display and Leaflet boundary

The normalized GeoJSON is technically consumable by Leaflet. However,
[Google's Routes display policy](https://developers.google.com/maps/documentation/routes/policies)
requires Google route results displayed on a map to use a Google map. The existing
`LannPyaCustomerMap.routeView(..., 'google')` correctly preserves that distinction:
it converts positions to `{lat, lng}` for a Google polyline and withholds geometry when
the Google map is unavailable. Leaflet remains available for offline/ORS routes.

Do not remove that safeguard merely to draw a Google road line on an OSM basemap.
The real display step needs an appropriate separately restricted public Maps JavaScript
key and authorized map loading. The private backend Routes credential must not be
reused as a browser key. Neither Google SDK nor Google tiles were fetched in this phase.

Chromium tests verified the existing conversion contract using a **stub Google renderer**,
the no-Google-map withholding state, and real local Leaflet rendering of fictional geometry.
Those tests do not constitute a live Google map or real Yangon route display.
Actual live geometry/display verification remains pending the authorized provider response
and an appropriately configured map. Google content was not cached or committed.

## Local changes

- `backend/tools/google_demo_route.py`: network-free plan, masked key storage, guarded
  one-attempt execution, sanitized failure reporting; no database access.
- `backend/tests/test_google_demo_route.py`: 24 mock-only regression cases.
- `tests/browser/google-route-display.spec.cjs`: three real Chromium local display tests.
- This verification document; ignored empty private environment template.

Application source, frontend design, shared adapter, SQLite schema, OR-Tools engine,
offline provider, existing APIs and authentication were not modified.

## Verification results

- Targeted Python routing/evaluation/one-shot checks: **99 passed**, three upstream
  OR-Tools SWIG deprecation warnings.
- New one-shot tests after private-file guard addition: **24 passed**.
- Existing frontend Node tests: **112 passed, zero failed**.
- Existing routing Chromium scenarios: **3 passed** (preview/commit/COD/replan,
  stale preview rejection, unavailable routing/missing pins).
- New Chromium display scenarios: **3 passed** on final run. An initial cleanup assertion
  incorrectly expected Leaflet to remove its container CSS class; corrected the test to
  assert layer/control removal. No application bug or behavior change was involved.
- Frontend build: **27 validated assets**, no keys/environment files bundled.
- Dependency compatibility: `pip check` passed.
- Full backend regression suite: **972 passed, zero failed**, in 117.63 seconds;
  three upstream OR-Tools SWIG deprecation warnings.
- Ruff lint and formatting: passed; **103 files already formatted**.
- `git diff --check`: passed. Exactly four new tracked-candidate files; no application
  source changes or retained generated screenshot changes. Secret-pattern scan of those
  four files found zero Google-key patterns. The private template is ignored/untracked;
  the live-attempt ledger does not exist, confirming no runner reservation/execution.

## Next step

Privately supply a replacement Demo Key and authorize the **one DRIVE request** specified
above. Until then, real route availability, actual distance/duration, key restrictions,
remaining quota and live Google map display are unverified. Keep ordinary application
routing offline and preserve existing OR-Tools/simulation behavior.
