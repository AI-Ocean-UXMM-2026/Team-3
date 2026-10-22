# Task 2 report: customer phone OTP

Implemented on `codex/automatic-rider-otp` in the isolated `lannpya-flow` worktree. No frontend files were changed.

## Behavior and interfaces

`POST /api/confirm/{token}/otp` accepts an empty JSON object and chooses the saved customer phone server-side. A success response is:

```json
{
  "challenge_id": "<uuid>",
  "destination_masked": "••••4567",
  "expires_at": "<ISO-8601 timestamp>",
  "resend_after": "<ISO-8601 timestamp>",
  "mode": "DEMO"
}
```

`mode` is `DEMO` locally or `SMS` through Twilio. The public response never contains the code. `POST /api/confirm/{token}/verify` accepts `{"code":"123456"}` with six ASCII digits and returns the existing `BuyerAuthorizationResult` (`access_token`, `token_type: "Bearer"`, `expires_at`) only after a successful check. Public `last_four` verification now returns 422.

The local BFF proxies OTP requests through `POST /dashboard/api`, for example:

```json
{
  "method": "POST",
  "path": "/api/confirm/@buyer/otp",
  "body": {},
  "buyer_handle": "<session-owned handle>"
}
```

Its response envelope retains `method`, `endpoint`, `status`, `duration_ms`, `ok`, and `data`; `data` is the public challenge response. After verification, the BFF keeps the bearer authorization server-side and returns `data: {"verified":true,"expires_at":"...","notice":"Buyer authorization held server-side, never returned to this browser."}`.

The protected local-only `GET /dashboard/buyer-otp?buyer_handle=<handle>` returns the active test proof as `{"simulation":true,"code":"123456","expires_at":"...","notice":"SIMULATION ONLY — enter this test code in the local buyer flow."}`. It checks the current dashboard owner's handle, and the code is unavailable after expiry, replacement, consumption, lockout, or revocation.

## Settings and lifecycle

Settings are `LANNPYA_BUYER_OTP_MODE` (`demo` or `twilio`), `LANNPYA_BUYER_OTP_EXTERNAL_SENDS_ENABLED` (default false), `LANNPYA_BUYER_TWILIO_ACCOUNT_SID`, `LANNPYA_BUYER_TWILIO_AUTH_TOKEN` (secret), and `LANNPYA_BUYER_TWILIO_VERIFY_SERVICE_SID`. Production configuration requires Twilio mode, explicit external-send opt-in, and all three credentials; it cannot run in demo mode.

Myanmar `09xxxxxxxxx`, `+959xxxxxxxxx`, and `959xxxxxxxxx` inputs normalize to `+959xxxxxxxxx`. Codes use a cryptographic six-digit generator, expire locally after five minutes, allow three wrong checks, and have a 60-second resend cooldown. Wrong attempts persist on the link across successful verification. Cooldown applies to pending or uncertain replacement attempts; a consumed proof does not prevent a fresh challenge. Both OTP endpoints consume the existing verification request budget (default 10 per minute).

Twilio Verify requests use the fixed `https://verify.twilio.com/v2` origin through `httpx2`, basic auth, a five-second timeout, no redirects, and no environment proxy. Sends use `To` and `Channel=sms`; checks use the stored `VerificationSid` and submitted code. Before a replacement send, stored provider SIDs for pending, expired, revoked, locked, or cancellation-failed challenges for the normalized phone are canceled. A cancellation failure returns a safe 503 and persists the cooldown; a retry after cooldown retries cancellation before sending. This covers Twilio's provider-side code reuse even when the local five-minute challenge has expired. Provider calls in tests are mocked; this task made no live SMS requests.

Migration `0007_buyer_otp` creates `buyer_otp_challenges`. The table is included in startup browser-grant checks and the Supabase RLS/revoke script. Both OpenAPI snapshots were regenerated with `backend/scripts/export_contract.py` by the preceding worker.

## Verification evidence

The preceding worker's handoff reported a baseline RED observation (`POST /otp` returned 404 and legacy last-four verification returned 200), a 73-pass buyer suite, then a broad regression run with 279 passed, 1 skipped, and 5 failures. The exact earlier commands and captured output were not preserved, so these are predecessor-reported results rather than independently reproduced evidence.

The five reported failures were `test_otp_expires_rejects_replay_and_is_link_bound`, `test_session_rotation_and_expiry`, `test_failed_budget_never_resets_after_success`, dashboard `test_expired_link_session_and_real_lockout`, and `test_verification_rate_limit_even_with_correct_digits`. The first four exposed cooldown being applied after a consumed/expired proof; cooldown now follows pending/uncertain challenge state. The rate-limit case depended on wall-clock minute rollover and now freezes the clock. The preceding worker reported that a focused six-test covering run passed after those changes.

This finishing pass added a mocked expired-Twilio-SID replacement regression and ran this focused set (unique temporary pytest base directory generated from a GUID):

