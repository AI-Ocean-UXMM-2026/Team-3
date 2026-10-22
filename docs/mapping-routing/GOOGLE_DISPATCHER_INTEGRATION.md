# Phase 28 — Google dispatcher and rider estimates

Worktree: `LannPya-AI-mtt-integration`, branch `feature/mtt-maps-database-integration`.
Date: 2026-10-22. **No live Google routing requests were made in this phase.**

## Implemented workflow

The existing Routes screen and rider route panel now include **Google road estimate —
single delivery**. This is separate from the existing SIMULATED OR-Tools optimizer.

1. The UI reads server enablement and remaining budget. Opening or refreshing a page
   does not calculate a route or contact Google.
2. An authorized dispatcher selects an order and explicitly enters an origin. A rider
   can select only their queue's orders; the API independently enforces active assignment.
3. The operator checks explicit external-request consent and submits. The backend uses
   the canonical delivery coordinates, not a client-supplied destination. Missing,
   unreviewed, pending-buyer-review and completed delivery locations are rejected.
4. A successful Google response displays road kilometers, static travel minutes and
   Google Maps attribution. `GOOGLE_LIVE`, `GOOGLE_MOCK` and the optimizer's `SIMULATED`
   labels remain distinct. No numeric location confidence is inferred.
5. No assignment, delivery status, order pin, OR-Tools cost matrix or committed route
   plan is changed. Results are transient; refreshing clears the estimate.

The UI disables submission while pending and after each attempt. It does not retry
automatically or turn a failure into a simulated success. Editing routing inputs clears
the old estimate and consent; further requests remain subject to the server budget.

## Protected additive API

Existing local/test development access and loopback protections remain mandatory.
Production still fails closed. The same-origin local BFF holds private credentials and
requires its existing session/CSRF checks. Never expose its privileged tokens in JavaScript.

### GET /api/routes/google-demo/status

Dispatcher, admin or rider; no credential loading or provider request. Example default:

```json
{"enabled":false,"maximum_requests":0,"reserved_requests":0,"remaining_requests":0,
 "explicit_consent_required":true,"matrix_supported":false}
```

Enablement reports permission/configuration, not verified key validity or remaining
Google-project quota. Exhausting the local budget does not imply Google's quota is exhausted.

### POST /api/routes/google-demo

Example request (fictional IDs and origin):

```json
{"order_id":"11111111-1111-4111-8111-111111111111",
 "origin":{"latitude":16.825,"longitude":96.130},
 "request_id":"22222222-2222-4222-8222-222222222222",
 "authorize_external_request":true}
```

The consent value must be literal JSON `true`; strings and numeric substitutes fail
validation. Unknown fields such as `mode`, `destination`, or matrix locations are rejected.
The server fixes mode to DRIVE and preference to TRAFFIC_UNAWARE. One request produces
one Compute Routes POST, without retries, redirects, advanced features or matrices.

Response fields are `observation`, `order_id`, `request_id`, and `route`. The latter is
the existing normalized RoadRoute schema: provider, origin, destination, mode, meters,
seconds, GeoJSON geometry, quality, traffic flag, warnings and attribution. Quality is
`ROAD_STATIC`, traffic-aware is false. Test transports explicitly produce `GOOGLE_MOCK`;
only a real successful transport produces `GOOGLE_LIVE`.

Browser integration uses the existing store/BFF, e.g.:

```javascript
const result = await store.googleEstimate({
  order_id: selectedOrderId,
  origin: { latitude: selectedLatitude, longitude: selectedLongitude },
  request_id: crypto.randomUUID(),
  authorize_external_request: true
}); // Rider UI passes 'rider' as the second argument.
```

401: missing local credential; 403: wrong role/unassigned rider; 404: missing order;
409: review needed, terminal order or previously attempted request ID; 422: invalid
payload; 429: local budget exhausted or provider rate limit; 503: disabled/missing key/
provider rejection; 502/504: invalid provider response/timeout. Errors never include keys
or provider payloads and never substitute a simulated result.

## Durable quotas and authorization

These settings default to **zero live requests**:

```dotenv
LANNPYA_ROUTING_PROVIDER=offline
LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED=false
LANNPYA_GOOGLE_DEMO_ENABLED=false
LANNPYA_GOOGLE_DEMO_MAX_REQUESTS=0
```

After a **separate owner approval for additional live calls**, a local operator can enable
both flags and set a reviewed total budget from 1 to 10 in the launcher process environment.
Do not enable them merely because Phase 27's one call succeeded; that authorization is
already consumed. No such settings were enabled by this implementation.

