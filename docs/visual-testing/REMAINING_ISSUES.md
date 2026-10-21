# Remaining issues and demo boundary

Historical Phase 15 report. Interactive Leaflet selection and the persisted event-history viewer
were completed in [Phase 16](../PHASE16_MVP_COMPLETION.md). Use that report for current status.

## Before public access

- Production authentication and per-user/tenant authorization are absent. The loopback
  role selector/BFF is a developer tool, not public login. Do not expose this server.
- Production PostgreSQL, hosting/TLS and deployment security have not been verified by
  this SQLite/loopback browser run. Existing production configurations continue to fail closed.

## Local hackathon readiness

The verified browser delivery flow is ready for a **local, supervised demonstration**.
All five major Admin sections, Customer verification/update forms, assigned Rider queue,
delivery/failure and hub cash closeout work against real backend persistence. Port 8780
was restarted with the fixes and remains the local entry point.

Present these limits explicitly:

- AI is mock/configurable, with rules-only/not-requested cases; no real-model quality claim.
- No trusted geospatial catalog or township boundaries: no automatic GREEN, fabricated
  coordinates or measured confidence percentage. Customer confirmation is not map accuracy.
- The Customer UI uses coordinates/current-location assistance; it is not an interactive
  draggable doorstep map picker. Rider map/route art is schematic; navigation is an optional
  external URL, not live GPS or optimization.
- Routed delivery starts at dispatcher departure. There is no separate Rider start button
  for these routed orders. The lifecycle remains enforced by the backend.
- Complete event history exists in the protected API, but lacks a full viewer in the
  selected product UI. Arbitrary status editing, rider-availability administration and all
  legacy API operations are not represented as buttons on these pages.
- Rescheduling/leave-with-security may need dispatcher review under configured policies.
  The browser test verifies proposal/review, not automatic courier acceptance.
- Updates use refresh/polling, not WebSockets or push. Reload requires local reconnect;
  buyer verification authorization is deliberately cleared across process restart.
- Masked calling, photographic proof, optimized route drawing, live tracking and payment
  transfers are not implemented live services. The separate prototype is browser simulation.
- The prototype toolbar's legacy API-workspace link still targets port 8000; use its explicit
  LIVE_BACKEND banner link to return to this app. The live workspace itself uses same-origin
  links. This minor prototype navigation debt was reviewed, not exercised as a live workflow.

## Verification limits / next work

Compact navigation/role-switch touch targets deserve accessibility polish. Viewport checks
are not physical-device, cross-browser, assistive-technology or exhaustive text-length tests.
No unexplained browser failures remain in the final 28-case suite. External AI availability,
DB fault injection and concurrency were regression-tested in Python, not claimed as real
external outages or simultaneous browser users. Dependency consistency passed; a new external
vulnerability audit was not performed.

Next: review this integration branch locally, add the event-history UI and improve compact
touch targets, then implement approved production identity/authorization before any public
demo. Preserve this browser suite for each later integration change. No remote push, merge,
deployment, regular database mutation or paid service was performed.
