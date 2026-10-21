# Phase 8A frontend integration preparation

This is a preparation and verification report, not a completed frontend integration.
No frontend source has been supplied. The supported local workflows already have backend
endpoints; no new backend module or access bypass was added.

## Base URL and contract

Normal development API origin: `http://127.0.0.1:8000`, without an `/api` suffix.
Interactive schemas: `/docs`; machine-readable schemas: `/openapi.json` and
[OPENAPI.json](OPENAPI.json). The isolated demo uses distinct dynamically allocated
loopback origins for each actor; use its actual role URLs, not an assumed port.

[API_CONTRACT.md](API_CONTRACT.md) describes full field constraints and lifecycle rules.
[FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md) has complete workflow notes and abridged JSON
for every response family. [FRONTEND_TEAM_SETUP.md](FRONTEND_TEAM_SETUP.md) covers Git,
frontend import and local startup. The endpoint inventory below is derived from live
FastAPI OpenAPI, including the request and success response schema names.

## Access arrangement

Health/stateless parsing require no token. Saved orders, users and riders require
`X-Dev-Access-Token`, a loopback peer, enabled local/test configuration and a server-bound
actor UUID. Merchant access is limited to its own orders; Dispatcher/Admin have local
management access; Rider is restricted to its own permitted operations. There is no
browser login, client role selector or merchant onboarding endpoint.

For now run frontend and backend on the same developer laptop. Supply its own generated
role token manually at runtime only, keep it in memory, and discard it when finished.
Never embed it in delivered JavaScript, frontend `.env` build variables, fixtures or HTML.
Never share the backend developer's token with a public website. The localhost helper
checks both the backend origin and browser origin; the backend checks the actual peer.
Different ports on the same laptop work with explicit CORS approval. Other computers
cannot use that laptop's `localhost`. Public/shared use needs proper authentication or
a reviewed authenticated BFF plus secure deployment; no shared remote endpoint is provided.
Production saved-order, rider and buyer APIs remain disabled regardless of enable flags.

Buyer access is separate: the private link allows only a minimal card; the last-four
check issues short-lived Bearer authorization for that link/order. It cannot access
dispatcher endpoints. Keep buyer bearer credentials only in memory, avoid third-party
scripts/analytics on the card, and prevent token URLs from entering logs/referrers/caches.

## Request and response examples

Examples containing angle-bracket values are templates: replace them with runtime IDs
and user selections. Response excerpts are explicitly abridged. Full validated responses
are in OpenAPI and [PHASE7_SAMPLE_RESPONSES.json](PHASE7_SAMPLE_RESPONSES.json).

```http
POST /api/orders/parse
Content-Type: application/json

{"raw_text":"လှိုင်မြို့နယ် ဗဟိုလမ်း COD ၂၅၀၀၀"}
```

This sample intentionally has no phone. Its response excerpt is:

```json
{"is_mock":false,"provider":"rules","address":{"customer_name":null,"phone_number":null,"township":"Hlaing","street":"ဗဟိုလမ်း","landmark":null,"building_floor_unit":null,"cod_amount":25000,"delivery_instructions":null,"time_window":null},"confidence":"RED","manual_review_required":true}
```

The full response includes `original_text`, `normalized_text`, normalization warnings,
`field_sources`, `validation_reasons`, `location_verification` and AI availability metadata.
Check actual provider/AI metadata; mock enrichment is not real model extraction. A
complete-looking address still cannot become GREEN without trusted location validation.

```http
POST /api/orders
X-Dev-Access-Token: <runtime local role credential>
Content-Type: application/json

{"merchant_id":"<merchant UUID>","structured":{"township":"Hlaing","street":"Demo street","cod_amount":"25000"}}
```

HTTP 201 response excerpt (this missing-phone fixture is RED):

```json
{"id":"<order UUID>","merchant_id":"<merchant UUID>","status":"DRAFT","version":1,"township":"Hlaing","customer_phone":null,"cod_amount":"25000","latitude":null,"longitude":null,"confidence_level":"RED","manual_review_required":true,"parsing_mode":"structured","ai_availability_status":"not_requested"}
```

Alternatively send `{merchant_id,raw_text}` with actual input. Exactly one of raw_text
or structured is required. Do not submit the whole parse response. Merchant IDs come
from protected `GET /api/users?role=Merchant` or local bootstrap/demo data.

