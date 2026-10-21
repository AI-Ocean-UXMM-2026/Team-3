# LannPya AI frontend handoff — Phase 7

Backend contract for vanilla JavaScript, React or another framework. No frontend code was
changed. The backend supports the dispatcher, buyer and rider workflows below locally.
**An internet-accessible, shared-browser demo is blocked on production authentication and
secure deployment. Never deploy a dispatcher/admin development token in browser code.**

## Start here

- Normal backend origin: `http://127.0.0.1:8000`; no `/api` suffix in the base URL.
- Interactive schemas: `/docs`; machine-readable contract: `/openapi.json` and the exported
  [OPENAPI.json](OPENAPI.json). Full field/validation detail: [API_CONTRACT.md](API_CONTRACT.md).
- Repeatable isolated setup/real HTTP validation from `backend`:
  `.\.venv\Scripts\python.exe scripts\demo_mvp.py`.
- For live local integration:
  `.\.venv\Scripts\python.exe scripts\demo_mvp.py --serve --frontend-origin http://localhost:5173`.
  The script creates data, migrations, private tokens and three loopback actor instances
  itself. Ctrl+C stops them. Ports/IDs/credentials are in the printed **ignored run directory**,
  `private_access.json`; tokens are not printed. Do not serve that directory as static content.
  Its buyer_link opens a fresh candidate card against the matching merchant backend.
  Each run gets a fresh database; existing `.env` and normal local database stay untouched.
- Read [DEMO_GUIDE.md](DEMO_GUIDE.md) before showing fixtures and
  [PRODUCTION_BLOCKERS.md](PRODUCTION_BLOCKERS.md) before planning any public access.

## Access and CORS

| Client | Required access | Limit |
| --- | --- | --- |
| Health / stateless parser | No credential | Echoes caller input only; saves nothing |
| Merchant / dispatcher | X-Dev-Access-Token, server-bound local actor | Merchant scoped to own orders; Dispatcher/Admin manage local records |
| Rider | Its own server-bound Rider actor + local token | Own profile/availability/queue/delivery actions; no private order-management API |
| Buyer card | Secret link capability only | Minimal data before verification |
| Buyer sensitive actions | Same link + Authorization: Bearer credential after last-four check | Bound to link/order/generation, short-lived |

The local token is not login or production authentication. Each instance represents one
server-configured actor; there is no user/role-switch endpoint. The demo uses separate
merchant/dispatcher/rider instances with distinct secrets. Enter local credentials at
runtime and keep them in memory; never source them from public build-time variables,
query parameters, analytics, localStorage or a committed fixture. Buyer requests must
never inherit a dispatcher token. Buyer Bearer credentials do not authorize dispatcher APIs.

Local CORS config is an exact-origin JSON array, for example:

```dotenv
LANNPYA_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5500"]
```

Defaults also include localhost:5500. Other local frontend ports are supported through
configuration; the demo --frontend-origin flag configures only its child processes.
`localhost` and `127.0.0.1`, different ports and different schemes are different origins.
Serve the frontend over HTTP; file:// and Origin:null are unsupported. No wildcard origins,
cookie credentials or arbitrary public-origin access are needed. Approved OPTIONS preflights
allow GET/POST/PATCH and Content-Type/X-Dev-Access-Token/Authorization without authenticating
the preflight. Subsequent API calls still enforce access. Disallowed preflights return 400
plain text; browser failures commonly surface as fetch TypeError, not the JSON envelope.
Retry-After is exposed to browser JavaScript. Allowed-origin 401/429/500 JSON remains readable.
CORS is a browser policy, not authentication; production management/buyer APIs remain closed.

## Complete endpoint list

Three-role workspace extensions (current local UI is `D:/Zero_Lag/api.html`):

| Operation | Purpose |
| --- | --- |
| `GET /api/session` | Server-bound actor identity, not a role-switch API |
| `GET /api/routes` | Paginated own/admin route summaries, actual cash and closure blockers |
| `POST /api/routes` | Admin creates rider/day draft route |
| `POST /api/routes/{route_id}/actions` | Versioned/idempotent DISPATCH, HANDOVER, RECEIVE_CLOSE or CLOSE |
| `POST /api/orders/{order_id}/operations` | Physical hub/return receipt, incident or collection-difference resolution |
| `POST /api/orders/{order_id}/prepare-assignment` | Admin atomically prepares a reviewed parcel, optionally records explicit physical receipt, creates/selects a draft route, and assigns it; does not dispatch |

