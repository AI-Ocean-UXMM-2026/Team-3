# Automatic rider offers and buyer OTP

The existing dispatcher, buyer and rider screens now follow the backend offer and OTP
contracts. The current layout and CSS remain in place. Local simulation does not send SMS,
use external credentials or grant a rider consent in browser storage.

## Run the local workspace

From the repository root, start the loopback-only workspace:

```powershell
npm.cmd start -- --port 8781 --state automatic-rider-otp
```

Open `http://127.0.0.1:8781/api.html` for the API-backed local workspace. This local
developer mode uses its isolated state name above. The `/prototype.html` screen is a
separate browser-only simulation and does not write to the backend.

## Buyer confirmation

1. Create or open an order in the API workspace and generate its buyer link.
2. Open the link. The unverified card does not include the customer's full phone number
   or the test code.
3. Choose **Request verification code**. The API sends a six-digit OTP to the saved phone.
   A local test workspace labels its protected code preview **SIMULATION ONLY**; this is
   the only place the local code is shown. No SMS is sent by the simulation.
4. Enter the six ASCII digits. Resend is disabled until the server-provided cooldown ends.
   A successful check opens the existing location and availability forms.
5. Submit location or a customer response. Requests that need review remain pending until
   a dispatcher approves or rejects them.

The API-backed client calls `POST /api/confirm/{token}/otp` with `{}` and verifies through
`POST /api/confirm/{token}/verify` with `{ "code": "123456" }` (the example value is
illustrative). Production code delivery and test-code preview are server-controlled. The
browser never submits phone-last-four as verification and never receives a production OTP.

The standalone `/prototype.html` simulation uses a local test code (`123456`) only after
the request action. Its simulated clock applies expiry, resend cooldown and failed-attempt
limits. Its auto-allocation chooses a free simulated rider, creates a pending offer, and
requires explicit accept or decline. Decline excludes that rider for replacement;
acceptance starts the delivery and route automatically.

## Dispatcher and rider workflow

After customer reviews are resolved and the order is ready, the dispatcher reconfirms in
the existing order panel. The form retains the physical hub-receipt evidence and location
accuracy acknowledgement. The server allocates to a free `AVAILABLE` rider automatically;
the dispatcher does not select a rider. The result may be an offer or a waiting state if
no eligible rider is free.

The rider sees a pending offer with **Accept** and **Decline**. A decline triggers the
server's replacement attempt and refreshed state. Acceptance atomically starts the order
and route; no dispatcher departure confirmation is needed. Rider routes remains available
to the dispatcher with acceptance, delivery and handover progress plus Refresh progress.
Delivery-day/window, COD, returns and cash-closeout checks remain enforced. The rider
delivers and hands over cash; the dispatcher receives the handover and closes the route.

## Verification and boundaries

Focused frontend tests, the API workspace HTTP integration test, build validation, selected
backend regressions and a full local browser journey cover OTP request/verify, customer
review, automatic allocation, decline/reassignment, automatic start on acceptance, COD delivery
and hub closeout. Browser screenshots are written outside the repository by setting
`LANNPYA_SCREENSHOT_DIR`.

Twilio delivery, production credentials and live SMS delivery were not configured or
tested. Production OTP behavior depends on server configuration and fails closed when
required delivery configuration is missing. See the [frontend handoff](FRONTEND_HANDOFF.md)
for endpoint schemas and the [API contract](API_CONTRACT.md) for the complete service
contract.