Manual correction: `PATCH /api/orders/{order_id}` with
`{"expected_version":1,"floor":"2","delivery_instructions":"Call on arrival"}`.
It returns an updated Order including a new version and manual field provenance.
Status writes use `{"expected_version":<latest>,"status":"NEEDS_REVIEW"}`.
Use latest versions from responses; never hardcode them into the UI.

## Dispatcher workflow

1. Parse actual raw input and display missing/ambiguous fields, warnings and provenance.
2. Save with raw_text or structured data; retrieve/filter orders and correct editable fields.
3. Move DRAFT to NEEDS_REVIEW, ensure a valid registered phone, and generate a confirmation
   link. Response: `{link_id,confirmation_url,absolute_url,expires_at}` (201).
   `confirmation_url` is a frontend route `/confirm/<token>`, not the public API route.
4. Send the link manually through an existing trusted conversation. Review proposed changes
   through buyer-requests. For review PATCH use the history item's **id** as the path
   request_id, not its client idempotency UUID. Body:
   `{"expected_version":<latest>,"decision":"APPROVE","reason":"Reviewed buyer proposal"}`.
   Response: `{request_id,resolution:"APPROVE",order_version}`. Approval leaves NEEDS_REVIEW.
5. Confirm once validation/review allows; move CONFIRMED to READY_FOR_DISPATCH. For AMBER
   the dispatcher must explicitly send `acknowledge_unverified_location:true`. Unresolved
   buyer requests block readiness. COD must be known; zero is prepaid, null is unknown.
6. Assign an AVAILABLE rider with `{expected_version,rider_id,stop_sequence:1}`. HTTP 201
   returns `{assignment,order_status:"ASSIGNED",order_version}`. Use assignment endpoints
   for rider work. Generic ASSIGNED bookkeeping does not create a rider assignment.
7. Read events and assignment history. Unassign before start to process a later correction,
   return to review, then confirm/ready/reassign. On-road and terminal edits are restricted.

Confidence GREEN/AMBER/RED is separate from lifecycle. The normal progression is
DRAFT -> NEEDS_REVIEW -> optional AWAITING_CONFIRMATION -> CONFIRMED -> READY_FOR_DISPATCH
-> ASSIGNED -> OUT_FOR_DELIVERY -> DELIVERED/FAILED. See the contract for guarded branches.
Do not use location-reference to manufacture trust; it records a real operator attestation.

## Buyer verification and updates

1. `GET /api/confirm/{token}` returns only
   `{order_reference,shop_display_name:null,delivery_status,state,expires_at}`. No fabricated
   branding or item information. VERIFICATION_REQUIRED permits the check; LOCKED means
   contact the shop; VIEW_ONLY permits minimal post-delivery viewing.
2. `POST /api/confirm/{token}/verify` body `{"last_four":"<four ASCII digits>"}`.
   It returns `{access_token,token_type:"Bearer",expires_at}`. Never guess, prefill, or retry
   automatically. Three failed valid guesses lock the link; new sessions cannot bypass it.
3. `GET /api/confirm/{token}/details` with `Authorization: Bearer <buyer credential>` returns
   current address/pin/window/instructions and policy, with no full phone or customer name.
4. PATCH location with a fresh UUID, deliberate user coordinates and
   `initial_pin_acknowledged:true` when no trusted original pin exists:
   `{request_id,latitude:<selected>,longitude:<selected>,initial_pin_acknowledged:true}`.
   Coordinates must be finite, in range and at most seven decimal places. An initial pin
   is a review proposal, not independent township accuracy. No coordinates are fabricated.
5. PATCH response with `{request_id,action:"AVAILABLE"}`, or
   `{request_id,action:"INSTRUCTIONS",instructions:<user text>}`. RESCHEDULE requires
   `{request_id,action:"RESCHEDULE",time_window:{start:<ISO with offset>,end:<ISO with offset>}}`.
   LEAVE_WITH_SECURITY is also supported as a request. Unsupported policies/cutoff changes
   require review. Windows must span 30 minutes..8 hours, one Yangon date, with configured
   notice/horizon limits. Defaults: 15:00 Yangon cutoff, 2-hour notice, 7-day horizon.