```powershell
$runId = [guid]::NewGuid().ToString('N')
$baseTemp = Join-Path $env:TEMP "pytest-otp-luna-xhigh-$runId"
& 'C:/Users/minth/Downloads/Ai ocean/lannpya-mtt/backend/.venv/Scripts/python.exe' -m pytest -q --basetemp="$baseTemp" `
  tests/test_buyer_confirmation.py::test_myanmar_phone_normalization `
  tests/test_buyer_confirmation.py::test_otp_resend_cooldown_and_replacement `
  tests/test_buyer_confirmation.py::test_otp_expires_rejects_replay_and_is_link_bound `
  tests/test_buyer_confirmation.py::test_session_rotation_and_expiry `
  tests/test_buyer_confirmation.py::test_failed_budget_never_resets_after_success `
  tests/test_buyer_confirmation.py::test_verification_rate_limit_even_with_correct_digits `
  tests/test_buyer_confirmation.py::test_twilio_resend_cancels_and_checks_the_stored_sid `
  tests/test_buyer_confirmation.py::test_twilio_expired_challenge_is_cancelled_before_replacement `
  tests/test_buyer_confirmation.py::test_twilio_cancellation_failure_revokes_local_challenge_and_keeps_cooldown `
  tests/test_buyer_confirmation.py::test_twilio_outage_fails_closed_and_production_rejects_demo `
  tests/test_backend_dashboard.py::test_expired_link_session_and_real_lockout
```

Output: `13 passed, 3 warnings in 13.09s`. The warnings were dependency deprecations for `SwigPyPacked`, `SwigPyObject`, and `swigvarlink`. `git diff --check` also passed; Git only warned that the two OpenAPI snapshots may be normalized from CRLF to LF on a future write. No broad regression suite was rerun, in line with the task handoff; the final combined gate remains for after frontend work.

## Files changed

- OTP service and model: `backend/app/services/buyer_otp.py`, `backend/app/db/buyer_models.py`, `backend/migrations/versions/0007_buyer_otp.py`.
- Public API, schema, and settings: `backend/app/api/buyer_confirmation.py`, `backend/app/services/buyer_confirmation.py`, `backend/app/schemas/buyer.py`, `backend/app/core/config.py`, `backend/.env.example`.
- Local BFF and database protections: `backend/tools/backend_test_dashboard/runtime.py`, `backend/tools/backend_test_dashboard/server.py`, `backend/app/core/database_security.py`, `backend/scripts/secure_supabase_tables.sql`.
- Buyer, dashboard, fixture, migration, workflow, rider, and routing coverage: `backend/tests/test_buyer_confirmation.py`, `backend/tests/test_backend_dashboard.py`, `backend/tests/test_api_contract.py`, `backend/tests/test_database_compatibility.py`, `backend/tests/test_integrated_workspace.py`, `backend/tests/test_mtt_runtime.py`, `backend/tests/test_overnight_concurrency.py`, `backend/tests/test_riders.py`, `backend/tests/test_routing.py`, `backend/tests/test_three_role_workflow.py`.
- OpenAPI snapshots: `docs/OPENAPI.json`, `docs/integration/OPENAPI.json`.

## Review limits

The exact predecessor shell logs are unavailable, and only the focused OTP/dashboard set above was rerun. The browser prototype flow and combined rider/customer gate remain for the frontend task. No push, merge, deployment, or real SMS was performed.

## Review round 1 fixes (2026-10-23)

Addressed all three important findings from `task-2-review.md`:

- Order cancellation now revokes pending challenges and clears demo codes in the same transaction as confirmation-link revocation. New challenge expiry is capped at the parent link expiry. The local demo-code lookup now checks the live parent link, order state, revocation, lockout, phone binding, generation, and link expiry before returning a code.
- OTP start now acquires the existing allocation coordinator before `_link()` acquires the order lock, matching allocation's coordinator-then-order order. A focused TestClient regression wraps the real lock helpers and asserts the observed order. SQLite cannot reproduce PostgreSQL deadlocks; this integration assertion verifies the acquisition sequence used by both backends.
- Added an explicit same-phone cross-link test: code from link A is rejected at link B and remains usable at link A.

Covering tests were added in `backend/tests/test_buyer_confirmation.py` and `backend/tests/test_backend_dashboard.py`. Run from `backend/`; the focused command (unique temporary base directory generated from a GUID) was:

```powershell
$runId = [guid]::NewGuid().ToString('N')
$baseTemp = Join-Path $env:TEMP "pytest-otp-review1-$runId"
& 'C:/Users/minth/Downloads/Ai ocean/lannpya-mtt/backend/.venv/Scripts/python.exe' -m pytest -q --basetemp="$baseTemp" `
  tests/test_buyer_confirmation.py::test_otp_expiry_is_capped_by_confirmation_link `
  tests/test_buyer_confirmation.py::test_otp_start_locks_coordinator_before_order `
  tests/test_buyer_confirmation.py::test_otp_from_one_link_cannot_verify_another_link `
  tests/test_buyer_confirmation.py::test_otp_start_returns_only_safe_challenge_state `
  tests/test_buyer_confirmation.py::test_otp_is_invalid_after_link_revocation_or_phone_change `
  tests/test_buyer_confirmation.py::test_phone_change_revokes_pending_otp `
  tests/test_buyer_confirmation.py::test_concurrent_first_challenges_for_same_phone_serialize `
  tests/test_backend_dashboard.py::test_dashboard_demo_code_is_hidden_after_parent_link_invalidation `
  tests/test_backend_dashboard.py::test_buyer_handle_cannot_cross_browser_sessions `
  tests/test_backend_dashboard.py::test_expired_link_session_and_real_lockout
```

Output: `11 passed, 3 warnings in 14.59s`. The three warnings are the same third-party SWIG deprecations recorded above; they were not suppressed. No broad suite was run.
