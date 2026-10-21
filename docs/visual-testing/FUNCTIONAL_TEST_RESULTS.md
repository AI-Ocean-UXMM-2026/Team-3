# Functional results

All 28 final browser cases passed. Exact case names/outcomes are in
`BROWSER_OBSERVATIONS.json`; executable coverage is `tests/browser/website.spec.cjs`.

| Area | Rendered-browser verification |
| --- | --- |
| Admin navigation | Home, Orders, Routes, Hub closeout, Riders; empty states, shortcuts, refresh |
| Parsing | Burmese Unicode numerals, Myanglish, mixed text, invalid/missing phone, unknown/missing/multiple townships; COD; UI values compared with actual API responses |
| Parsing safety | Second parse clears stale fields/payment choice; no percentage or invented coordinates; configured AI mock label and `not_requested` status remain explicit |
| Order writes | Original chat saved; structured manual form saved; field correction; inert HTML-like instructions; record survives browser refresh/reconnect |
| Customer | Generated native link, minimal card, four-digit verification, initial pin proposal, availability, instructions, rescheduling, explicit dispatcher review |
| Buyer failures | Three wrong attempts, lockout despite correct fourth attempt, revoked/reissued link, invalid token, expired link and expired verification authorization |
| Dispatcher | Approve/reject buyer request, keep unapproved pin off canonical order, explicit hub receipt, map-review acknowledgement, assignment, route departure |
| Rider | Valid local identity and invalid-ID rejection; assigned queue, expanded other stops, landmark/notes, encoded navigation link, refresh, delivery/cancel/failure actions |
| COD | Incorrect amount without required reason rejected; correct actual cash and explicit delivery submission accepted; no duplicate completion button/event |
| Routes/hub | Past route date rejected; real draft saved; no empty-route dispatch; physical departure, handover, invalid negative receipt, counted receipt and closure |
| Exceptions | Incident blocks preparation, resolution restores it; draft unassignment; failed parcel requires physical return before zero-cash closeout |
| Error handling | Aborted real order write displays an error; no simulated success and no saved row |
| Local security | Anonymous bootstrap rejection, forged CSRF rejection, private raw paths/assets unavailable, cookie policy, no privileged browser headers |
| Simulation | Separate prototype explicitly says DEMO_SIMULATION; its static startup has no unexpected console error |

The main end-to-end case performs user actions through controls. Read-only API calls inspect
saved orders, routes and event history; they do not secretly complete missing UI steps.
Expiry uses the explicit local `/dashboard/expire` fixture to move database timestamps;
subsequent browser requests are checked by the real backend. Network failure uses an
explicit Playwright abort, not a claim about a real provider outage.

The 842 Python tests additionally exercise provider timeout/malformed/unavailable behavior,
transactions/fault injection, authorization, duplicate completion, migrations and database
reopening. Those checks were not misrepresented as visual browser interactions.