Buyer action response excerpt:
`{request_id,decision:"REVIEW_REQUIRED",reason_codes:[...],order_status,confidence_level,
submitted_at,confirmed_at:null,resolution:null}`. HTTP 200 does not mean canonical dispatch
details changed. Only APPLIED/dispatcher-approved values reach rider queues. Buyer writes
stop at READY_FOR_DISPATCH. Default link life is 72 hours and session life 15 minutes;
new successful verification invalidates the previous session. Phone correction, revocation
and cancellation invalidate access. Eligible delivered links allow minimal viewing for
24 hours, without sensitive changes. Four digits plus a link are not proof of phone ownership.

## Rider queue and actions

Use the rider-bound instance and its own runtime token. `GET /api/riders/{rider_id}/queue`
returns `{rider_id,operational_status,cursor,unchanged,total,items,generated_at}`. Items have
assignment_id/order_id/status/order_version/stop_sequence, current delivery/contact notes,
township, COD, window, coordinates, navigation and confirmation/verification flags.
Only approved canonical updates are reflected. A buyer-confirmed pin is not independently
verified. `navigation_ready:false` and null URL mean no usable confirmed pin.

Order is deterministic: eligible/on-road status, confirmed window, dispatcher stop sequence,
then stable timestamps/IDs. This is not geographic route optimization.

Poll every five seconds while active without overlap. First request has no cursor; send the
last cursor on later requests. `unchanged:true` means preserve displayed items despite an
empty items array. `unchanged:false` means replace the entire list, including an empty list.
Abort polling when leaving the screen and refresh after mutations. This is REST polling.

Status PATCH bodies (each request gets its own UUID):

```javascript
const start = { request_id: crypto.randomUUID(), expected_version: item.order_version, action: "START" };
const delivered = { request_id: crypto.randomUUID(), expected_version: started.order_version,
  action: "DELIVERED", cod_collected: collectionConfirmedByRider };
const failed = { request_id: crypto.randomUUID(), expected_version: started.order_version,
  action: "FAILED", failure_reason: "CUSTOMER_UNAVAILABLE" };
```

START requires ASSIGNED and an AVAILABLE rider. Completion/failure requires OUT_FOR_DELIVERY.
Positive COD requires explicit true by default; do not automatically tick collection.
Response: `{request_id,assignment_id,order_id,rider_id,status,assignment_status,order_version,
cod_collected,failure_reason,updated_at}`. Successful completion removes the stop from the
next queue snapshot. Retrying the identical UUID/body is idempotent; a changed body conflicts.

## CORS and browser requests

Configure an exact origin array in private backend configuration, for example:

```dotenv
LANNPYA_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000"]
```

Restart the backend after configuration changes. The demo's `--frontend-origin` applies
only to its child processes. Origin includes scheme, host and port; localhost differs from
127.0.0.1. Serve over HTTP, not file://. Allowed preflights permit GET/POST/PATCH and
Content-Type, X-Dev-Access-Token, Authorization. Cookie credentials are disabled. OPTIONS
needs no token; the actual request still does. Retry-After is exposed. A rejected preflight
returns 400 text and usually appears as fetch TypeError. CORS is not authorization.

```javascript
// Public parse: no private token required.
const response = await fetch("http://127.0.0.1:8000/api/orders/parse", {
  method: "POST", credentials: "omit", cache: "no-store", redirect: "error",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ raw_text: rawTextFromForm }),
});
const data = await response.json();
if (!response.ok) throw new Error(data.error?.message ?? "Request failed");
```

Use the tested dependency-free [example helper](examples/lannpya-client.mjs) for JSON
errors, Retry-After, loopback development guarding and separated buyer credentials:

```javascript
import { createDevelopmentApi, createBuyerApi } from "./lannpya-client.mjs";
// Runtime variables only; no real credentials appear in this example.
const dispatcher = createDevelopmentApi({ baseUrl: localDispatcherBase, token: runtimeLocalToken });
const page = await dispatcher("/api/orders?page=1&page_size=20&confidence=AMBER");
const buyer = createBuyerApi({ baseUrl: matchingBuyerBackendBase, linkToken: tokenReadFromLink });
const card = await buyer.card();
await buyer.verify(lastFourFromForm);
const details = await buyer.details();
const proposedPin = { request_id: crypto.randomUUID(), latitude: selectedLatitude,
  longitude: selectedLongitude, initial_pin_acknowledged: true };
const proposal = await buyer.location(proposedPin); // Retain same body/UUID for network retry.
buyer.clear(); // Clear when leaving the buyer flow.
```

