# Phase 27 — First authorized live Google route test

Date: 2026-10-22. Worktree: `LannPya-AI-mtt-integration`.
Branch: `feature/mtt-maps-database-integration`.

## Actual result: GOOGLE_LIVE

| Measurement | Observed result |
|---|---|
| HTTP status | **200** |
| Live HTTP attempts | **Exactly one** |
| Road distance | **1,741 meters / 1.741 km** |
| Estimated travel duration | **405 seconds / 6.75 minutes** |
| Geometry | Valid encoded polyline returned; successfully decoded and validated |
| Geometry points | **31** |
| Travel mode | `DRIVE` |
| Routing preference | `TRAFFIC_UNAWARE` |
| Data classification | `GOOGLE_LIVE` observation; normalized API quality `ROAD_STATIC` |
| Live traffic | No |
| Runner exit code | `0` |

The stored credential loaded successfully without being printed and matched the
Git-ignored private key file. No credential value, provider message containing
credentials, raw encoded geometry, or full route coordinates are included in this report.

## Exact authorized request

`POST https://routes.googleapis.com/directions/v2:computeRoutes`

```json
{
  "origin": {"location": {"latLng": {"latitude": 16.825, "longitude": 96.130}}},
  "destination": {"location": {"latLng": {"latitude": 16.815, "longitude": 96.125}}},
  "travelMode": "DRIVE",
  "routingPreference": "TRAFFIC_UNAWARE",
  "polylineEncoding": "ENCODED_POLYLINE",
  "polylineQuality": "OVERVIEW",
  "computeAlternativeRoutes": false,
  "regionCode": "MM"
}
```

These are fictional Yangon test coordinates, not real customer records or verified
doorstep locations. Only the following response fields were requested:

```text
routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline
```

Authentication used the stored server-side API key header. No project/quota-project
override was supplied. No matrix, traffic-aware, two-wheeler, alternative-route,
waypoint optimization, browser SDK, map tile, billing or account-management request ran.

## Demo Key and billing verification boundary

The owner identifies the replacement credential as a Maps Demo Key. Google accepted
that credential for this Compute Routes request, proving it is currently authorized
for this operation. **The response does not independently prove the Cloud project's
Demo Key classification or billing status.** Verifying those account properties would
require separate account access/calls, which were outside this authorization.

No billing was enabled or changed, and no account resources were created. No monetary
charge or remaining daily allowance is inferred from HTTP 200. The request used the
project associated with the stored API key, without switching projects or bypassing
restrictions. Published Demo Key support was reviewed during Phase 26; no additional
documentation/network requests were made during this test.

## Safeguards and validation

- Existing live-request gate enabled only for the runner process and restored afterward.
- Existing exclusive, durable reservation ledger used before network access:
  `.tmp/google-demo/prompt26-attempt.json`. The filename is retained from preparation;
  this ledger now records the Phase 27 authorized attempt. Do not remove it to retry.
- HTTP transport retries: zero. Redirect following: disabled. Timeout: 10 seconds.
- Response size/deadline guards and strict routing response validation retained.
- Encoded geometry decoded at Google's five-decimal precision into GeoJSON
  `[longitude, latitude]` pairs, with coordinate ranges and point count validated.
- Numeric distance and duration validated by the existing shared adapter. Duration
  is represented in whole seconds by its existing rounding-up convention.
- No silent simulation fallback. A rejected/invalid response would stop the runner.
- Summary saved locally in ignored `.tmp/google-demo/phase27-result.json`; raw Google
  geometry remained in process memory and was not persisted or committed.

## Display policy and application preservation

No map display or browser requests were performed. Google geometry was **not** drawn
on Leaflet. The existing Google-map display boundary remains unchanged; Leaflet remains
available for existing offline/OSM-based workflows. This result verifies a backend road
route response, not live Google map rendering, navigation accuracy or real-world ETA.

The regular backend, frontend, database, OR-Tools optimizer, simulated provider,
authentication and API contracts were not modified or restarted. Normal application
routing was not switched to Google. No push, merge, deployment or migration occurred.

## Related local tool changes and checks

The existing one-request tool gained an opt-in `--encoded-geometry` flag so this test
could request precisely the encoded geometry authorized in Phase 27. Default GeoJSON
behavior remains unchanged. Six added mock-only cases cover the exact encoded request,
known polyline decoding, malformed values and missing/truncated geometry.

- Preflight one-shot tool tests: **32 passed**; all HTTP responses mocked.
- The live request above: **one attempt, HTTP 200, valid normalized route**.
- One-shot tool and routing-evaluation regression checks: **70 passed, zero failed**
  in 1.37 seconds; all test HTTP responses mocked.
- Ruff lint and formatting checks: passed. `git diff --check`: passed.
- Private key file, attempt ledger and sanitized local result confirmed Git-ignored.
- Branch unchanged; existing unrelated local files preserved.

## Limitations and next steps

This is one successful static DRIVE route between two test points. It does not verify
regional coverage across Yangon, multiple modes, matrices, traffic-aware ETA, sustained
quotas, production billing, frontend Google map rendering, or road accessibility for
motorcycles. No further live calls are authorized by this result. Any additional live
evaluation requires a separate bounded authorization.
