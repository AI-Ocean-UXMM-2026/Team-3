# Handoff: LannPya Signboard UI, order flow and rider tabs

Written 21 October 2026 so work can continue in another tool (Codex) if this session runs out. Check the "Status" column against `git log` on `mtt` before starting; anything marked done is pushed.

## Where things are

- Repo: `FightaHackathon/lannpya-ai`, branch `mtt` (Arti's fork). Upstream: `ZawLwinHtoo/lannpya-ai` (open a PR from fork `mtt` into Zaw's `mtt`).
- Product UI: `frontend/index.html` (same as `frontend/prototype.html`) loads `frontend/css/signboard.css`, `frontend/js/workflow-domain.js` (state machine, all rules) and `frontend/js/functional-app.js` (views; whole `#app` re-renders through `innerHTML` on every action).
- Developer API page (not product UI): `backend/tools/api_workspace/api.html`, served only by the local test server at `/api.html`.
- Product rules and voice: `PRODUCT.md`, `DESIGN.md`. Burmese strings needing native review: `BURMESE-REVIEW.md`.
- Brand: navy `#16263A`, saffron `#F0A032` (never text on light), cream `#FFF5E4`, ok green `--ok #1C6A45` / `--ok-bg #DDF1E5`. Fonts Inter, Manrope, Noto Sans Myanmar. Status = icon + word.

## How to run and test

```
npm run test:frontend          # node --test, must stay green (99 tests at handoff)
node scripts/build_frontend.cjs
cd backend && .venv/bin/python -m pytest -q tests/test_backend_dashboard.py tests/test_integrated_workspace.py tests/test_three_role_workflow.py tests/test_api_contract.py
cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
backend/.venv/bin/python -m tools.integrated_workspace --port 8790 --temporary   # live app at http://127.0.0.1:8790/
```

Frontend tests use a fake DOM (`frontend/tests/test-dom.js`): no `Element.closest`, forms are submitted through `form.onsubmit`, `FormData` skips unchecked radios and disabled fields. Five of Zaw's Playwright journeys on `/api.html` already fail before this work; don't chase them as part of this list.

## Arti's request (21 Oct, 17:00) and status

| # | Change | Where in code | Status |
|---|---|---|---|
| 1 | Create order opens a success pop-up on the same page instead of navigating to the order page | `manual.onsubmit` in `wireNewForms()` currently calls `go('order/'+id)`. Replace with `dialog()` showing the order, the buyer link (Copy) and buttons "Open order" / "Add another". | Done |
| 2 | Clearer success message after every action | `toast()` and `submit()` in functional-app.js. Make a success variant: green check icon, bold line naming what happened ("Order LP-0003 created"), Burmese first where the rider/buyer sees it, longer dwell (about 4 s). | Done |
| 3 | Separate stages on the order check: stage 2 = buyer confirmation (location), stage 3 = rider assignment. Stage 2 shows only location actions (no route button). Once the location is confirmed, stage 3 hides "Confirm the location myself" and "Check the buyer's pin" and shows only rider/route buttons | `detailView()`, the "Next steps" panel (`right-stack`) | Done |
| 4 | In the assign pop-up, let the dispatcher pick a rider directly (create a draft route for that rider and day if none exists), as well as choose an existing route | `orderDialog(id,'assign')`; domain commands `create_route` (check name in workflow-domain.js) then `assign` | Done |
| 5 | Next-step icons grey until done, green when done | same "Next steps" list; add `.step.done` (green `--ok`) and `.step.todo` (grey) classes in signboard.css | Done |
| 6 | Main action top right, e.g. move "Save and check again" to the top right of the order check | `detailView()` `.check-head`; use `<button form="edit-form">` in the header | Done |
| 7 | Service board: "Plan rider routes" moves into each Ready card as its own button, opening the assign pop-up on the same page | `boardRows()` `card()`; cards are `<a>` today, so turn the card into a `<div>` with a link plus a button (no nested interactive elements) | Done (button shows only on Ready cards without a route; not yet seen in a screenshot because the seed has no Ready order) |
| 8 | Buyer page shows order details: shop name, items, phone numbers | `customerView()` `.customer-parcel`; add `name`,`phone` to the verified order fields in `customer()` in workflow-domain.js | Done (phone shows as "ending 1602": a domain test forbids the full phone in the buyer view) |
| 9 | Rider: buttons are Can't deliver + Accept; Delivered appears only after Accept | `riderView()` `.stop-actions`; add domain command `accept` (sets `o.accepted={at,riderId}`) | Done |
| 10 | Rider: landmark block looks like a button (navy). Put the whole current stop in one bordered box instead | `.landmark` in riderView + signboard.css | Done |
| 11 | Rider tabs: Picked up, On the way, Delivered, Returns, All, reached from a three-line menu beside the rider's name | `riderView()` header; tab state in a module variable, filter the stop list | Done |
| 12 | Route status "Closed" reads "Complete" | `WORDS` map: add `closed:'Complete'` | Done |
| 13 | Cash handover amounts as boxes, not the sentence "The rider counted X. The hub received Y." | `routeCloseout()` `.handover-state`; reuse the `.facts.cash-facts` grid | Done (not yet seen in a screenshot) |

Rider tab meaning chosen: Picked up = on today's route, not yet accepted; On the way = accepted, not finished; Delivered; Returns = `return_pending` or `returned`; All.

## Left to polish (found in the last screenshot pass, not yet fixed)

All in `frontend/css/signboard.css`, appended blocks at the end of the file:

1. The "Order created" pop-up has no inner padding. Add `padding:22px 24px` to `.created-dialog`.
2. The rider three-line menu also shows the generic details chevron. Add `.rider-menu>summary::before{display:none}`.
3. The buyer's order details stack in one column on phones and get tall. Delete the `@media (max-width:560px){.customer-details{...}}` rule so it stays two columns.
4. On phones the success toast is narrow and wraps to four lines. Add `width:max-content` to `.toast`.
5. Not yet seen in a screenshot: the "Plan route" button on Ready cards, and the cash handover boxes in close-out. Seed a Ready order and a handed-over route, then look.
6. Stage logic in `nextSteps()` is strict. "Check the buyer's pin" only shows after the parcel has arrived. If buyers often confirm before the parcel arrives, also show it in stage 1.

## Already done earlier today (pushed)

- Delivery day cards + Morning / Afternoon / Evening / All day slots on the buyer page; shop prep / stock timeline on new and edited orders sets the earliest delivery day (`W.PREP`, `W.SLOTS`, `buyerDates()` in workflow-domain.js).
- Google Maps pin picker (`frontend/js/customer-map.js`), key from `LANNPYA_GOOGLE_MAPS_BROWSER_KEY` in `backend/.env`, served as `/maps-config.js`. Not yet wired into the Signboard UI.
- Motion batch (press, toast, sheet dialogs, undo drain), Mobbin-based paste banner and rider tool row.

## Still open after this list

- Connect the Signboard UI to Zaw's API (`frontend/js/local-api.mjs`, `backend-client.mjs`) so it uses real orders; today it is demo data in localStorage.
- Native review of Burmese strings.
