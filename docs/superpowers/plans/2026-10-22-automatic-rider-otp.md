# Automatic Rider Offers and Customer OTP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate rider allocation after dispatcher reconfirmation, require rider consent, and protect customer links with phone OTP.

**Architecture:** FastAPI/SQLAlchemy owns offer reservations, retries and OTP challenges. The existing vanilla frontend and simulation store adapt these operations without a redesign. Twilio Verify is prepared behind explicit configuration and mocked in tests.

**Tech Stack:** Python, FastAPI, SQLAlchemy/Alembic, httpx2, vanilla JavaScript, Node tests and Playwright.

**Spec:** docs/superpowers/specs/2026-10-22-automatic-rider-otp.md

## Global Constraints

- Preserve the existing UI styling and page layouts. Add only controls and copy needed by the requested workflow.
- After acceptance, retain existing dispatch, delivery-window, COD, return and cash-closeout behavior.
- Free means an operationally AVAILABLE rider with no active assignment or pending offer.
- Prepare Twilio Verify and clearly labeled local demo OTPs; no real SMS calls during implementation.
- No push, merge or deployment before explicit user approval of the final changes.
- Preserve prior auth/demo work from baseline faad941. Work only in lannpya-flow, branch codex/automatic-rider-otp.
- Do not dispatch subagents from worker/reviewer tasks. The controller owns all review seats.

## Review Focus

- Concurrent confirmations and cross-order lock ordering must not double-book or deadlock a rider.
- A stale decline or completion request must not alter a replacement offer or bypass consent.
- All-riders-busy/declined must terminate allocation and retain a recoverable waiting order.
- An OTP resend, link revocation or phone change must invalidate previous proof, including concurrent requests.
- A missing or failing SMS provider must never reveal codes publicly or fall back to phone-last-four.

## Task 1: Authoritative automatic assignment and rider offers

**Files:** backend/app/services/automatic_assignment.py (new), backend/app/services/riders.py, backend/app/services/workflow.py, backend/app/api/workflow.py, backend/app/schemas/riders.py, backend/app/db/rider_models.py and a new Alembic migration; focused backend tests. Touch buyer review integration only where required. No frontend edits.

**Interfaces:**
- Produce a versioned idempotent dispatcher operation `POST /api/orders/{order_id}/auto-assignment` with request_id, expected_version, acknowledge_unverified_location and optional receive_at_hub. Do not require client rider_id or route_id.
- Return order, allocation status (ASSIGNED, WAITING_FOR_RIDER or WAITING_FOR_READINESS), optional assignment/route and a readable reason. Persist reconfirmation and waiting state, not only the response.
- Produce rider offer response actions ACCEPT and DECLINE using existing authenticated rider action routes and request receipts; include current offer identity/version so stale replacement actions cannot apply.
- Extend queue projections with acceptance/offer identity and allocation state. Document exact final JSON fields in the report for Task 3.
- Keep existing manual/preparation APIs compatible for documented legacy callers, while all new automatic offers enforce explicit consent on START, DELIVERED and route departure.

**Behavior:**
- Reconfirm only after a real recorded customer response and required dispatcher review; retain readiness gates and physical receipt.
- Reserve AVAILABLE/zero-active riders deterministically with database-safe locking. Avoid order/profile lock inversions across availability-drain hooks.
- Decline persists exclusion for the current order/cycle, releases pre-departure membership, and allocates to another free rider. No free rider retains a bounded, visible wait state.
- Drain eligible waiting work on availability or delivery completion, safely outside conflicting transaction lock scopes where necessary. Retry rechecks customer/readiness state.
- Explicit ACCEPT records consent; the existing dispatcher departure/delivery/COD flow continues. No delivered action before acceptance.
- Migrate existing records with a deliberate compatibility default and test it. New offers never inherit legacy auto-acceptance.

- [ ] Write failing focused lifecycle, role, idempotency and concurrency tests.
- [ ] Implement the minimal schema/service/API changes.
- [ ] Run focused tests, then relevant rider/workflow/buyer regression suites once; update affected fixtures where behavior intentionally changes.
- [ ] Self-review, commit only this task's changes using command-scoped Codex identity, and write task report with exact test commands/output, interfaces and risks.

## Task 2: Link-bound phone OTP and Twilio Verify adapter

**Files:** backend/app/services/buyer_otp.py (new), backend/app/services/buyer_confirmation.py, backend/app/api/buyer_confirmation.py, backend/app/schemas/buyer.py, backend/app/db/buyer_models.py, backend/app/core/config.py, backend/.env.example, new Alembic migration after Task 1; backend/tools/backend_test_dashboard/runtime.py and server.py; backend/app/core/database_security.py, backend/scripts/secure_supabase_tables.sql; focused OTP and affected API tests. No frontend edits.

