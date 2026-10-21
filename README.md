# LannPya — admin, customer and rider

Version 0.7.0 · 21 October 2026

**API integration:** the supplied `lannpya-ai` backend now has a separate connected
workspace in `api.html`. See [API_INTEGRATION.md](API_INTEGRATION.md) for startup,
per-role local credentials and the database-backed walkthrough. API mode calls
the supplied APIs plus route/cash extensions. The local prototype below remains
available; this update does not reset browser records.

The app has exactly three operating roles: **admin, customer, rider**. There is no merchant workspace or merchant permission. Sender/business names are optional parcel context, not a fourth role.

Open `index.html` and reload once after updating. No install or build is required.

## Requested data reset

The v0.6.0 three-role update introduced a one-time reset per app origin, removing previous saved orders, routes, links, events, collections, queued actions and old form drafts. It starts empty: no sample orders, no default route and no legacy import. New orders you create after this one-time reset are retained normally across refreshes. The v0.6.1 closeout update keeps the same storage key and reset marker: it does not reset your new test data again.

Only known LannPya storage keys are cleared. Other apps' storage, workspace source files, the supplied PRD and files you previously exported are untouched. There is no in-app undo for this reset. If the browser blocks storage removal, the status reports memory-only operation; another browser/origin's records cannot be erased from this page.

## Quick workflow

1. **Admin → Add order.** Enter recipient/phone, item, township, COD or prepaid amount and delivery day. Availability defaults to **Any time**, so same-day testing does not require adjusting a clock.
2. Tick physical hub receipt only if the parcel is present. Coordinates are optional. Create the order; its own customer confirmation link is generated automatically.
3. **Customer.** Open the specific order from the labelled local preview, or paste its private link. Verify with the last four digits of the phone you entered—there is no universal demo PIN.
4. If no verified anchor exists, enter a point, use device GPS, or select an explicitly approximate test point. Save availability and the rider note. A proposed point stays held until the admin reviews it.
5. **Admin → order → Review customer location.** Approve with evidence. Confirm the parcel is received. Create a rider route for the same day and assign it. Dispatch the route.
6. **Rider.** Select the assigned rider; the delivery-stop card shows its Delivered action. Tap Delivered, wait two seconds, then confirm the actual COD/zero cash.
7. Finish any other parcels/returns. Rider taps **Hand over [recorded total]** once when physically handing cash to the hub—no second dialog. Use **Different amount** to record an exception with a reason.
8. Admin → Hub closeout → **Receive cash & close route**. Count the cash, enter the amount physically received (including 0 for zero-cash routes), and confirm once. Matching receipt and route closure are saved together; there is no separate close confirmation. Only cash differences reveal the reason/resolution controls.

If a return, collection discrepancy, incident or queued action is unresolved, receipt is still saved but the route stays open with the blockers listed. After resolving them, use **Close route** without counting/receiving cash again. Rider declaration and admin physical receipt remain separate audited actions; the shortcut never assumes that the hub received cash.

If admin already knows a location, enter coordinates and explicitly tick location reviewed during manual creation. Customers can still confirm preferences and nudge the pin within 500 m before dispatch.

## Time and customer access

The normal clock follows real time in Asia/Rangoon. Customer edits remain open until dispatch by default. A daily cutoff is optional in Hub policy. Test scenarios can freeze the clock deliberately; Use real date/time resumes it. Specific windows still enforce their dates/start times. Any time allows delivery at any hour on the selected day.

The Customer menu opens a real landing page, not an arbitrary first order. Its local preview list is for testing only; live customers will receive their own token link after backend integration. Locked, revoked or expired links explain how to contact the admin.

## Implementation and tests

- `workflow-domain.js`: empty initialization/reset, manual/batch creation, three-role command guards, readiness, links, customer proposals, assignment/departure, attempts, returns/cash closeout and local replay.
- `functional-app.js`: admin forms, customer landing/confirmation, rider workspace and scenario controls.
- `sw.js`: versioned static-shell caching when served over HTTP/HTTPS. It does not cache private API responses or external maps.
- `workflow-domain.test.js` and `functional-app.test.js`: business rules and controller tests, including a fresh manual-order-to-delivery journey.

Run `npm test` and `npm run check`. Fixtures live only in explicit test setup; they are never automatically loaded into the running app. Old implementation files remain inactive and are not referenced by index.html.

See [FUNCTIONAL_REVIEW.md](FUNCTIONAL_REVIEW.md) for the current test guide. The original PRD remains reference material; its merchant role and old fixed-clock assumptions are superseded by this three-role update.

## Current limits

Data and command guards remain device-local, not authenticated backend security. There is no cross-device synchronization. Location editing uses fixture coverage/coordinates rather than verified map boundaries; customer GPS depends on permission and coverage. Uncertain encoding requires manual review and no AI provider is contacted. Browser voice/navigation and actual mobile/visual/service-worker behavior require device verification. No real message, payment or external deployment is triggered.
