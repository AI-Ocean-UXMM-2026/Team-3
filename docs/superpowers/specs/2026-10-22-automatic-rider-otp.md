# Automatic rider offers and customer phone OTP

## User requirements

- Preserve the existing UI styling and page layouts. Add only controls and copy needed by the requested workflow.
- After the dispatcher reconfirms customer confirmation, assign automatically to a free rider.
- A rider must explicitly accept or decline before Delivered is available. A decline returns the parcel to automatic allocation, excluding that declining rider.
- After acceptance, retain existing dispatch, delivery-window, COD, return and cash-closeout behavior.
- Replace customer phone-last-four verification with a phone OTP. Customer details must stay inaccessible without a correct OTP.
- Prepare Twilio Verify and clearly labeled local demo OTPs, as explicitly selected by the user.
- Use subagent-driven development, with task reviews and a final review. Show changes and wait for user confirmation before any push. No push, merge, deployment or real SMS sends during implementation.

## Workflow decisions

Free means an operationally AVAILABLE rider with no active assignment or pending offer. An outstanding offer reserves that rider; simultaneous confirmations cannot reserve the same rider twice. Select deterministically among eligible riders and persist assignment state in the backend. Declining riders remain excluded for that order's allocation cycle. If nobody qualifies, keep a visible waiting-for-rider state; do not loop indefinitely or silently choose an unavailable rider. Retry when availability changes or an active delivery finishes. A dispatcher can explicitly retry a waiting order.

Dispatcher reconfirmation is an explicit versioned, idempotent operation after a recorded customer response and resolution of pending buyer reviews. Physical hub receipt, a reviewed location, delivery day, no incidents, and existing readiness rules remain required. Missing physical receipt must not be invented. Reconfirmation can persist a waiting/readiness result; when readiness becomes satisfied, allocation is automatic.

An offer is separate from departure. Acceptance records consent and unlocks the existing next steps; it does not claim delivery or bypass dispatcher departure, physical receipt, customer time windows or cash collection. Decline is allowed only on the current pending offer, is idempotent, removes its pre-departure route membership, and triggers one bounded reallocation attempt in a safe transaction. Stale or wrong-rider responses must fail without changing another rider's offer. Legacy assignments require a deliberate compatibility policy recorded in the task report, never an accidental bypass for new offers.

## Customer verification

The server chooses the destination from the order's stored phone; the client cannot supply a replacement recipient. Normalize Myanmar 09 numbers to +959 E.164. OTPs are six digits, expire within five minutes locally, have at most three incorrect attempts per challenge, and have a 60-second resend cooldown. Resend invalidates the previous local challenge. Expiry, revocation, phone changes, successful consumption and exhausted attempts invalidate the challenge. Enforce existing request rate limits. No code, raw phone, credentials or private link in logs.

Production uses Twilio Verify with server-only account SID/auth token/service SID and an explicit external-send opt-in. No configured provider means a clear unavailable error, never a phone-last-four fallback. Local/test demo mode can show the server-generated test code only through the protected loopback developer boundary, visibly marked simulation; the public production response must never include it. Codes are bound to their private link/challenge and checked server-side before issuing the existing limited buyer bearer session. The explicit browser prototype simulates the same request/verify state machine and labels its test code. No actual SMS calls during this task.

## Architecture and isolation

Baseline faad941 preserves earlier authorized auth/demo work. Implementation belongs on codex/automatic-rider-otp in the isolated lannpya-flow Git worktree. Existing mtt checkout and its running demo on port 8783 remain untouched.

Keep authoritative allocation and OTP state in FastAPI/SQLAlchemy. Extend existing versioned operations and receipt patterns, not browser-only authorization. Retain SQLite and PostgreSQL compatibility. Update migrations, startup database grant checks and the Supabase table-security script for new tables. Update both OpenAPI snapshots from the export script. Maintain the existing separate local BFF and Supabase bearer boundaries.

## Validation

Tests must prove deterministic selection, busy/offline exclusion, no double reservation, acceptance before completion, decline/reassignment/exhaustion, stale/wrong-rider/idempotent retries, and waiting-order recovery. OTP tests must prove correct/incorrect/expired/replayed/other-link codes, resends, rate limits, phone changes, revocation, provider failure, production no-provider behavior and no old last-four bypass. Browser flows must cover customer OTP -> confirmation -> dispatcher reconfirmation -> automatic offer -> decline to another rider -> acceptance -> existing delivery and COD closeout. Render desktop and mobile with unchanged design tokens and CSS.
