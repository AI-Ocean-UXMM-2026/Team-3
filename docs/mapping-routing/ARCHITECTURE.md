# Mapping and routing MVP

Foundation: `feature/mtt-maps-database-integration`, based on MTT commit
`0e95c6a9970198a345622a145330749aaabca83f`. Existing uncommitted Phase 19 work was
preserved; a local backup is under ignored `.tmp/phase22-baseline/`. No branch was
merged, reset, pushed or deleted.

## Audit and changes

Before this work, MTT already had interactive Leaflet pin selection/dragging,
permission-based device GPS, buyer verification, dispatcher review, persistent
orders, assignments, queues, COD and history. These remain authoritative. Its
workflow routes were persistent dispatcher stop lists, without a road matrix or
optimization solver. The TypeScript parser and browser prototype remain separate
research/demo capabilities, not routing engines.

New flow: existing location review -> canonical database coordinates -> protected
routing adapter -> validated matrix -> OR-Tools preview -> persistent PREVIEW ->
explicit, version-checked transactional commit -> existing workflow assignments
and queue. AI never supplies optimization costs or coordinates.

- `backend/app/routing/`: provider interface, offline fixture, HTTP adapters, solver.
- `app/schemas/routing.py`: normalized requests, geometry, matrices and plans.
- `app/services/route_planning.py`: eligibility, budgets, snapshots, commit and privacy.
- `app/api/routing.py`: eight additive protected operations.
- `frontend/js/routing-ui.mjs`: planning panel and rider plan viewer in existing MTT UI.
- `frontend/js/live-store.mjs`: existing local BFF adapter plus routing calls.

## Persistence and security

Alembic `0005_routing_plans` follows `0004_workflow_routes`. It adds `routing_plans`
(UUID, actor FK, optimistic version, state, UTC timestamp, JSON query/result/basis)
and `routing_rate_limits` (actor FK, minute bucket, count). Existing order,
assignment, workflow-route and event tables remain authoritative. JSON uses the
existing PostgreSQL JSONB variant; PostgreSQL execution has not been verified.

Preview creation saves no assignments. Commit locks selected records, rechecks
versions/queue state/expiry, uses existing assignment guards without intermediate
commits, updates stop sequences and records `RIDER_SEQUENCE_CHANGED` events carrying
the plan ID. An injected second-assignment failure rolls back the whole commit.
Repeated commit requests are idempotent. Old plans are retained for audit.

Routing is dispatcher/admin only; riders may retrieve only their own filtered
plans and currently assigned stops. No new public coordinate endpoint exists.
The loopback BFF keeps private keys/dev tokens server-side and preserves session,
CSRF, origin and production fail-closed controls. Public production authentication
remains a blocker; this is not a public administrator application.

## Running locally

From the repository root in PowerShell:

```powershell
npm.cmd start -- --port 8781 --state phase22-local
```

Open `http://127.0.0.1:8781/#/routes`. This named workspace is separate from the
normal development database. For a disposable workspace:

```powershell
npm.cmd start -- --port 8781 --temporary
```

The launcher applies migrations to its own workspace only. No regular database
was migrated during verification. The existing local Python environment now has
the pinned OR-Tools dependency. Clean setup uses
`backend/requirements-dev.lock`, then `pip install --no-deps -e backend`.

See [API contract](API_CONTRACT.md), [solver](ROUTE_OPTIMIZATION.md),
[providers](ROUTING_PROVIDERS.md) and [verification](TEST_RESULTS.md).
