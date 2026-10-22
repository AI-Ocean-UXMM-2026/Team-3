# Phase 30 acceptance checklist (established before implementation)

Preserve worktree/branch and all Phase 26–28 local changes. No live routing calls,
billing, Supabase, schema migration, merge, push or deployment is authorized.

| Area | Existing evidence / gap | Acceptance work |
|---|---|---|
| Customer map | Leaflet clicks, drag and click-only GPS already implemented | Re-run real Chromium, five viewports, GPS deny/unavailable/timeout and persisted review |
| Location policy | Server Haversine/trusted reference, initial review and 500 m tests exist | Re-run buyer security/geofence regressions; no GREEN from a pin |
| Google routes | One historical live success; default-disabled bounded dispatcher action | Re-run mock errors, privacy, duplicate/concurrent budgets; no new live calls |
| Google map | Provider boundary exists; no authorized browser renderer credential supplied | Add route endpoint/approved-stop markers and key-free navigation fallback; mocked renderer tests |
| Real matrix | Google Demo Key list omits matrix; ORS adapter already exists | Review official provider limits, validate boundary with mocks, retain explicit SIMULATED optimizer |
| Optimization | Capacity, service times, windows, assignment locks and bounds implemented | Add priority-based selection; add capacity/window inspection; test infeasible, multi-rider and unavailable cases |
| Dispatcher/rider | Preview, versioned commit, own queues, COD and replan exist | Full browser workflow, default-safe Google panel, refresh and navigation tests |
| Updates | Explicit Refresh retrieves REST queue; no push | Verify approved changes on refresh, stale versions and failed reads; document refresh contract |
| Replanning | Snapshot/version consistency already implemented | Exercise reschedule, pin/rider/status changes, duplicate commits and completed-stop preservation |
| Persistence | Existing real HTTP restart tool covers completed order/events | Extend isolated restart demonstration to saved optimized plans/sequence |
| Release | Prior counts historical; uncommitted work preserved | Full Python/Node/TS/browser/build/lint checks; secret/artifact review and local commit manifest |

Hardware GPS accuracy, live browser Google rendering and genuine road-matrix results
cannot be inferred from synthetic browser/API fixtures. Record provider blockers explicitly.
