# Complete browser delivery workflow

The final Chromium scenario passed using a fresh isolated SQLite database and fictional
order text. Every mutation below was initiated by the actual selected frontend controls.

1. Enter local Admin workspace. Open the optional parser; paste Burmese digits and address
   text with COD 25,000. Actual backend parsing produces AMBER and no coordinates.
2. Fill parcel description and save original chat. The API creates a saved order with the
   unmodified original message and extraction provenance.
3. Generate a private customer link. Open it in another browser tab sharing the local
   session. Verify the synthetic phone's last four digits.
4. Submit **0,0 as an explicitly fictional test point**, acknowledge selection, and submit
   availability/instructions. The canonical order still has no pin while review is pending.
5. Return to Admin; refresh and approve the actual customer request(s). The pin is now
   saved, with AMBER retained and no claim of independent geospatial verification.
6. Explicitly acknowledge hub receipt and unverified map accuracy; prepare and assign a
   rider. Confirm physical route departure in the dialog. The order becomes OUT_FOR_DELIVERY.
7. Open Rider workspace using the assigned local rider. See its real assigned queue,
   landmark/notes and properly encoded Google Maps link where navigation is ready.
8. Open delivery/cash dialog. Save is disabled for two seconds; cancel is available.
   An unexplained cash difference is rejected without completing delivery. Record 25,000
   actual COD and confirm delivery through the button. The order becomes DELIVERED.
9. Submit rider cash handover. Return to Admin, reject a negative receipt via input
   validation, then record 25,000 physically received and close the route.
10. Refresh/reconnect to Admin. The delivered order remains visible. Read-only API checks
    confirm persisted status, closed route, DELIVERY_STARTED and exactly one DELIVERY_COMPLETED.

In this application **route departure is the delivery start action** and records its events
for all stops. The rider cannot independently depart a draft route. The original rider
START API remains, but the browser case does not secretly call it to claim a missing button.

Delivery history is inspected via the protected API; the selected order page does not yet
provide a complete event-history viewer. Cash records are ledger/physical-count assertions,
not a payment-transfer or remittance integration. No external Google Maps navigation, phone
call, real GPS measurement, customer contact or paid AI request occurred.

Additional browser journeys cover failure -> physical hub return -> zero-cash closeout,
incident resolution, unassignment, multi-stop viewing, rescheduling/rejection and link
security. Expiry moves timestamps only through an explicit test-fixture endpoint.
Browser refresh persistence was verified; isolated database reopening across process restart
is additionally covered by the passing Python suite. The pre-existing port-8780 workspace
was restarted after testing with an identical before/after logical database fingerprint.
