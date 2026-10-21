# Three-role functional review

Version 0.6.1 · 21 October 2026

Test only these three sides: Admin, Customer and Rider. The merchant role was removed. Sender details are optional order context.

## Start clean

Reload index.html after updating. The one-time v4 reset removes previous LannPya records and drafts on that browser origin. It does not import the previous v1/v3 data and does not recreate sample parcels or RT-001. Subsequent refreshes preserve new work. The normal clock uses real Yangon time; use Any time on manual orders for an immediate end-to-end test.

## Test one parcel

1. Admin → Add order. Enter a name, phone such as 09794339082, an item, Kamayut, COD 100 MMK, today and Any time. Enter the real values you want to test; the example is not automatically seeded.
2. Tick The parcel has physically arrived at the hub if appropriate. Leave coordinates blank to test customer-side location submission. Click Create order and customer link.
3. Open Customer. Pick that exact order under Local customer preview, or copy the link from the order's Customer link panel and paste it into Open my delivery.
4. Enter that phone's last four digits (9082 for the example). Opening another order requires that order's own digits.
5. Choose a location. For a repeatable schematic test, select Use township preview point (test only); it never becomes verified automatically. Enter availability/note and submit.
6. Admin → the order → Review customer location. Enter why the point is accepted and confirm. The saved response stays intact. The parcel becomes Ready only if payment/contact/location/custody checks all pass.
7. Admin → Routes / departure → Create route. Select Ko Aung or Ko Wai and the same delivery day. Return to the order, assign the new route, then dispatch it from Routes / departure.
8. Rider → choose the route's rider. The Delivery stop card shows recipient, instructions, amount and Delivered. Tap Delivered, test Undo if desired, then repeat and wait two seconds to confirm cash. With Any time and today's date, no clock adjustment is required.
9. Customer link now shows delivery completed and recorded amount. Rider history shows the completed parcel.
10. Rider taps **Hand over [recorded total]** once after all route parcels/returns are accounted for. No amount dialog opens for a matching handover. Use **Different amount** only for a different count and explain the difference. The page then shows awaiting hub receipt rather than another submit button.
11. Admin → Hub closeout → **Receive cash & close route**. Count the cash and enter the physical amount (0 for zero cash), then confirm once. The normal route closes immediately with the receipt. No separate close button or acknowledgement dialog is needed. Cash handover is not the parcel-delivery action.

This closeout update does not run another data reset. Reload to load the updated controls; existing v4 orders and routes remain.

## Test alternatives

- **Admin already knows the location:** enter both coordinates during manual creation and tick I have verified these coordinates. Leave it unticked to require review.
- **Prepaid:** selecting prepaid fills zero. Nonzero collection is prohibited.
- **Cash mismatch:** Rider uses Different amount and enters a reason. Admin actual receipt differing from either declaration or recorded collection requires a reason. Without the explicit investigated/resolved checkbox it stays disputed; the route cannot close. Reason controls stay hidden for matching amounts.
- **Unresolved work at receipt:** a valid hub receipt is retained even if a collection discrepancy, physical return, incident or queued action blocks closure. The exact blockers are listed. Resolve them, then Close route without re-entering the receipt. Separate receive/close audit records are preserved even when submitted together.
- **Customer receives a forwarded/incorrect link:** three wrong well-formed checks lock only that link. Admin reissues, revoking the previous token. Customer cannot search by phone alone.
- **No orders/links:** Customer shows a clear empty state with a path to manual creation, not an invalid hardcoded link.
- **No GPS:** manual coordinates or admin assistance remain available. An approximate test point is always labelled and requires approval.
- **Changes after dispatch:** customer details become view-only. No material address/payment change can silently reopen or move a departed parcel.
- **Specific future delivery day/window:** dispatch errors show the parcel date, route date and current app date; delivery errors show the start time. Use Test scenarios only if deliberately testing future dates; Use real date/time returns to normal.
- **Failure:** rider records reason and future retry/return. Return pending requires admin physical receipt before Returned. Cash closure remains blocked until accounted for.
- **Offline:** prepare the rider's assigned queue online, then enable simulated offline. Handoff becomes pending locally; reconnect/replay acknowledges it locally, never across devices. Unprepared offline work says Queue unavailable, not zero completed work.
- **Partial intake failure:** batch intake remains optional. Successfully imported rows do not erase failed drafts.

## Reset and verification boundaries

Reset deletes the old app storage keys and drafts at first new-version load. Source, PRD and exported files are not deleted. No in-app undo exists. Each browser origin owns its storage; this app cannot remotely clear other devices or origins. Reload all old app tabs so they no longer run the prior version.

Automated checks exercise both domain rules and form handlers in an in-process DOM adapter; they do not render CSS or certify a real browser. Browser/mobile visual review remains outstanding. Static HTTP offline-shell restart, real geolocation/voice/navigation and secure multi-user backend behavior need integration/device verification.

The customer preview list is explicitly a local testing aid. Production customer access must be token-scoped by a backend; public local storage and role previews do not provide authentication.
