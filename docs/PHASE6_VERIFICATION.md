# Phase 6 verification: Rider Copilot

Implemented against the existing backend on 2026-10-21, Windows/Python 3.14.7. Backend
only; no frontend changes, external messaging, paid services, deployment or Git push.
The supplied prompt ended at Task 8's actor-information requirement; this implementation
covers every provided task, with verification and frontend documentation consistent with
the earlier phases.

## Audit

Reviewed the API contract, Phase 5 report, models/migrations, lifecycle, event schema and
local access mechanisms. Before changes, **359 tests passed in 28.71 seconds**. Existing
parsing, provider-independent mock AI, buyer verification and review, transaction sessions,
confidence rules, actor binding and order ownership were reused.

## Features and schema

Alembic **0003_rider_copilot** creates:

| Table | Purpose |
| --- | --- |
| rider_profiles | User UUID PK/FK, AVAILABLE/ON_BREAK/OFFLINE, optional normalized phone, optimistic version, queue version, UTC created/updated times |
| delivery_assignments | UUID, order/rider/dispatcher FKs, ACTIVE/UNASSIGNED/COMPLETED/FAILED/CANCELLED, stop sequence, private failure reason/note, COD assertion, assigned/updated/ended times |
| rider_action_receipts | Actor/rider/order/assignment FKs, request UUID, payload hash, original result, creation time; unique actor/request key |

User name/email/role are reused, not copied into another identity table. Existing Rider
users get OFFLINE profiles. Omitted email uses a reserved internal identifier for the
existing required User.email constraint; rider responses return null contact email.
No rider identity/contact is invented for real orders.

A SQLite/PostgreSQL partial unique index prevents multiple active assignments per order.
Checks constrain statuses, sequences, versions and active/ended consistency. UUIDs,
JSON/JSONB and UTC timestamps remain PostgreSQL-compatible. Tests verify metadata drift,
offline PostgreSQL DDL, old-record preservation, and backfill of existing Rider profiles.
Initial/updated migrations were applied to isolated SQLite databases and the normal local
development database. `.env` was preserved. Live PostgreSQL remains unverified.

Operations lock order then rider profile. Assignment, capacity check, order transition,
queue version, event and action receipt commit atomically; failures roll back. Actor/request
idempotency returns the original acknowledgment, including after delivery completion.
Concurrent duplicate completion cannot create duplicate events. Earlier assignment rows
are retained through reassignment and retry.

Queue is a bounded full snapshot, ordered deterministically by active delivery status,
confirmed delivery-window start, dispatcher sequence, assignment time, order creation and
UUIDs. A rider-specific digest covers the full snapshot and queue generation; removals,
completion and reordering are visible through cursor changes. Polling is REST-based,
not WebSocket push, route optimization or an immutable change-event feed.

