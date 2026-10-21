# Isolated local MVP demo

Repeatable backend demonstration with fictional Burmese names and invented delivery text.
No public deployment, production login, real courier activity or frontend changes.

## Run modes (PowerShell, from backend)

```powershell
.\.venv\Scripts\python.exe scripts\demo_mvp.py
.\.venv\Scripts\python.exe scripts\demo_mvp.py --serve --frontend-origin http://localhost:5173
```

Default mode builds and verifies the demo, then stops its three loopback servers. --serve
also leaves them running for local integration until Ctrl+C. Other localhost/127.0.0.1
frontend ports are accepted; no wildcard/public origin is enabled. Production configuration
is refused, and `.env` is never changed.

Every run creates a new UUID directory under ignored backend/data/demo/, a fresh SQLite
database, migrations, fictional merchant/dispatcher users and an API-created rider. The
normal database cannot be selected or overwritten. No reset/delete is performed; earlier
demo runs and existing local data remain intact.

The printed directory contains:

- demo.sqlite3: fixtures and real API-generated history.
- private_access.json: matching local role base URLs, actor UUIDs, fresh development tokens
  and order IDs, plus a fresh buyer_link on the merchant backend for the candidate order.
  **Private: never serve, publish, commit or bundle this file.** Tokens are
  not printed. Windows permissions remain OS-managed; Git-ignore is not encryption.
- summary.json: verification outcome/counts.
- verification.json: actual responses with capabilities and complete fixture phone strings
  redacted; shareable copy is docs/PHASE7_SAMPLE_RESPONSES.json.

Each instance is bound to one actor; no client-selected identity or public login is added.
Only use its matching credential at runtime in local browser memory. A realistic remote
shared-browser/mobile demo requires proper authentication and secure deployment first.

## Scenarios and final states

| Fixture | Actual result | Interpretation |
| --- | --- | --- |
| green_candidate_unverified | NEEDS_REVIEW / AMBER; fresh buyer link | Complete-looking candidate; trusted data absent, GREEN disabled |
| amber_needs_buyer | ASSIGNED / AMBER; live queue stop | Sparse location needs confirmation; dispatcher explicitly acknowledges unverified location |
| red_missing_contact | DRAFT / RED | Missing phone/unknown township; unsuitable for dispatch |
| cod_delivery | DELIVERED / AMBER | Buyer pin reviewed, availability recorded, rider explicitly asserts COD collection |
| rescheduling_and_failure | FAILED / AMBER | Unsupported schedule reviewed/rejected, then a separate prepaid attempt fails |

Role names carry Burmese demo/fake labels. Emails use reserved .invalid domains or absent
rider contact. No real customer records, names, phones, addresses or credentials are
imported. A constructed format-valid phone fixture is necessary for validation/last-four
verification. It is **not claimed to be reserved or proven unassigned**: never contact,
look up, publish or copy it into real operations. Complete digits are redacted in shared
samples. No SMS/calls/messaging integration exists or is invoked.
The constructed fixture uses last-four `0000` for this isolated demo only; the real buyer
UI must ask for the recipient's input and never default or auto-submit guesses.

The deliberate (0,0) test pin at Null Island is **not a Myanmar customer location**. It
exercises the initial-pin/manual-review protocol without claiming a home address. Approval
is labelled demo-only, not township/geospatial verification. No reference anchor or trusted
boundary resolver is seeded. Never treat the synthetic navigation link as a real destination.

Unicode/COD parsing is actual deterministic code. The configured AI adapter is mock; some
inputs return not_requested when no minimal AI payload is available. No successful real
AI extraction, numeric confidence, geocoding or GREEN proof is manufactured.

## Actual checks

Real loopback HTTP health; accepted/rejected OPTIONS; Unicode parsing; order creation,
retrieval and corrections; links/card/verification/details; pin request; approval/rejection;
availability; rescheduling review without silent plan changes; rider assignment, queue,
start, completion and failure; COD guard; idempotent retry; polling removal; unauthorized
access; history; and reopened database persistence.

Successful setup: 5 orders, 3 buyer requests, 3 assignments, 4 action receipts, 32 events,
3 links and 68 recorded HTTP cases, plus individual startup/preflight assertions. One
assigned stop remains for --serve testing. No actual browser/mobile UI is present or
verified; HTTP CORS verification is not a browser UX test. See FRONTEND_HANDOFF.md.
