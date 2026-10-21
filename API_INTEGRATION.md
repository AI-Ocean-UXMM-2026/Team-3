# LannPya API workspace

The supplied FastAPI backend is connected through **api.html**. The existing
index.html remains the local-storage prototype, with an **API workspace** link.
They are separate modes: API saves use the database; a failed API write never
falls back to a fake local success. Browser records are not deleted or imported.

## Start on this computer

Dependencies are installed in `lannpya-ai/backend/.venv` (Python 3.12).
From PowerShell:

```powershell
cd D:\Zero_Lag\lannpya-ai\backend
.\.venv\Scripts\python.exe -m scripts.run_workspace
```

Keep that terminal running. Open **http://127.0.0.1:8000/api.html** manually.
Ctrl+C stops the three loopback-only API processes. Occupied ports cause a safe
startup failure, not termination of another server. No orders are seeded/reset.
The dedicated `backend/data/workspace.sqlite3` is migrated without touching the
old developer/demo database.

The ignored `backend/data/workspace_access.json` holds connection records for
Admin, Ko Aung and Ko Wai. Open it privately in your editor. Enter the matching
base_url and token in the app's connection form. Never share the file, paste its
contents into chat, commit it or serve the data directory. Tokens rotate on
restart and stay only in frontend memory. Reloading requires reconnecting.
This is local development access, not real login.

## Test one parcel

1. Admin: connect with the admin record (port 8000).
2. Add order: valid Myanmar phone, recipient, item, township, amount and today.
   Availability is Any time. Tick hub receipt only if physically present.
   Leave coordinates empty to exercise customer-side submission.
3. On the new order, **Create / reissue customer link**. This moves a draft into
   review and produces its secret link. Open/share it privately.
4. Customer: enter the phone's last four digits. Submit coordinates deliberately
   (GPS optional), then At home or another response. Review-required results
   are shown as pending, not incorrectly labelled confirmed.
5. Admin: Refresh and review each pending customer request with a reason. Check
   the point yourself. No trusted boundary/geocoding dataset is installed;
   operator approval does not manufacture GREEN map confidence.
6. On this same order, use **Prepare & assign parcel**: choose an existing
   matching-day draft route or an available rider to create a new one. Explicitly
   acknowledge map accuracy; tick physical hub receipt if it was not already
   recorded. Saved fields, pending customer requests and incidents are checked
   first. Review, receipt, optional route creation and assignment commit as one
   transaction; any failure rolls all of them back. No empty route is left behind.
   Customer edits freeze when prepared; missing coordinates block readiness.
7. The assigned route now appears on this same order. Use **Dispatch route**
   once the rider and all parcels on it are physically ready. Departure remains
   a separate confirmation and dispatches the whole route, not just this parcel.
   A future route can be planned today but can depart only on its Yangon date.
8. Rider: connect with the matching rider record (8001 Ko Aung, 8002 Ko Wai).
   Refresh queue. The current stop is prominent; other stops are collapsible.
   Only that rider's work appears. Tap Delivered, wait two seconds,
   then save actual cash. Differences need a reason; prepaid allows zero only.
   Cancel leaves the delivery incomplete.
9. After all deliveries/physical returns, Rider taps **Hand over [total]** once.
   Different amount is reserved for an explained mismatch.
10. Admin: Refresh → **Receive cash & close route**. Count cash, enter actual
    receipt and confirm once. Receipt and closure commit together if all checks
    pass. Cash differences require review; collection discrepancies and incidents
    remain separate blockers even if hub cash matches.
11. With another blocker, valid receipt is retained and the route stays open.
    Resolve it, then Close route without receiving/counting cash again.

Failed deliveries require admin physical-return receipt before handover/closure.
An empty rider queue now states the next action: return parcels to the hub,
submit cash, wait for physical hub receipt, or wait for admin resolution. It does
not imply closure just because all delivery stops have left the queue. Saving a
delivery refreshes and advances the displayed current stop automatically. Other
devices/sides still need Refresh; no background polling discards in-progress forms.
This API workspace does not yet expose the local prototype's same-day retry
scheduler or offline outbox; it is not a feature-parity production release.

## APIs reused and extended

- The supplied parser, persistent orders/corrections/history, customer links,
  verification/review, rider profiles/queues/assignments and delivery APIs are
  called directly, not replaced by fake responses.
- Admin creation no longer requires a merchant account. The legacy merchant_id
  column stores the administrative owner when omitted; explicit merchant clients
  remain compatible. No merchant side/account is created by the new starter.
- Validated parcel context adds item, sender, reference, day, physical custody,
  actual collections and resolution history to existing order metadata, protected
  by Order.version.
- Migration 0004 adds route aggregates without rewriting existing order tables.
  Route commands use version checks, transaction rollback and per-actor request
  IDs. Replaying a receipt does not count cash twice.
- New endpoints: GET /api/session; GET/POST /api/routes;
  POST /api/routes/{id}/actions; POST /api/orders/{id}/operations;
  POST /api/orders/{id}/prepare-assignment (versioned, admin-only, idempotent).
  The preparation form retains its request ID for an identical retry after a
  network error; changed payloads get a new ID. Never blindly retry with a newer
  version after a conflict. Advanced mark-ready-only and standalone route creation
  remain available when planning separately.
- The UI server has an exact file allowlist. Backend source, environment files,
  access JSON and databases are not served. Private responses are no-store.
  Customer credentials never inherit admin headers. The customer token is removed
  from the current page URL after loading; backend access logs redact link paths.

## Verify

```powershell
# From D:\Zero_Lag
npm test
npm run check

# From D:\Zero_Lag\lannpya-ai\backend
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-workspace
```

Use a dedicated disposable pytest base directory, never a real data directory.
Tests cover API journeys, roles, custody gates, money, returns, idempotency,
static-file exclusions and frontend handlers. DOM tests do not render CSS or
certify a real mobile browser.

API mode is online-only. Production login, PostgreSQL deployment/load tests and
browser/mobile verification remain needed. AI remains mock/disabled; map accuracy
is not independently verified. No public deployment, paid service, message or
real payment is triggered. The older merchant-centric handoff remains only for
legacy API consumers; this guide describes the new three-side workspace.

After updating this workflow, restart the local backend and hard-refresh api.html.
No migration, data reset or checkpoint overwrite is required. This refinement is
for the API-backed workspace; the separate index.html local prototype is unchanged.