The backend uses the native private Routes setting when present, otherwise the existing
ignored `backend/.env.google-demo.local`. This private credential is loaded only after
enablement, access, input and order checks. It is never copied to maps-config or a bundle.
The normal integrated launcher continues ignoring ordinary `.env` files; the dedicated
private key file is loaded explicitly by this operation only.

The default shared reservation directory is `.tmp/google-dispatch-budget` at the repo root.
`LANNPYA_GOOGLE_DEMO_BUDGET_DIRECTORY` can choose a server-owned path for isolated tests.
Atomic exclusive request-ID and budget-slot files are flushed/fsynced before any provider
call. Slots cover all actors/workers and do not reset on backend restart or test-database
reset. Provider rejection, invalid responses and timeouts consume their reserved slots.
Duplicate requests never replay stored Google content. Ledger failures fail closed.
Do not delete/change the directory to bypass a spent budget. New budget authorization is
an operator decision, not a public API. No database migration or route-result cache exists.

## Google display, Demo Key licensing and attribution

Reviewed [Demo Key features](https://developers.google.com/maps/demo-key) include Compute
Routes and Maps JavaScript rendering; Demo Keys are for prototyping, not production.
The published quota description does not promise a numeric allowance, so none is assumed.
Project entitlement and billing classification cannot be inferred from key syntax.

[Routes policies](https://developers.google.com/maps/documentation/routes/policies) require
Google route data shown on a map to use a Google map and proper attribution. They also
restrict caching and require suitable terms/privacy notices for applications.

The existing Google-map renderer is preserved. A result offers **Show route on Google map**
only if a separate restricted Maps JavaScript browser credential is already configured.
Loading that map requires the additional explicit button action. Do not reuse the private
Routes key as a browser credential. We did not configure or expose any browser key.

Without that browser configuration the app displays attributed numeric results and a
clear map-display blocker, and never draws Google geometry on Leaflet. Leaflet customer
pinning, OSM/offline maps, independent distance calculations and existing navigation links
remain intact. Google SDK attribution is not hidden or modified. The UI does not persist
Google results to localStorage or to the database.

No real Google Maps SDK display was tested here. Chromium used a stub Google renderer
to verify coordinate conversion/withholding, and local Leaflet for synthetic geometry.
Owner-approved browser credential configuration, appropriate restrictions, attribution
review and terms/privacy notices remain prerequisites to a real/public map demonstration.

## Verification and findings

- Targeted backend routing/one-shot/evaluation checks initially: 120 passed.
- New browser checks cover consent, one explicit mocked request, units, attribution,
  GOOGLE_MOCK/GOOGLE_LIVE presentation, no Leaflet overlay, failure without retry,
  clearing on refresh and default disablement.
- Existing browser routing/COD/replanning flow initially caught a missing rider proxy
  allowlist entry. Fixed only these new paths; backend own-assignment checks remain enforced.
- First full backend pass found two outdated generated OpenAPI snapshots. Regenerated
  both snapshots, documented the new operations and updated the inventory count 43 → 45.
- Final full backend regression: **997 passed, zero failed**, 134.38 seconds. Includes
  **17 new Google estimate tests**. Three existing OR-Tools SWIG deprecation warnings remain.
- Frontend Node regression: **112 passed**; dashboard Node regression: **17 passed**.
- Relevant Chromium coverage: **10 distinct scenarios passed** across the Google workflow,
  Google/Leaflet display boundary and existing optimization/rider COD/replanning specs.
  The four Google workflow scenarios were rerun after adding a safe local budget-status
  refresh following each attempt. Status refresh never contacts Google.
- Frontend build: **27 validated assets**. Ruff lint/formatting and `pip check` passed.
  Both generated OpenAPI snapshots match the app's **45 operations**; diff checks passed.
- Private key pattern scan: zero matches in changed sources. Defaults confirmed disabled,
  external routing false, Google budget zero, optimizer offline, no dispatcher ledger created.
  No model/migration/database-file changes; no credential file tracked or modified.
- No Google routing call occurred. Phase 27's historical 1.741 km / 6.75 min success is
  not presented as a new observation. Browser Google responses were intercepted fixtures;
  backend provider tests used MockTransport. No real Google SDK rendering was claimed.

## Remaining simulated and blocked capabilities

The optimizer's matrix, costs, road geometries and times remain explicitly SIMULATED.
No Google matrix support is assumed for the Demo Key, and no matrix is synthesized from
single-route responses. Existing rider stop sequences and assignments are preserved.
This feature does not enable live traffic, continuous GPS tracking or automatic replanning.
Production authentication/tenancy, public deployment, PostgreSQL verification, independent
geospatial accuracy and broader routing coverage remain separate workstreams.
