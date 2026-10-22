# Task 1 report: authoritative automatic assignment and rider offers

Branch: `codex/automatic-rider-otp`
Baseline: `86ef31a4d98b496f552c9e1350a42a07389d7079`
Commit: see the task completion note for the exact hash.

## Result

Implemented durable, versioned dispatcher reconfirmation and automatic rider offers. Offers reserve only AVAILABLE riders without an active assignment. The coordinator row serializes reservation, decline, manual assignment, route changes, and workflow operations; candidate ordering is rider UUID order. New allocations and offer state persist in `automatic_allocations` and `delivery_assignments`. Declines end the assignment, detach the parcel from its pre-departure route, exclude that rider for the cycle, and make one replacement attempt. Exhaustion and readiness failures remain visible and bounded. Availability changes, RECEIVE, RESOLVE_INCIDENT, delivery completion/failure, startup, and a 30-second recovery worker drain waiting work; each retry checks current buyer authorization and the saved customer-material hash.

Accept is required before rider START/DELIVERED and dispatcher route departure. Acceptance does not dispatch the route. Legacy/manual assignments use the explicit compatibility default `ACCEPTED`, while automatic offers write `PENDING`. Existing delivery and COD actions remain on the existing rider workflow.

The migration is `0006_automatic_assignment`. SQLite uses additive column changes to preserve foreign-key references and existing action receipts. PostgreSQL gets check constraints and defaults. The migration test upgrades an existing 0005 database with an active legacy assignment and receipt, and checks that both survive with legacy acceptance. New tables protected from browser roles are `allocation_coordinator`, `automatic_allocations`, and `allocation_receipts`; they are included in both `app/core/database_security.py` and `scripts/secure_supabase_tables.sql`.

## JSON contracts for Task 3

Request `POST /api/orders/{order_id}/auto-assignment`:

```json
{
  "request_id": "UUID",
  "expected_version": 1,
  "acknowledge_unverified_location": true,
  "receive_at_hub": false
}
```

`receive_at_hub` is optional and defaults to false. It records receipt only when explicitly true. Response has exactly these top-level keys: `order`, `allocation_status`, `reason`, `assignment`, `route`. `allocation_status` is `ASSIGNED`, `WAITING_FOR_RIDER`, or `WAITING_FOR_READINESS` for this operation. `order` is the existing `OrderResponse` object with keys `id`, `merchant_id`, `customer_name`, `customer_phone`, `original_message`, `normalized_message`, `township`, `street`, `landmark`, `building`, `floor`, `unit`, `building_floor_unit`, `latitude`, `longitude`, `cod_amount`, `delivery_instructions`, `delivery_time_window`, `confidence_level`, `confidence_reasons`, `parsing_mode`, `ai_availability_status`, `field_sources`, `parsing_metadata`, `manual_review_required`, `status`, `version`, `created_at`, `updated_at`. `assignment` is null while waiting; otherwise it has `id`, `order_id`, `rider_id`, `dispatcher_id`, `status`, `response_status`, `offer_version`, `allocation_cycle`, `responded_at`, `stop_sequence`, `failure_reason`, `failure_note`, `cod_collected`, `assigned_at`, `updated_at`, `ended_at`. `route` is null when no current route exists; otherwise it has `id`, `rider_id`, `version`, route data (`day`, `state`, `order_ids`, `handover`, `events`), `items`, `blockers`, and `recorded_total`.

Offer response uses the existing authenticated rider status route `PATCH /api/riders/{rider_id}/deliveries/{order_id}/status`, with `action: "ACCEPT" | "DECLINE"`, `request_id`, `expected_version`, `assignment_id`, and `offer_version`. A successful response has `request_id`, `assignment_id`, `order_id`, `rider_id`, `status`, `assignment_status`, `order_version`, `cod_collected`, `failure_reason`, `updated_at`, `response_status`, `offer_version`, `allocation_status`, `outcome`, `replacement_assignment`, `replacement_route`, and `reason`. On decline `outcome` is `REASSIGNED` or the resulting waiting state; replacement fields are null when there is no replacement. A matching retry returns the stored receipt before checking current offer state. Reusing a request ID with different data conflicts. Stale offer identity/version and wrong rider fail without changing an offer.

Queue entries retain existing fields and add `response_status`, `offer_version`, `allocation_cycle`, and `allocation_status`; the queue already includes `assignment_id` and `order_id`.

## Validation

The predecessor's recorded RED run had 6 failures because the automatic endpoint did not exist (9.31s). The first GREEN run completed after implementation:

```text
python -m pytest tests/test_automatic_assignment.py -q --basetemp=.tmp/task1-luna-focused-20261022
17 passed, 3 warnings in 27.20s
```

Regression command:

```text
python -m pytest tests/test_riders.py tests/test_three_role_workflow.py tests/test_buyer_confirmation.py tests/test_order_management.py tests/test_database_compatibility.py tests/test_routing.py -q --basetemp=.tmp/task1-luna-regressions-20261022
289 passed, 1 skipped, 3 warnings in 208.73s
```

Both runs used `C:\Users\minth\Downloads\Ai ocean\lannpya-mtt\backend\.venv\Scripts\python.exe` from the `lannpya-flow/backend` directory. The three warnings are environment-baseline deprecations from native SWIG bindings (`SwigPyPacked`, `SwigPyObject`, `swigvarlink`); they are external to the changed Task 1 code and appeared in both runs. No warning filters were added. One existing regression case was skipped; no failures occurred. `git diff --check` passed.

## Self-review and limits

The SQLite focused and regression suites exercise migration preservation, idempotent requests, stale and wrong-rider offers, concurrent reconfirmation and response races, rider availability exclusion, pending-offer reservation, consent before delivery/departure, decline/reassignment/exhaustion, customer edits/revocation/review rechecks, and startup/availability/completion recovery. PostgreSQL migration SQL and SQLAlchemy model DDL are covered by existing compatibility tests, but no live PostgreSQL concurrency run was available. Recovery is bounded to 50 waiting allocations per drain and runs every 30 seconds; later eligible work is picked up on the next drain. Existing manual assignment compatibility deliberately keeps historical acceptance semantics.

