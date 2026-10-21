# Controlled Yangon route evaluation

This is preparation, not a live provider result. No Google Routes or ORS API was
called. The evaluator never connects to the application database, creates orders,
changes assignments or modifies the optimization engine.

## Fixed fictional dataset

Source: `backend/tools/routing_evaluation/yangon_points.json`. It contains a hub
and six explicitly fictional delivery coordinates within the existing synthetic
graph's area. They are not customer homes, verified township labels or known
routable road positions. `SYN-YGN-06` is a possible off-road probe; its real
reachability is deliberately unknown. A provider may snap it to a road or reject
it. Neither outcome establishes that delivery to a real doorstep is possible.

| ID | Latitude | Longitude | Intended observation |
|---|---:|---:|---|
| Hub | 16.825 | 96.130 | Shared origin; fictional |
| SYN-YGN-01 | 16.815 | 96.125 | Ordinary test point |
| SYN-YGN-02 | 16.835 | 96.140 | Ordinary test point |
| SYN-YGN-03 | 16.845 | 96.120 | Ordinary test point |
| SYN-YGN-04 | 16.805 | 96.155 | Ordinary test point |
| SYN-YGN-05 | 16.855 | 96.175 | Ordinary test point |
| SYN-YGN-06 | 16.805 | 96.205 | Possible off-road probe, unverified |

The fixture validates unique synthetic IDs, coordinates and the fictional label.
The entire point set must fit configured stop limits; no silent truncation occurs.

## Planned request counts

| Separate evaluation | Route queries | Matrix queries | Matrix elements | Maximum HTTP attempts |
|---|---:|---:|---:|---:|
| Google DRIVE | 6 | 1 | 49 | 7 |
| Google DRIVE + TWO_WHEELER | 12 | 2 | 98 | 14 |
| ORS driving-car | 6 | 1 | 49 | 7 |

All three independent evaluations together would permit **28 HTTP attempts and
196 matrix elements** if separately approved and fully executed. They are not run
automatically together. Actual attempts stop early on failures or budget/deadline
exhaustion. Dry runs of all three were executed with **zero external requests**;
see the adjacent `YANGON_*_DRY_RUN.json` artifacts. Current example configurations
have zero request/element/cost budgets, disabled live execution and no pricing.

For a safe, repeatable dry run from `backend`:

```powershell
.venv\Scripts\python.exe -m tools.routing_evaluation.evaluate --config tools/routing_evaluation/google-drive.example.json --output ..\.tmp\yangon-drive-plan.json
```

Other examples are `google-modes.example.json` and `ors-drive.example.json` in the
same directory. `config.schema.json` documents every accepted field. No key belongs
in these files. Explicit JSON fields take precedence over corresponding process
environment values. The CLI intentionally ignores `.env` files.

## Later live evaluation, only after separate approval

1. Review the chosen provider's current account pricing, SKU/mode, quotas, terms
   and permitted vehicle use. Provide reviewed per-mode unit prices and a small
   estimated-cost ceiling in a private configuration; no price is assumed here.
2. Supply the appropriate server secret through the approved process environment.
   Independently enable the native outbound gate and the evaluation live gate;
   authorize TWO_WHEELER separately if selected.
3. Re-run the dry plan and inspect its counts, price estimate and blockers.
4. With explicit authorization for provider calls, invoke the same tool using
   `--execute-live --evaluation-id yangon-google-drive-001`, an approved private
   configuration and an output path under ignored `.tmp/routing-evaluations/`.
   This invocation was **not executed** in Phase 23.
5. A new exclusive ledger is required for each deliberately approved evaluation.
   Reusing an ID is rejected, including concurrent invocations. A failure does not
   trigger retries or delete/reuse its ledger. Fresh IDs are new evaluations, not
   a way to obtain a cumulative billing guarantee.

## Observations to assess

For each origin-to-delivery pair: provider, mode, static road distance in metres,
duration in seconds, geometry availability/point count, endpoint offsets from the
requested GPS pins, response latency and a sanitized error code. Geometry offsets
are geographic differences, not delivery accuracy or trusted-reference geofence
decisions. Raw provider geometry is not persisted by the report.

For each matrix: row = origin, column = destination, all seven points in fixture
order, distance/duration arrays, paired null unreachable cells and response latency.
Google's streamed elements are placed by indices rather than response arrival
order. Distinct directional costs are preserved; symmetry is not assumed.

The report keeps SIMULATED fixture routes/matrix in a separate section and reports
signed provider-minus-simulation deltas. Compare DRIVE and TWO_WHEELER entries
for the same case ID, including unreachable/error results. These differences do
not measure time savings, accuracy, traffic or real courier ROI. Mock transport
runs say `MOCK_HTTP`; only a later authorized run can observe `EXTERNAL_HTTP`.
`live_verified` remains false pending actual review, not a claim of global coverage.

## Missing-road and coverage review

ORS expects longitude/latitude coordinate pairs. Its matrix preserves source and
destination ordering and durations in seconds; explicit metre units are requested.
[Current ORS matrix documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/)
describes these conventions. This does not establish hosted Yangon road coverage.

Google's [two-wheeler coverage table](https://developers.google.com/maps/documentation/routes/coverage-two-wheeled)
lists Myanmar. Country-level API support does not establish routability, legal
vehicle access or operating suitability on a particular Yangon street. Confirm
those separately before an operational demonstration. ORS TWO_WHEELER is unsupported
by this adapter; driving-car is never relabeled as motorcycle routing.

After observing real results, review missing-road cases and provider-snapped
endpoints before changing optimization policy. No solver changes are justified by
the synthetic comparison alone.