`POST /api/orders` now allows Admin/Dispatcher to omit merchant_id. Its legacy
merchant_id column then holds the bound administrative owner, not a synthetic
merchant account. Existing explicit merchant clients retain their old scope.
Optional `parcel` context contains item, sender, reference, delivery_day and
hub_received; custody, route and actual cash history live in parsing_metadata.parcel.
Rider assignment accepts route_id. Routed deliveries require explicit actual_amount
and support difference_reason. Route handover never implies hub receipt. Matching
admin RECEIVE_CLOSE records receipt and closes atomically only when all blockers
are cleared. These additions use the existing orders/links/assignments/database,
not a parallel browser-only ledger. The older merchant-centric guide below remains
for backward-compatible API consumers; the new workspace has three sides only.

Preparation body: `{request_id:u,expected_version:v,rider_id:r,
receive_at_hub:true,acknowledge_unverified_location:true}`. Supply exactly one of
`rider_id` (create a route for the parcel's saved delivery day) or `route_id`
(append to an existing matching-day draft). Existing readiness, rider availability,
pending-customer-review, location, custody and COD checks still apply. A failure
rolls back every change, including receipt and new route creation. Success returns
`{order,assignment,route}`. Repeating the same actor/request UUID/body has no second
assignment; changed content for that UUID conflicts. Retain the UUID and exact body
for uncertain network retries. Departure requires a separate route DISPATCH, and
rider handover never substitutes for admin physical cash receipt.

Names in braces are runtime UUIDs/tokens, not literal strings. Examples use aliases:
`v` = latest order version, `rv` = latest rider profile version, `u` = new request UUID,
`m/r` = existing merchant/rider UUID. All examples are JSON descriptions, not hardcoded
customer data. HTTP success is 200 unless noted. Data schemas are defined below and in OpenAPI.

| Operation | Request body / query example | Success |
| --- | --- | --- |
| `GET /health` | none | Health |
| `POST /api/orders/parse` | `{raw_text: rawText}` | Parse |
| `POST /api/orders` | `{merchant_id:m,raw_text:rawText}` OR `{merchant_id:m,structured:{township:"Hlaing",cod_amount:"0"}}` | 201 Order |
| `GET /api/orders` | `?page=1&page_size=20&status=NEEDS_REVIEW&confidence=AMBER&q=...` | OrderPage |
| `GET /api/orders/{order_id}` | none | Order |
| `PATCH /api/orders/{order_id}` | `{expected_version:v,floor:"2",delivery_instructions:userText}` | Order |
| `PATCH /api/orders/{order_id}/status` | `{expected_version:v,status:"NEEDS_REVIEW"}` | Order |
| `GET /api/orders/{order_id}/events` | `?page=1&page_size=20` | EventPage |
| `GET /api/users` | `?role=Merchant&limit=100` | User[] |
| `POST /api/orders/{order_id}/confirmation-link` | none | 201 Link |
| `POST /api/orders/{order_id}/confirmation-link/revoke` | none | `{revoked:true}` |
| `POST /api/orders/{order_id}/location-reference` | `{request_id:u,latitude:lat,longitude:lng,township:"Hlaing",source_reference:evidence,independently_checked:true}`; only real independent operator checks | 201 `{reference_set:true,independent_township_boundaries_available:false}` when boundaries unavailable |
| `GET /api/orders/{order_id}/buyer-requests` | `?page=1&page_size=20` | BuyerRequestPage |
| `PATCH /api/orders/{order_id}/buyer-requests/{request_id}` | `{expected_version:v,decision:"APPROVE",reason:operatorReason}` OR REJECT; path uses **history item id**, not its request_id | Review |
| `GET /api/confirm/{token}` | none | Card |
| `POST /api/confirm/{token}/verify` | `{last_four:userEnteredFourAsciiDigits}` | BuyerAuthorization |
| `GET /api/confirm/{token}/details` | buyer Bearer header | BuyerDetails |
| `PATCH /api/confirm/{token}/location` | `{request_id:u,latitude:lat,longitude:lng,initial_pin_acknowledged:true}` + buyer Bearer | BuyerAction |
| `PATCH /api/confirm/{token}/response` | `{request_id:u,action:"AVAILABLE",instructions:userText}` + buyer Bearer | BuyerAction |
| `POST /api/riders` | `{name:actualRiderName,operational_status:"AVAILABLE"}`; optional email/contact_phone | 201 Rider |
| `GET /api/riders` | `?page=1&page_size=20&operational_status=AVAILABLE` | RiderPage |
| `GET /api/riders/{rider_id}` | none | Rider |
| `PATCH /api/riders/{rider_id}` | `{expected_version:rv,operational_status:"ON_BREAK"}` | Rider |
| `GET /api/riders/{rider_id}/queue` | optional `?cursor=<last snapshot hash>` | Queue |
| `POST /api/orders/{order_id}/assign` | `{expected_version:v,rider_id:r,stop_sequence:1}` | 201 AssignmentResult |
| `POST /api/orders/{order_id}/unassign` | `{expected_version:v}` | AssignmentResult |
| `PATCH /api/orders/{order_id}/assignment` | `{expected_version:v,stop_sequence:2}`; null clears sequence | AssignmentResult |
| `GET /api/orders/{order_id}/assignments` | `?page=1&page_size=20` | AssignmentPage |
| `PATCH /api/riders/{rider_id}/deliveries/{order_id}/status` | `{request_id:u,expected_version:v,action:"START"}`; completion/failure examples below | DeliveryActionResult |

## JSON responses and field conventions

These examples are **abridged**; full actual redacted output is in
[PHASE7_SAMPLE_RESPONSES.json](PHASE7_SAMPLE_RESPONSES.json). All full success schemas are
in OpenAPI, including buyer request history/review. Tolerate additive fields. Do not treat
null as zero, an empty address or a verified location.

```json
{"status":"ok","service":"LannPya AI"}
```

Parse returns `is_mock:false`, provider/notice, `address` (customer_name, phone_number,
township, street, landmark, building_floor_unit, cod_amount, delivery_instructions,
time_window), confidence, validation_reasons, original_text, normalized_text, normalization,
field_sources, location_verification, manual_review_required and ai status metadata.
The rules parse actual input. Hybrid AI is mock or not_requested/privacy_blocked; it is
not real model extraction. Legacy explicit fixed mock mode is not used for saved raw orders.

```json
{
  "id":"<order UUID>","merchant_id":"<merchant UUID>","status":"DRAFT","version":1,
  "customer_phone":"<normalized input phone>","township":"Hlaing","cod_amount":"25000",
  "latitude":null,"longitude":null,"confidence_level":"AMBER",
  "manual_review_required":true,"parsing_mode":"hybrid","ai_availability_status":"mock"
}
```

Order additionally includes customer_name, original_message, normalized_message, street,
landmark, building/floor/unit, building_floor_unit, delivery_instructions, delivery_time_window,
confidence_reasons, field_sources, parsing_metadata, created_at and updated_at. Saved field
names differ intentionally: Parse.phone_number -> Order.customer_phone; Parse.time_window
-> Order.delivery_time_window; Parse.confidence -> Order.confidence_level.

COD from `/parse` is integer/null; persisted/queue COD is an exact whole-MMK **digit string**
or null. Keep it as a string (or BigInt for calculation), not a floating-point money value.
Coordinates in typed stored/detail/queue responses are decimal strings/null; send decimal
strings for precision. Coordinates must be supplied/cleared together, finite, within
[-90,90]/[-180,180], maximum seven decimal places. UTC timestamps use ISO 8601.

Paginated endpoints return `{items:[...],total:5,page:1,page_size:20}`. Page >=1 (up to
1,000,000), page_size 1..100; default 20. Order filters combine, q is a nonblank literal
substring <=100 characters. Queue is the bounded full snapshot below, not a paginated page.
GET users is a limited array, not a page; there is no merchant user-creation HTTP endpoint.

Link: `{link_id,confirmation_url:"/confirm/<secret>",absolute_url,expires_at}`. This is a
**frontend route**. Frontend reads its token and calls `/api/confirm/{token}` on the backend.
Absolute URL is optional and based on trusted configured frontend base, never request Host.

Card: `{order_reference,shop_display_name:null,delivery_status,state,expires_at}` only.
No phone/address/GPS/notes before verification. Shop branding/items must later come from
a trustworthy merchant source; do not substitute the internal user-profile name.

BuyerAuthorization: `{access_token,token_type:"Bearer",expires_at}`. Store bearer only in
memory. BuyerDetails contains current township/street/landmark/building_floor_unit, pin,
instructions/window, order_reference/status, initial_pin_requires_review and policy.
No full phone, customer name, raw message or development token is exposed.

BuyerAction: `{request_id,decision:"REVIEW_REQUIRED",reason_codes:[...],order_status,
confidence_level,submitted_at,confirmed_at:null,resolution:null}`. APPLIED or later APPROVE
sets confirmation time. A 200 review result is **not** a successful dispatch-plan update.
BuyerRequestPage items contain id, request_id, kind, decision, reason_codes, previous_values,
submitted_values, resolution/reason/actor/time and created_at. This private history requires
dispatcher/merchant authorization. Review returns `{request_id,resolution,order_version}`.

Rider: `{id,name,email,contact_phone,operational_status,version,created_at,updated_at}`.
Absent contact stays null. ID reuses User UUID; profile version may change with queue activity.
AssignmentResult: `{assignment,order_status,order_version}`. Assignment has id/order_id/
rider_id/dispatcher_id/status/stop_sequence/failure_reason/failure_note/cod_collected/
assigned_at/updated_at/ended_at. Assignment status ACTIVE is separate from Order.status.

Queue: `{rider_id,operational_status,cursor,unchanged,total,items,generated_at}`. Each item has
assignment_id, order_id, status, order_version, stop_sequence, current delivery/contact notes,
township/street/landmark/building_floor_unit, delivery_time_window/confirmed_window_start,
COD, pin, coordinate_status/navigation_ready/navigation_url, confidence_level,
location_verification, buyer_confirmation and updated_at. No raw message, AI payload or secret.

DeliveryActionResult: `{request_id,assignment_id,order_id,rider_id,status,assignment_status,
order_version,cod_collected,failure_reason,updated_at}`. Events include id/order_id/event_type,
previous_status/new_status, metadata and created_at. Event metadata contains actor/assignment
IDs and operation flags, not private correction/failure values; read private audits separately.

## Dispatcher workflow

1. Parse raw Unicode Burmese/Myanglish text with POST /parse; show normalization warnings,
   field source/review flags and reasons. No record exists yet. POST /orders to save actual
   raw input, or structured explicitly entered fields. Do not submit the parse object whole.
2. GET/filters retrieve saved orders; PATCH editable fields with latest version. Unknown keys
   are rejected; omitted fields stay, null clears. Manual corrections get manual provenance.
   An edit outside DRAFT returns order to NEEDS_REVIEW. Assigned/on-road/terminal edits close.
3. DRAFT -> NEEDS_REVIEW; generate a link only after review status and valid registered phone.
   Send it manually through an existing trusted conversation. Do not include the admin token.
4. GET buyer-requests; review the private proposed/previous values. PATCH using history item's
   **id**, latest order version, APPROVE/REJECT and reason of 5..500 characters. Approval/rejection
   leaves NEEDS_REVIEW; it does not grant geospatial trust or silently prepare dispatch.
5. Buyer AVAILABLE or an operator can set CONFIRMED once validation/review allows. Unresolved
   requests block confirmation/readiness. READY_FOR_DISPATCH requires explicit
   acknowledge_unverified_location:true for AMBER and a Dispatcher/Admin actor.
6. Create/select AVAILABLE rider. POST /assign, not generic ASSIGNED bookkeeping. COD must
   be known (zero means prepaid). GET events/assignments for history. Unassign before start
   to process later buyer corrections, then review/confirm/ready/reassign. No on-road edits.

Lifecycle: DRAFT -> NEEDS_REVIEW -> optional AWAITING_CONFIRMATION -> CONFIRMED ->
READY_FOR_DISPATCH -> ASSIGNED -> OUT_FOR_DELIVERY -> DELIVERED/FAILED. Review/cancellation
branches and allowed back-transitions are in the full contract. FAILED may return to review;
DELIVERED/CANCELLED are terminal. Confidence AMBER/RED/GREEN is not a delivery status.

## Buyer workflow

1. GET card; state VERIFICATION_REQUIRED allows the check, LOCKED means contact shop,
   VIEW_ONLY means completed delivery and minimal information only.
2. POST verify with a **string of four ASCII digits**, never a JSON number. Three failed
   valid guesses lock the link across sessions/concurrent calls. Malformed input is 422.
   Failures never return digits/remaining guesses; do not auto-retry guesses.
3. Success gives separate default 15-minute authorization, capped at link expiry. New
   successful verification invalidates the old credential; success does not reset failures.
4. GET details with Bearer; select a pin deliberately. Initial pin needs
   initial_pin_acknowledged:true and is stored for review, not applied or township-verified.
   <=500m automatic acceptance requires actual independent anchor AND trusted boundaries.
   Default data has neither; unverified/larger/cross-township moves require review.
5. Respond AVAILABLE, INSTRUCTIONS (requires nonblank instructions <=2,000),
   LEAVE_WITH_SECURITY or RESCHEDULE. No unsupported action or client trust flag is accepted.

```javascript
// Construct future values from user selection; keep explicit timezone offsets.
const rescheduleBody = {
  request_id: crypto.randomUUID(), action: "RESCHEDULE",
  time_window: { start: selectedStartWithOffset, end: selectedEndWithOffset },
};
```

RESCHEDULE requires a 30-minute..8-hour window on one Yangon date, default >=2 hours'
notice and <=7-day horizon. Unsupported rescheduling/security delivery is saved for review;
at/after 15:00 Yangon cutoff scheduling also needs review. No fee is collected. Initial
review/confirmation never manufactures GREEN. Buyer writes stop at READY_FOR_DISPATCH.

Default links last 72 hours. Phone correction/cancellation/revocation invalidates them.
Active eligible delivered links become minimal view-only for 24 hours; sensitive edits stop.
Expired/revoked/locked links are not revived. Four digits plus a private link do not prove
phone ownership. Protect frontend page with no-referrer/no-store, no analytics/third-party
scripts, no token logging/history persistence or service-worker caching.

## Rider workflow and polling

Fetch own queue using rider instance/token. Display confidence, pin confirmation and
geospatial verification separately. BUYER_CONFIRMED is not independent accuracy proof.
Only use provided navigation_url when navigation_ready is true, through an explicit user
click. No backend map call/route optimization exists. Missing pin must remain unavailable.

```javascript
const startBody = { request_id: crypto.randomUUID(), expected_version: item.order_version, action: "START" };
const deliveredBody = { request_id: crypto.randomUUID(), expected_version: started.order_version,
  action: "DELIVERED", cod_collected: true }; // User must explicitly attest collection.
const failedBody = { request_id: crypto.randomUUID(), expected_version: started.order_version,
  action: "FAILED", failure_reason: "CUSTOMER_UNAVAILABLE", failure_note: userEnteredNote };
```

START requires AVAILABLE rider and ASSIGNED order. DELIVERED/FAILED require OUT_FOR_DELIVERY.
Positive COD requires true by default; prepaid zero needs none, unknown COD needs review.
Failure requires enum CUSTOMER_UNAVAILABLE, ADDRESS_NOT_FOUND, CUSTOMER_REFUSED,
ACCESS_BLOCKED, COD_NOT_COLLECTED or OTHER. Failure note is optional, private, <=500 characters.
COD flag is an assertion, not payment processing. Do not automatically set it in UI.

Poll every five seconds while active, with no overlapping calls. First request has no
cursor. unchanged:true means **preserve** current items (returned items are empty).
unchanged:false means **replace the full list**, including empty list after completion.
Order is on-road status, confirmed window, stop sequence and stable ties, not shortest route.
Abort on unmount/screen exit and refresh after actions. This is near-real-time polling,
not push. Keep the same UUID/body for a network retry; changed body with a used UUID conflicts.

## Fetch examples: vanilla JavaScript and React

Tested, dependency-free documentation helper:
[examples/lannpya-client.mjs](examples/lannpya-client.mjs). It separates buyer/development
credentials, rejects non-loopback development base URLs, uses omitted cookies, handles
JSON errors/Retry-After and makes no automatic mutation retries. It is an example artifact,
not a change to the frontend or a production SDK.

```javascript
import { createDevelopmentApi, createBuyerApi } from "./lannpya-client.mjs";
const api = createDevelopmentApi({ baseUrl: localDispatcherBase, token: runtimeLocalToken });
const parsed = await api("/api/orders/parse", { method: "POST", body: { raw_text: rawTextFromForm } });
const saved = await api("/api/orders", { method: "POST", body: { merchant_id: merchantId, raw_text: rawTextFromForm } });
const corrected = await api(`/api/orders/${saved.id}`, { method: "PATCH",
  body: { expected_version: saved.version, delivery_instructions: instructionsFromForm } });
const buyer = createBuyerApi({ baseUrl: buyerBackendBase, linkToken: tokenReadFromLink });
const card = await buyer.card();
await buyer.verify(lastFourFromForm); // Helper keeps bearer in closure memory.
const details = await buyer.details();
const requestId = crypto.randomUUID(); // Retain for a retry of this same body.
const proposal = await buyer.location({ request_id: requestId, latitude: selectedLatitude,
  longitude: selectedLongitude, initial_pin_acknowledged: true });
// Show pending review for proposal.decision === "REVIEW_REQUIRED".
```

```jsx
// React example only; React is not installed or selected by the backend.
function useRiderQueue(api, riderId) { // api is a memoized rider-scoped local helper.
  const [items, setItems] = React.useState([]);
  const [error, setError] = React.useState(null);
  React.useEffect(() => {
    const controller = new AbortController();
    let timer, cursor;
    setItems([]); setError(null);
    async function refresh() {
      try {
        const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
        const data = await api(`/api/riders/${riderId}/queue${query}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!data.unchanged) setItems(data.items);
        cursor = data.cursor;
        timer = setTimeout(refresh, 5000);
      } catch (err) {
        if (!controller.signal.aborted) setError(err); // Surface auth/network error; no blind retry.
      }
    }
    refresh();
    return () => { clearTimeout(timer); controller.abort(); };
  }, [api, riderId]);
  return { items, error };
}
```

Memoize api with React.useMemo from runtime local credentials; never use a bundled
administrator token. Render messages/notes with textContent or framework escaping, not HTML.
No logging request bodies/headers, bearer, raw input or confirmation URLs.

## Errors, retries and limitations

```json
{"error":{"code":"VERSION_CONFLICT","message":"Order changed; retrieve the latest version before updating.","details":[]}}
```

422 details contain location/message/type, not submitted private input. Use status/code/
field location, not exact prose. 401: missing/expired authorization; 403: role/local denial
or generic verification failure; 404: missing/out-of-scope/revoked link; 409: stale version,
lifecycle/review/COD conflict; 410: expired link; 423: locked; 429: wait Retry-After (60);
503: production disabled/configuration/database unavailable; 500: sanitized internal error.
Full code list is in API_CONTRACT. Network errors/preflight rejection/proxy HTML may have
no JSON. Distinguish connectivity errors from validation and review outcomes.

Use `version` from Order or `order_version` from queue/action for expected_version.
Rider availability uses the Rider profile version instead. On 409 reload and review current
state; do not silently repeat with a newer version. A recorded buyer/rider retry reuses the
same request UUID/body. Do not mint a new UUID on each network retry.

There is no production login, tenant auth, trusted geospatial dataset, live PostgreSQL
verification, real AI adapter, merchant onboarding API, trustworthy shop/items endpoint,
public deployment or frontend UI. These are transparent prerequisites/limits, not hidden
features. Health is liveness only, not a database/provider readiness check. No endpoint is
missing for the stated local workflows; shared public multi-user use still requires auth.