The import path assumes the developer copies or explicitly imports the docs example;
it is not an installed frontend package. React uses the same functions; memoize the
API instance and see the abortable queue hook in FRONTEND_HANDOFF.md. Display notes with
textContent/framework escaping. Do not log input, headers, private responses or link URLs.

## Common errors and field conventions

JSON error example:
`{"error":{"code":"VERSION_CONFLICT","message":"Order changed; retrieve the latest version before updating.","details":[]}}`.

| HTTP | Meaning / handling |
| --- | --- |
| 401 | Missing/expired development or buyer authorization; verify the matching local role/session |
| 403 | Role/local-only denial or generic last-four failure; do not retry guesses |
| 404 | Missing/out-of-scope record, malformed UUID route or invalid/revoked link |
| 409 | Stale version, lifecycle/review/COD/idempotency conflict; reload and review before retry |
| 410 / 423 | Expired / locked link; contact shop for a new eligible link |
| 422 | Malformed JSON, missing/extra/invalid fields; details give location/message/type without private input |
| 429 | Rate limited; honor Retry-After (currently 60 seconds) |
| 500 / 503 | Sanitized internal error / disabled config or unavailable database; do not expose internals |

Network errors and preflight/proxy text may have no JSON. Use HTTP status and error.code,
not exact message wording. Paginated endpoints return `{items,total,page,page_size}`;
page >=1, page_size 1..100 (default 20). Users returns an array, queue a full snapshot.
Order search q is a nonblank literal substring of at most 100 characters. Filters combine.
Parse.phone_number maps to Order.customer_phone; Parse.time_window maps to
Order.delivery_time_window; Parse.confidence maps to Order.confidence_level.
Parse COD is integer/null; persisted and queue COD is an exact digit string/null.
Coordinates in typed output are decimal strings/null. Null means unknown, never zero.
UTC timestamps are ISO 8601. Order updates need version; queue actions use order_version;
rider availability uses the separate rider profile version. Tolerate additive fields.

## Recommended integration order

1. Import frontend on its feature branch; confirm its origin/start command and buyer routing.
2. Health, public parsing, error display, field-source/review UI and CORS.
3. Local runtime role access, merchant lookup, order save/list/detail/correction/history.
4. Buyer link/card/verification/details, pin proposals and availability/reschedule review UI.
5. Dispatcher review, confirm/ready, rider selection/assignment and history.
6. Rider queue, cursor polling, navigation, START/DELIVERED/FAILED and explicit COD confirmation.
7. Actual browser/mobile workflow checks with synthetic data. Plan production authentication
   before connecting a shared online UI or real customer information.

## Phase 8A verification and repository audit

Verified locally on 2026-10-21:

- Branch `main`, origin `https://github.com/ZawLwinHtoo/lannpya-ai.git`; fetch succeeded.
  Initial tree clean; main and origin/main both at `a030097`, zero ahead/behind. One reachable
  commit was inspected. `frontend/` has only its placeholder. No Git conflicts were found.
- All 103 tracked files and reachable history inspected for sensitive filenames, common
  credential signatures and exact matches against 10 locally discovered private values.
  No matches found. `.env.example` contains placeholders, not live credentials. Local
  `.env`, backend/data, virtual environment and databases are ignored. Synthetic test
  phone strings exist in test fixtures; they must never be contacted as real customers.
  This is a bounded audit, not a guarantee that every possible secret format was detected.
- Added ignore coverage for alternate venv folders, temporary/editor files, package-manager
  logs and private_access.json outside its usual ignored demo directory. Ignore rules do
  not remove an already tracked secret. Any later discovery requires revocation/rotation;
  deleting the current file alone does not undo exposure. History was not rewritten.
- Live OpenAPI equals docs/OPENAPI.json: 29 operations. Reviewed actual routes, Pydantic
  schemas, access dependencies and lifecycle; the existing handoff covers all operations.
  API_CONTRACT uses shorter `{id}` aliases for some paths; these mean the same runtime UUIDs.
- Complete Python suite: **423 passed in 49.34 seconds**. JavaScript helper: **4 passed**.
  `pip check`: no broken requirements. Ruff lint passed; format check: **71 files formatted**.
