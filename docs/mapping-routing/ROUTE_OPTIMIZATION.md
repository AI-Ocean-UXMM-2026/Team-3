# Bounded multi-rider optimization

The engine uses Google OR-Tools 9.15.6755 RoutingModel, independently of the AI
layer. It consumes a provider matrix and canonical eligible order locations.
Input supports one hub, up to 50 selected orders (configured default 25), up to
10 available riders, per-rider parcel capacities, per-order integer demand and
service time, a timezone-aware operating period of at most 24 hours, distance or
duration objective, and optional return to hub. Solver time is 1–10 seconds.

Delivery windows come from the stored order, not an untrusted frontend override.
Both approved ISO start/end windows and native MTT `HH:mm–HH:mm`/`HH:mm-HH:mm`
windows anchored to the parcel's Yangon delivery day are supported. Unsupported
free text is excluded with a review reason. Service must finish within the
window; travel, waiting and service must fit the operating period. Capacity and
time constraints are hard. Unreachable arcs are removed.

Existing active rider assignments are fixed. Unavailable/unselected assigned
riders result in unassigned reasons; no parcel is silently transferred. A
dispatcher must use the existing permitted unassign flow before replanning for a
different rider. Started deliveries cannot be unassigned through this shortcut.

Droppable stops use a large penalty so the solver can report partial/infeasible
plans rather than violating constraints. Returned reasons identify definite
pre-validation failures; the combined `CAPACITY_TIME_WINDOW_UNREACHABLE_OR_SEARCH_LIMIT`
reason intentionally does not assert an unsolved exact cause. FEASIBLE means a
valid solution was found, not a globally optimal route. Search timeout is bounded.
There is no measured travel-time-savings claim.

## Preview, commit and replan

The Routes screen includes an additive planner: choose hub coordinates, operating
hours, eligible orders, available riders and capacities. A map click selects the
hub only, not a customer's doorstep. Explicit simulation acknowledgement is
required for offline routing. Preview persists query/matrix-derived result and
snapshots, with ordered stops, planned arrivals, distances/durations, geometry,
warnings and excluded orders; it does not assign or dispatch parcels.

Commit is separate and requires the plan version, location-accuracy acknowledgement
and simulation acknowledgement where applicable. It rejects expired/stale plans,
missing eligible stops and any attempt to omit a rider's other active stops.
Assignments/sequence/events commit atomically through existing lifecycle guards.
Committing does not send the rider out; the existing dispatch action remains.

Replanning uses a new preview from current records. Order versions, rider status
and queue versions invalidate old plans after edits, approval, cancellation,
delivery/failure or assignment changes. Completed/failed/cancelled stops are
excluded; existing workflow history remains. A departed route cannot acquire new
parcels, but its remaining active stops may be explicitly resequenced. No automatic
background reassignment occurs. Static estimates on stale plans must not be used
as current promises.

[OR-Tools time windows](https://developers.google.com/optimization/routing/vrptw)
and [dropping visits](https://developers.google.com/optimization/routing/penalties)
informed the model. Windows OR-Tools 9.15's `SetAllowedVehiclesForIndex` Span
binding rejected Python lists during testing; the implementation restricts the
VehicleVar domain instead while retaining the optional dropped-stop value.

## Reproducible benchmark

```powershell
cd backend
.venv\Scripts\python.exe -m tools.routing_benchmark --output ..\docs\mapping-routing\BENCHMARK.json
```

This owns a disposable SQLite database, creates 50 fictional orders, runs 5/10/20/50
stop previews (three samples each), checks capacity/horizon and reopens storage.
No real routing service is contacted. See the JSON artifact and TEST_RESULTS for
actual timings and the limitations of three-sample percentiles.
