# Provider-independent road routing

`RoadProvider.get_route(RouteQuery)` and `get_route_matrix(MatrixQuery)` return
Pydantic-validated, provider-neutral values. Distances are integer metres; durations
are seconds; GeoJSON positions are `[longitude, latitude]`. Matrices are complete,
square and bounded; unreachable pairs use paired `null` values, never zero-cost
roads. Zero diagonals are required. No provider receives customer names, phone
numbers or delivery notes: only coordinates, mode and routing settings.

| Provider | Route/geometry | Matrix | Current verification |
|---|---|---|---|
| `offline` | Invented fixture graph | Deterministic fixture costs | Executed locally, always SIMULATED |
| `google` | Compute Routes, GeoJSON, static duration | Compute Route Matrix, 20x20 chunks | Mock HTTP contract/error tests; no live call |
| `ors` | driving-car GeoJSON directions | driving-car matrix | Mock HTTP contract/error tests; no live call |
| `disabled` | Unavailable | Unavailable | Explicit error; no fallback |

Offline routing is restricted to local/test environments and requires
`allow_simulation: true` on each request and commit. Its fixture is
`app/data/routing_fixture.json`: an invented Manhattan grid within latitudes
16.75–16.95 and longitudes 96.05–96.25. Distances are synthetic edge/connector
costs, not measured Yangon roads. Straight-line connectors are explicitly part
of this invented test graph; they are never called live road-network distance.
Out-of-fixture points fail explicitly.

Google and ORS require server-side credentials and the external-request gate.
They never silently fall back to offline data. Both currently return ROAD_STATIC,
not traffic-aware estimates. Error responses distinguish disabled/missing key,
credentials/quota rejection, rate limit, timeout, unsupported request/mode,
missing route and invalid provider response without exposing response bodies or
keys. Responses are capped at 2 MB and the provider has a shared configurable
deadline, including matrix chunks and itinerary geometry requests. A successful
matrix can still support a plan when geometry fails; an explicit geometry warning
is returned instead of drawing partial/fabricated lines.

ORS uses OSM-derived data, not proof that Yangon access restrictions or traffic
conditions are complete. Its hosted quotas, matrix limits, attribution and terms
depend on the approved service plan. No account/quota/road quality was verified.
TWO_WHEELER is not mapped to ORS driving-car.

Sources checked for adapter design:

- [Google Compute Routes REST](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes)
- [Google Compute Route Matrix REST](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix)
- [Google two-wheeler coverage](https://developers.google.com/maps/documentation/routes/coverage-two-wheeled) lists Myanmar (MM); mode remains explicit opt-in and was not live-tested.
- [ORS directions](https://giscience.github.io/openrouteservice/v9.10.0/api-reference/endpoints/directions/), [matrix source documentation](https://github.com/GIScience/openrouteservice/blob/main/docs/api-reference/endpoints/matrix/index.md), [FAQ](https://giscience.github.io/openrouteservice/v9.10.0/frequently-asked-questions).

Google geometry is displayed only through the optional Google map integration.
If that map is unavailable, the UI withholds Google geometry rather than placing
Google road data on an unrelated Leaflet basemap. Offline/ORS geometry uses
Leaflet and appropriate attribution. Confirm current provider terms and display
requirements before enabling a public service.