- Real HTTP isolated demo: **68 cases passed**, including approved/rejected CORS preflights,
  unauthorized access rejection and merchant/buyer/dispatcher/rider flow. Servers stopped;
  reopened storage retained 5 orders, 3 buyer requests, 3 assignments, 4 action receipts,
  32 events and 3 links. No paid service or production database was contacted. Existing
  tracked sample responses were preserved; this verification used a fresh ignored database.
- No application/schema behavior was changed. Documentation and ignore rules are the only
  preparation edits. No commit, push, merge, deployment, invitation or permission change.

Local integration can begin immediately after the frontend import. It is not yet integrated
or browser-verified. Remaining decisions: frontend source/start command/origin/buyer route,
GitHub write access if needed, and local versus authenticated shared-demo scope. Production
auth, live PostgreSQL validation, secure deployment and real-data privacy protections are
public-demo prerequisites. AI stays mocked and trusted geospatial data is unavailable;
do not advertise real model extraction or automatic GREEN verification.

## Current endpoint inventory

The following table names actual Pydantic input/output schemas. A dash means no JSON body.
Path placeholders are runtime values. Success responses are JSON; consult OpenAPI for all
properties and constraints. Access: Public = stateless; Local = role-scoped development
access; Link = private link capability; Buyer = link plus short-lived buyer bearer.

| Method | Endpoint | Access | JSON request schema | Success schema |
| --- | --- | --- | --- | --- |
| GET | `/health` | Public | - | 200 HealthResponse |
| POST | `/api/orders/parse` | Public | ParseRequest | 200 ParseResponse |
| POST | `/api/orders` | Local | CreateOrder | 201 OrderResponse |
| GET | `/api/orders` | Local | - | 200 OrderPage |
| GET | `/api/orders/{order_id}` | Local | - | 200 OrderResponse |
| PATCH | `/api/orders/{order_id}` | Local | CorrectOrder | 200 OrderResponse |
| PATCH | `/api/orders/{order_id}/status` | Local | ChangeStatus | 200 OrderResponse |
| GET | `/api/orders/{order_id}/events` | Local | - | 200 EventPage |
| GET | `/api/users` | Local | - | 200 UserResponse[] |
| POST | `/api/orders/{order_id}/confirmation-link` | Local | - | 201 LinkResult |
| POST | `/api/orders/{order_id}/confirmation-link/revoke` | Local | - | 200 RevocationResult |
| POST | `/api/orders/{order_id}/location-reference` | Local | SetLocationReference | 201 LocationReferenceResult |
| GET | `/api/orders/{order_id}/buyer-requests` | Local | - | 200 BuyerHistoryPage |
| PATCH | `/api/orders/{order_id}/buyer-requests/{request_id}` | Local | ReviewBuyerRequest | 200 BuyerReviewResult |
| GET | `/api/confirm/{token}` | Link | - | 200 BuyerCardResult |
| POST | `/api/confirm/{token}/verify` | Link | VerifyBuyer | 200 BuyerAuthorizationResult |
| GET | `/api/confirm/{token}/details` | Buyer | - | 200 BuyerDetailsResult |
| PATCH | `/api/confirm/{token}/location` | Buyer | BuyerLocation | 200 BuyerActionResult |
| PATCH | `/api/confirm/{token}/response` | Buyer | BuyerResponse | 200 BuyerActionResult |
| POST | `/api/riders` | Local | RiderCreate | 201 RiderResponse |
| GET | `/api/riders` | Local | - | 200 RiderPage |
| GET | `/api/riders/{rider_id}` | Local | - | 200 RiderResponse |
| PATCH | `/api/riders/{rider_id}` | Local | RiderPatch | 200 RiderResponse |
| GET | `/api/riders/{rider_id}/queue` | Local | - | 200 QueueResponse |
| POST | `/api/orders/{order_id}/assign` | Local | AssignOrder | 201 AssignmentResult |
| POST | `/api/orders/{order_id}/unassign` | Local | UnassignOrder | 200 AssignmentResult |
| PATCH | `/api/orders/{order_id}/assignment` | Local | SequencePatch | 200 AssignmentResult |
| GET | `/api/orders/{order_id}/assignments` | Local | - | 200 AssignmentPage |
| PATCH | `/api/riders/{rider_id}/deliveries/{order_id}/status` | Local | DeliveryAction | 200 ActionResult |