**Interfaces:**
- Produce `POST /api/confirm/{token}/otp` to start/resend verification to the stored phone, returning only safe challenge state, masked destination and cooldown/expiry.
- `POST /api/confirm/{token}/verify` accepts the OTP proof and issues the existing BuyerAuthorizationResult only after verification. Remove network-accessible last_four verification; old private test helpers may exist only if unreachable from public endpoints and clearly separated.
- Expose demo challenge codes only through the protected loopback BFF, with explicit demo/test labeling. Report exact BFF and public response contracts for Task 3.
- Use existing session authorization for details/location/response after OTP verification.

**Behavior:**
- Six-digit cryptographic demo codes; five-minute local expiry; maximum three wrong attempts; 60-second resend cooldown; resends replace prior proof; one-time consumption.
- Bind to link, phone, generation and expiry. Reject other-link, stale, replayed, revoked/changed-phone challenges. Preserve existing public request rate limits and bounded lockouts.
- Prepare Twilio Verify POST Verifications (Channel=sms) and VerificationCheck against the fixed official verify.twilio.com origin using httpx2, TLS, short timeout, no redirects and server-only credentials. Gate external sends explicitly; tests use transports/mocks, never live calls.
- Use documented +95 normalization. Production cannot use demo mode or leak test codes and fails closed without configuration.
- Preserve safe provider errors with no secrets/phones/URLs/code logging. Add new tables to database browser-access protections.
- Update affected backend HTTP fixtures to obtain a local OTP rather than accepting legacy last-four proof. Maintain the intent of existing session/rate-limit/revocation tests.

- [ ] Write failing security tests for success, error, resend, expiry, replay, wrong-link, revocation, phone change, outage and configuration.
- [ ] Implement challenges, provider adapter, endpoints and local bridge support.
- [ ] Run focused tests and affected buyer/contract/dashboard regressions once; regenerate both OpenAPI snapshots with the existing exporter.
- [ ] Self-review, commit task files only, and report exact interfaces, settings and verification evidence.

## Task 3: Existing frontend, prototype and end-to-end flow

**Files:** frontend/js/functional-app.js, frontend/js/live-store.mjs, frontend/js/api-model.mjs, frontend/js/local-api.mjs, frontend/js/backend-client.mjs, frontend/js/workflow-domain.js and focused helper modules if justified; frontend tests; browser fixtures/tests; tools/backend-test-dashboard and docs/examples callers if their contracts require updates; docs/AUTOMATIC_RIDER_OTP.md and Codex Context.md. Update script test lists only when necessary. No CSS redesign or new page layout.

**Interfaces:** consume Task 1 and Task 2 contracts exactly from their reports. Work after both task reviews are clean.

**Behavior:**
- Existing dispatcher reconfirm/review controls automatically request server allocation once required review is resolved; remove rider-selection requirement from this path. Preserve explicit hub-receipt evidence and location acknowledgement. Show allocation/waiting status in existing notices.
- Put ACCEPT and DECLINE in the existing rider action area for pending offers. Hide/disable Delivered until accepted; never implement server consent in browser storage alone. A decline refreshes dispatcher/rider state and a replacement offer appears without manual selection.
- Accepted parcels retain existing route departure, delivery-window, COD, return and cash-closeout controls. Show a waiting-for-departure notice when appropriate.
- Customer link verification retains its existing form styling but requests/sends OTP, offers resend with cooldown, and verifies six digits. Remove all phone-last-four copy/paths from the active UI; do not reveal full phone data pre-verification.
- Clearly label local simulator OTP preview; production never displays an OTP. Explicit browser prototype implements equivalent request/verify/expiry/retry/accept/decline/allocation behavior, with a simulated clock/test code, not production authentication.
- Ensure any path that reassigns or completes refreshes relevant views and does not fabricate success on failure. Preserve drafts on failed OTP/confirmation/API calls.
- Update old tests and demo tools to exercise the intended OTP flow instead of bypassing it. Keep credential boundaries and existing auth tests intact.

- [ ] Write failing frontend and browser tests for OTP -> customer confirmation -> dispatcher reconfirmation -> auto-offer -> decline/reassign -> accept -> existing completion/COD; add no-free and stale response cases.
- [ ] Implement UI/adapter/domain changes using current components and CSS.
- [ ] Run frontend suite, build, targeted full-flow browsers, and relevant backend regressions. Capture desktop/mobile evidence outside the repo. No real SMS.
- [ ] Document setup, demo procedure, exact changed behavior, tests and missing live credentials; self-review, commit task files and write the task report.

## Final validation and handoff

- [ ] Dispatch a broad whole-change review against faad941, including parked/minor ledger findings. One fix wave and a scoped re-review if needed.
- [ ] Ensure all implementation/test/build processes finish, update context and prepare a readable change summary and unresolved live-SMS limits.
- [ ] Ask for confirmation before any push. Do not push during this plan.
