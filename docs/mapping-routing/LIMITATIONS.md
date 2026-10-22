# Remaining limitations and release boundaries

- Optimization remains SIMULATED on an invented fixture graph. One separately
  authorized Google DRIVE request succeeded in Phase 27; this is not evidence for
  matrix support, live traffic, regional coverage or production readiness. Phase 28
  adds default-disabled single-order Google estimates with a durable global budget.
  Phase 28 itself uses mock responses only; ORS remains mock-tested. Additional
  live requests require separate owner approval. See GOOGLE_DISPATCHER_INTEGRATION.md.
- No live traffic-aware ETA, independent geocoding accuracy, township boundaries,
  real-time rider tracking or guaranteed global route optimum is claimed.
- A buyer/dispatcher-approved pin is not independently verified. GREEN remains
  governed by the existing trusted-data validation policy, never route quality.
- Production authentication and tenant/role authorization remain unfinished.
  The current credential-holding BFF is loopback/test only; do not publish it.
- PostgreSQL execution/concurrency is unverified. Current tests and benchmarks use
  disposable SQLite databases; Supabase migration is intentionally postponed.
- One hub and one planning period; no multi-depot, vehicle break, load-weight,
  pickup/delivery precedence, continuous fleet telemetry or traffic constraints.
- Existing assignments remain fixed. Unavailable-rider reallocation requires
  permitted explicit unassignment; no automatic transfer of in-flight parcels.
- A committed plan does not depart the route. New parcels cannot be added to a
  departed route through replanning. Every active stop of a selected rider must
  remain in a committed solution.
- Replanning is explicit, not background automation. Any canonical order/queue
  change makes prior estimates stale. The rider should follow the refreshed
  current queue and approved navigation pin, not stale arrival promises.
- Maximum 50 stops, default 25; 10 riders; 10-second solver budget. ORS hosted
  quotas and Google element limits still apply independently. Many geometry
  requests may exhaust the shared provider timeout; matrix plans remain available
  with explicit geometry warnings. Aggregate geometry is capped at 20,000 points.
- Three benchmark samples per size provide a bounded smoke measurement, not a
  robust production percentile or proof of travel savings. Synthetic coordinates
  are fixture labels, not actual customer homes.
- OR-Tools emits three upstream SWIG deprecation warnings on this Python 3.14
  Windows environment. They do not fail current tests. The pinned development
  lockfile targets the verified Python 3.14 setup (NumPy requires Python >=3.12).

Next: team review of local workflows; approved small live-provider smoke test;
trusted location/boundary data; production authorization and deployment budgets;
isolated PostgreSQL verification. None requires changing the current frontend
design or replacing the deterministic parser.