Navigation is offered only for explicitly accepted buyer-coordinate provenance. URLs
contain encoded coordinates and driving mode only. No maps request, tracking, phone or
notes are sent by the backend. Reference:
[Google Maps URL documentation](https://developers.google.com/maps/documentation/urls/get-started).
Buyer confirmation does not prove geospatial accuracy or grant GREEN. No trusted boundary
dataset was added; the existing default remains unverified.

## APIs

- POST /api/riders; GET /api/riders; GET/PATCH /api/riders/{id}.
- GET /api/riders/{id}/queue with optional snapshot cursor.
- POST /api/orders/{id}/assign and /unassign.
- PATCH /api/orders/{id}/assignment for stop sequence.
- GET /api/orders/{id}/assignments for paginated dispatcher history.
- PATCH /api/riders/{id}/deliveries/{order_id}/status: START, DELIVERED, FAILED.

All require the existing local token, actual loopback peer and configured server actor.
Dispatcher/Admin can manage operational records. Riders can read only their own profile/
queue and act only on their active assignments; merchants/buyer credentials cannot enter
these routes. Rider actors remain excluded from private order-management and buyer-audit
APIs. Production fails closed. Availability may change while on road, but an unavailable
rider cannot receive/start new work; completion/failure can still be recorded.

Events add RIDER_ASSIGNED, RIDER_UNASSIGNED, RIDER_SEQUENCE_CHANGED, DELIVERY_STARTED,
DELIVERY_COMPLETED and DELIVERY_FAILED. New rider events include actor ID/role, rider and
assignment IDs, previous/new status and applicable reason/COD flags. Private failure notes
remain on protected assignment records. Existing buyer approvals preserve their actor ID.

## Integration choices and compatibility

Existing parsing and buyer contracts are unchanged. Earlier status-only ASSIGNED records
remain bookkeeping; migration never guesses a rider. Real work must use POST /assign so
the rider receives an actual queue entry. For a real assignment, generic operational status
updates return USE_RIDER_DELIVERY_ACTION; generic return-to-ready/cancellation atomically
closes the assignment and removes it from the queue.

Positive COD requires explicit cod_collected:true before completion by default, including
the older generic status endpoint. Null COD is not treated as zero; set explicit zero for
prepaid orders. The older status body gains a strict optional collection boolean applicable
only to DELIVERED. This is an intentional new completion precondition for earlier clients,
not a payment integration. Legacy regression delivery requests were updated to supply the
required assertion; no regression cases were removed. Migration expectations were updated
to the new table set/head. An explicit policy flag can disable collection confirmation,
without inventing a true collection value.

Buyer edits/approvals retain Phase 5's pre-dispatch restrictions. Late pre-start changes
require unassign -> NEEDS_REVIEW -> buyer request/review -> confirmation/readiness -> reassign.
Poll sees removal and later approved replacement. On-road edits are not silently applied.

## Verification results

- Full suite: **405 passed in 44.42 seconds**: 359 previous cases plus 46 new rider cases.
- Ruff lint passed; formatting check: **68 files already formatted**.
- Local migration current: **0003_rider_copilot (head)**.
- Editable package updated to **0.6.0**; `pip check` reported no broken requirements.
- Final real HTTP delivery demonstration repeated successfully. Phase 5 buyer smoke also
  passed (1 order / 2 requests / 9 events), and the Phase 4 lifecycle passed (2 orders /
  10 events). Health/parsing smoke checks passed in hybrid and rules modes (200 valid,
  422 empty input). OpenAPI includes the rider and assignment routes; the 22-case Phase 6
  sample JSON was validated and all capabilities were redacted by the smoke script.
- New tests cover rider creation/contact validation, ownership/role/public/production
  denial, availability, pagination, assignment history, capacity/unique-index concurrency,
  stable ordering, confirmed/unconfirmed navigation, cursor removal/change detection,
  sequence edits, COD and legacy COD protection, failure notes, idempotent completion,
  concurrent completion, rollback, migration preservation/backfill, and reopened persistence.
- A buyer correction/reassignment test confirms only dispatcher-approved coordinates and
  Burmese instructions reach the next queue; buyer edits after assignment remain rejected.
- An initial test setup omitted the existing AMBER readiness acknowledgement; it was
  corrected to satisfy the existing rule. Two subsequently added tests needed imports
  restored after lint removed them while unused. These test failures were fixed.

The real HTTP demonstration `scripts/smoke_delivery.py` creates an isolated SQLite database,
separate merchant/dispatcher/rider identities and three loopback Uvicorn instances:

1. Merchant creates a raw Burmese order (201), parser extracts actual phone/township/COD.
2. Merchant requests review and generates buyer link; public card has no private address.
3. Buyer verifies, proposes an initial pin; dispatcher explicitly approves it.
4. Buyer records AVAILABLE with Burmese instructions; dispatcher acknowledges AMBER readiness.
5. Dispatcher creates rider and assignment (201); rider queue exposes the approved data
   and encoded navigation URL, unchanged polling returns its stable cursor.
6. Rider cannot access dispatcher order APIs (403); anonymous queue is rejected (401).
7. Rider starts delivery; completion without required COD assertion is rejected (409).
8. Explicit collection completes delivery; identical retry creates no duplicate event.
9. Queue reports removal and the delivered buyer card is minimal view-only for 24 hours.

After stopping all three servers and reopening storage: **1 delivered order, 1 rider profile,
1 completed assignment, 2 action receipts, 2 buyer requests and 11 events** persisted.
COD collection was explicitly true; confidence remained **AMBER**. All capabilities in
[PHASE6_SAMPLE_RESPONSES.json](PHASE6_SAMPLE_RESPONSES.json) are redacted. Samples use
synthetic test values only, not generated application coordinates or contact identities.

See [API_CONTRACT.md](API_CONTRACT.md) for every request, response, access assumption,
completion precondition, polling example and error code. See backend README for launch
and verification commands; normal launch remains loopback-only with no access logging.

## Boundaries and next decisions

This is a working local hackathon foundation, not production authentication or multi-tenant
authorization. Each instance uses one server-configured actor; the HTTP demo uses separate
isolated instances instead of adding an insecure client-selected identity/login mechanism.
Real customer/rider data must not be exposed through public deployment, tunnels or forwarding
proxies under this mechanism. No frontend files or normal local data records were replaced.

No live PostgreSQL verification, trusted geospatial boundaries, real AI, messaging, payment
processing, geographic route optimization, GPS tracking, WebSockets or spatial memory was
implemented. Queue ordering is operational priority only. A confirmed pin is a buyer/operator
assertion, and COD collection is an actor assertion, not proof of delivery/payment.

Next decisions: production tenant-aware user/rider authorization, disposable PostgreSQL
integration tests, courier COD/proof-of-delivery policy, trusted location data and the
frontends for dispatcher/buyer/rider flows. Retention, encrypted storage, audit access,
larger fleet pagination and production concurrency/edge limits need review before launch.
No decision blocks local frontend integration with the documented APIs.
