# Buyer delivery window, edit limit and reminder SMS

The requested day and selected delivery window are the ETA. Branded buyer submissions require a concrete window, including for “At home”; “Any time” cannot establish a safe cutoff. The buyer may make three materially changed submissions after the initial confirmation. The edit deadline is one hour before the selected window starts, using Asia/Yangon. An accepted reschedule updates the deadline only when submitted before the current deadline.

The first address confirmation is exempt from the edit cutoff and advance-notice rule, including for a newly created draft. It may be saved after the cutoff on the selected delivery day; subsequent edits are then closed. Past calendar delivery dates, cancelled/delivered orders, invalid or locked links and unverified sessions remain disallowed. An evening confirmation on an earlier date does not close edits for a future delivery day.

PATCH /api/confirm/{token}/request stores the buyer's pin, availability, requested window and instructions in one transaction. Existing /location and /response endpoints remain available with the same order-scoped edit policy. OTP/link/session state does not own the edit count. Authenticated details continue to return the current order and an editing_policy projection after edits close.

Location and availability retain separate dispatcher review records: approving the pin does not approve an unsupported reschedule. A newer complete submission supersedes older pending submissions without removing their audit history or refunding edits. Assigned or departed orders retain their rider, route, stage and custody; material amendments require review before delivery can proceed. Reviewing a proposal submitted before the cutoff is still allowed afterward.

The 0008 Alembic migration adds the order-scoped policy, idempotency receipts and reminder outbox. Apply the normal migration path, then run backend/scripts/secure_supabase_tables.sql with the database owner before enabling Supabase browser roles. Startup checks reject browser grants on these tables.

## SMS configuration

Custom delivery reminders use Twilio Messaging Messages, separate from Twilio Verify OTP. See [Twilio's Message resource](https://www.twilio.com/docs/messaging/api/message-resource). Server-side settings:

- LANNPYA_BUYER_REMINDER_EXTERNAL_SENDS_ENABLED=false by default.
- LANNPYA_BUYER_REMINDER_LEAD_MINUTES=30 schedules the warning 30 minutes before the cutoff (90 minutes before the window starts).
- To enable production sending, configure the existing server-only Twilio account SID and auth token, plus exactly one Messaging Service SID or sender.

The worker sends at most one reminder per order, only on the selected Yangon delivery day and before the edit deadline. It skips closed, exhausted, terminal, expired, revoked and changed-phone orders. It names the window, exact cutoff, three-edit maximum, remaining edits, and tells the buyer to use the link already shared by the shop. No raw link token is stored in the outbox.

A claim is committed before contacting Twilio. If a process exits or a provider response is uncertain, the outbox becomes UNKNOWN; it is not automatically retried. Local and test runs never contact Twilio and record SIMULATION. With production sending disabled, the outbox records DISABLED. ACCEPTED means Twilio accepted the request, not that the handset received it.
