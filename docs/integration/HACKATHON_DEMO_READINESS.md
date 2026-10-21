# Hackathon demo readiness

The backend can support a credible local scripted workflow, but the frontend application
is not in this repository and its split-screen/pitch automation has not been executed.
The guide describes visuals and simulated actions that are not API capabilities.

## Supported with real backend requests

- Public Burmese/Myanglish parse with deterministic fields, evidence, warnings and triage.
- Protected order creation, retrieval, corrections and lifecycle updates in local loopback mode.
- Protected confirmation-link generation and public minimal card/last-four verification.
- Buyer authorized location and availability/time/instruction request, including pending review.
- Dispatcher read/review/approve/reject of buyer requests.
- Rider assignment and scoped queue retrieval, optional navigation URL when coordinates are available.
- Rider start/fail/deliver lifecycle and explicit COD collection assertion.
- Persistent events and isolated local SQLite data. Existing `scripts/demo_mvp.py` exercises
  68 HTTP cases using fictional records and private ignored credentials.

## Guide features that are presentation-only or absent

| Guide item | Actual state |
| --- | --- |
| AI confidence animation 68% -> 99% | No confidence percentage; backend categories are deterministic and default GREEN is disabled |
| Approximate AI map location / automatic 500m ring | No geocoder/trusted origin/boundary data; no enforceable arbitrary ring |
| Buyer map selection | Backend accepts a proposal; initial pin requires review and isn't a trusted point |
| Buyer gate photo selection | No upload/storage/schema or endpoint; may be a clearly labelled local fixture illustration |
| Masked customer calling | No carrier/telephony API; an animation cannot claim a call happened |
| Route polyline/hub/rider live map | No route optimizer, fleet GPS, live rider location or route API |
| Automatic instant dispatcher/rider update | REST polling only; suggested five-second rider snapshot polling |
| COD cash stamp/remittance to merchant | Rider can attest collection at completion; no payment, cash reconciliation or remittance ledger |
| Frontend static fallback when API is down | Not inspected/verified; must be explicit `DEMO_SIMULATION`, never a silent live fallback |
| 30-second synchronized pitch | Not end-to-end verified; can be built as presentation simulation with visible demo badge |

## Safe realistic sequence

1. Start `backend/scripts/demo_mvp.py --serve` and use its runtime-generated local role
   instances/private directory; never show or serve `private_access.json`.
2. In visible DEMO_SIMULATION mode, show the scripted Messenger text as fictional. To show
   a real backend operation, parse it and visibly label results “local backend / rules-first
   + mock AI status”; do not display invented provider extraction or numerical confidence.
3. Save a fictional order and show its actual `DRAFT`/review state, then transition it using
   the actual returned version. Generate a real short-lived buyer link through local dispatcher.
4. Open buyer card on the local UI, perform the last-four check using only the fixture data
   in the isolated demo, and submit an initial pin. Show “pending dispatcher review.”
5. Approve through the dispatcher API; show that the canonical queue changes on next poll.
   Keep buyer-confirmed and independently verified labels separate.
6. Assign and poll the rider queue. Use an actual returned navigation URL only if ready; the
   fixture may be (0,0) and explicitly must not be presented as a Myanmar destination.
7. Start delivery. Confirm COD explicitly, complete, and show the persisted event/receipt.
   This records an assertion only, not actual remittance/payment.

The demo script creates independent demo data and does not modify the normal local database
or `.env`. Production APIs, online multi-user auth, messaging, caller masking, real geospatial
verification and live GPS are not part of this demonstration. No public deployment or tunnel.
