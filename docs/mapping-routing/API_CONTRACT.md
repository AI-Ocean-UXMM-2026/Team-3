# Additive routing API contract

Existing endpoints remain unchanged. Base URL is the local FastAPI/BFF workspace;
the website uses its existing same-origin `/dashboard/api` bridge. Never put the
private dev credential into browser fetch code. Native API callers require the
existing local/test `X-Dev-Access-Token` and server-bound actor. Production fails
closed. All new paths begin `/api`.

| Method | Path | Authorization / effect |
|---|---|---|
| GET | `/routes/provider-status` | Dispatcher/admin; config booleans, no provider call |
| POST | `/routes/calculate` | Dispatcher/admin; normalized route; consumes budget |
| POST | `/routes/matrix` | Dispatcher/admin; square costs; consumes budget |
| POST | `/routes/optimize` | Dispatcher/admin; 201 persisted preview, no assignments |
| GET | `/routes/plans` | Dispatcher/admin; `page`, `page_size` pagination |
| GET | `/routes/plans/{plan_id}` | Dispatcher/admin; current stale flag |
| POST | `/routes/plans/{plan_id}/commit` | Dispatcher/admin; atomic, idempotent commit |
| GET | `/riders/{rider_id}/route-plans` | Own rider or dispatcher/admin; latest 20 scoped plans |

Route request:

```json
{"origin":{"latitude":16.8,"longitude":96.1},"destination":{"latitude":16.82,"longitude":96.12},"mode":"DRIVE","allow_simulation":true}
```

Route response fields: `provider`, `origin`, `destination`, `mode`, integer
`distance_meters`, integer `duration_seconds`, optional GeoJSON `geometry`,
`quality` (SIMULATED or ROAD_STATIC), `traffic_aware:false`, `warnings`,
`attribution`. Offline fixture name is `yangon-synthetic-grid-v1`, not a road-data
provider. Matrix requests use `locations` (2 through configured max-stops+1),
`mode`, `allow_simulation`; responses use square `distances`/`durations` arrays,
paired null unreachable cells and the same provider/quality fields.

Optimization request (replace IDs with actual saved records; dates must cover
the parcel delivery day and end in the future):

```json
{
  "origin":{"latitude":16.8,"longitude":96.1},
  "orders":[{"order_id":"00000000-0000-4000-8000-000000000001","demand":1,"service_seconds":180}],
  "riders":[{"rider_id":"00000000-0000-4000-8000-000000000002","capacity":20}],
  "operating_window":{"start":"2026-12-01T08:00:00+06:30","end":"2026-12-01T18:00:00+06:30"},
  "mode":"DRIVE","objective":"duration","return_to_hub":true,
  "solver_seconds":2,"allow_simulation":true
}
```

Plan response: `id`, `version`, `state` (PREVIEW/COMMITTED), UTC `created_at`,
dynamic `stale`, `origin`, `operating_window`, `routes` (rider ID -> existing
workflow-route ID, populated on commit), `result`.

`result` contains `solver:"OR-Tools"`, `solver_status`, `globally_optimal:false`,
`elapsed_ms`, `provider`, `quality`, `traffic_aware:false`, `matrix_size`,
`vehicles`, `unassigned`, `warnings`, `attribution`. Vehicle entries contain
`rider_id`, `stops`, `distance_meters`, `duration_seconds` (travel+wait+service),
`travel_seconds`, optional `geometry` and `geometry_warning`. Stops contain
`order_id`, `sequence`, timezone-aware `arrival`/`departure`, `demand`, `latitude`,
`longitude`. Unassigned entries contain `order_id` and an explainable `reason`.
Input order coordinates are never accepted in place of canonical stored pins.

Commit request:

```json
{"expected_version":1,"acknowledge_unverified_location":true,"allow_simulation":true}
```

List envelopes use `items`, `total`, `page`, `page_size`. Plan preview expiry is
15 minutes by default. Stale plans cannot be committed; create a fresh preview.
Plan listing is read-only and does not refresh provider data.

Errors preserve `{"error":{"code":"...","message":"...","details":[]}}`.
Important statuses: 401/403 access; 404 missing records; 409 version/stale/
incomplete-active-stop/departed-route conflict; 422 invalid coordinates, limits,
simulation acknowledgement, unsupported mode or no route; 429 actor/provider
rate limit; 502 malformed provider data; 503 disabled/missing key/provider
failure; 504 timeout. No provider body or secret is returned. Budget defaults to
10 expensive requests per actor per minute and persists across restart.

The MTT planner invokes the real local adapter, for example:

```javascript
const plan = await store.previewPlan(request); // Uses server-side credential boundary
// Render result. Preview does not assign anything.
await store.commitPlan(plan, {
  acknowledge_unverified_location: true,
  allow_simulation: plan.result.quality === 'SIMULATED'
}); // Explicit dispatcher action only
```

No new public paid-routing proxy, raw provider-key field or automatic assignment
endpoint was added. Replan means POST a new optimization preview from current
records, review it and commit separately.
