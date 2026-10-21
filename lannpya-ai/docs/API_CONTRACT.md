# LannPya AI — frontend API contract (Phase 7)

Local base URL: `http://127.0.0.1:8000`. JSON over REST, UTF-8.
Interactive docs: `/docs`; OpenAPI schema: `/openapi.json`.
Frontend entry point: [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md); exported schemas:
[OPENAPI.json](OPENAPI.json); isolated demo: [DEMO_GUIDE.md](DEMO_GUIDE.md).
Health and stateless parsing require no token. Buyer cards use the separate capability
and verification flow below. Saved orders and user lookup require
the local development access mechanism documented below. Production authentication
is not implemented; production order management fails closed.

## GET /health

No request body. HTTP 200:

```json
{"status":"ok","service":"LannPya AI"}
```

This reports that the application responds; it checks no database or external provider.

## POST /api/orders/parse

Header: `Content-Type: application/json`. Request object has exactly one required field:

| Field | Type | Rules |
| --- | --- | --- |
| raw_text | string | 1–10,000 original characters; Burmese, Myanglish, and English accepted; whitespace-only rejected |

Extra fields, empty/whitespace strings, missing values, and non-string values return 422.

```json
{"raw_text":"၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀"}
```

HTTP 200, existing response keys shown below. The response also includes the additive
metadata fields described in the next section. Full actual responses are recorded in
[PHASE2_SAMPLE_RESPONSES.json](PHASE2_SAMPLE_RESPONSES.json).

```json
{
  "is_mock": false,
  "provider": "rules",
  "notice": "Deterministic local extraction only. No AI call, saved order, geocoding, or delivery pin verification.",
  "address": {
    "customer_name": null,
    "phone_number": "09791234567",
    "township": "Hlaing",
    "street": "ဗဟိုလမ်း",
    "landmark": null,
    "building_floor_unit": null,
    "cod_amount": 25000,
    "delivery_instructions": null,
    "time_window": null
  },
  "confidence": "AMBER",
  "validation_reasons": [
    {"code":"LOCATION_UNVERIFIED","message":"Phone format is valid and township matched, but location requires buyer or dispatcher confirmation. Extracted landmarks are not geospatial verification."},
    {"code":"LOCATION_DATASET_UNAVAILABLE","message":"No trusted street/landmark catalog is configured; GREEN is disabled."}
  ]
}
```

| Response field | Type / meaning |
| --- | --- |
| is_mock | boolean; false for real rules extraction, true only in explicit mock mode |
| provider | string; `rules` by default, `mock` in legacy mock mode; this does not select an AI model |
| notice | string explaining processing limitations |
| address | object with all nine keys shown above |
| address.cod_amount | nonnegative integer whole MMK or null |
| other address fields | string or null; phone is a string to preserve leading zeroes |
| confidence | enum `GREEN`, `AMBER`, `RED`; deterministic triage, never a numeric percentage |
| validation_reasons | nonempty array of `{code: string, message: string}` |

Null means unknown, missing, invalid, or ambiguous; inspect field_sources. Never treat
null COD as zero. No coordinates, numeric confidence, order ID, or saved order is produced.

## Additive Phase 2 response fields and compatibility

The endpoint, request key, existing response keys, address key names/types, status codes,
error envelope, and fetch usage remain stable. Default behavior now extracts actual input
instead of returning fixed mock data. Clients should tolerate additional response keys.

| New response field | Type / meaning |
| --- | --- |
| original_text | exact unmodified submitted string, including leading/trailing whitespace |
| normalized_text | string after local encoding handling, NFC, and Myanmar-to-ASCII digit normalization |
| normalization | `{encoding, zawgyi_converted, digits_normalized, warnings}` |
| field_sources | object keyed by all nine address fields; source schema below |
| location_verification | `{status: "unverified" or "verified", dataset: string or null, source_url: string or null}` |

`normalization.encoding` is `non_myanmar`, `unicode_or_undetermined`, `zawgyi`, or `ambiguous`.
`warnings` contains `{code,message}` objects. Successful Zawgyi conversion carries
`ZAWGYI_CONVERSION_REVIEW`. Uncertain encoding is retained without conversion and flagged
`ENCODING_UNCERTAIN`; failed conversion retains text and flags `ZAWGYI_CONVERSION_FAILED`.
An encoding label is a local detector result, not a language or address confidence score.

Each `field_sources` entry contains:

| Field | Type / meaning |
| --- | --- |
| method | `rule`, `dictionary`, `not_extracted`, or `ai` |
| status | `extracted`, `missing`, `ambiguous`, or `invalid` |
| rule | rule identifier string or null |
| evidence | array of `{value: string/integer/null, matched_text: string, start: integer, end: integer}` |
| verified | boolean; true only for a trusted township-specific street/landmark catalog match |
| dataset | dictionary/catalog version or null; dictionary membership alone is not geospatial verification |
| provider | public AI adapter identifier or null; present on AI-filled fields or AI suggestions |
| requires_review | boolean; AI suggestions always require review |
| ai_suggestion | nullable string offered for review when deterministic evidence was ambiguous/invalid; the address field stays unchanged |

Evidence offsets index **normalized_text**, using Unicode code points and an exclusive end.
They are not offsets into original_text because normalization can change text length/order.
In JavaScript, slice `Array.from(normalized_text)` using these offsets (emoji may occupy
two UTF-16 units). Ambiguous candidates remain in evidence while the address value stays null.
Floor and unit evidence may be combined into one semicolon-separated output string.
Metadata and original text can contain personal data; do not log them or forward them to AI.

## Deterministic parsing and triage rules

- Phone: local Myanmar numbering metadata validates mobile ranges/lengths; accepts ASCII
  or Burmese digits, spaces/hyphens, domestic 09 and +95/959 formats. Output is domestic
  format. Metadata validity does not prove ownership or reachability. Conflicting numbers
  remain null; duplicate representations of the same number are accepted.
- COD: explicit `COD`, `cash on delivery`, `ငွေချေ`, `ကျသင့်ငွေ`, `ကောက်ခံငွေ`, `ကုန်ဖိုး`,
  or amount followed by `ကောက်ခံရန်`. Whole MMK only, standard comma grouping, maximum
  1,000,000,000 MMK for automatic extraction. No inference from time, floor, order ID,
  bare price, or delivery fee. Decimals, k/lakh-style shorthand, negatives, phone overlaps,
  invalid values, and conflicting amounts require confirmation. Missing COD is optional.
- Township: controlled initial 33-name Yangon list and explicit aliases; case-insensitive
  Latin matching, longest overlapping alias wins. Unknown or competing township names
  require confirmation. A road named Insein Road is not itself a township mention.
- Other fields: explicitly labelled names and bounded street, landmark, floor/unit,
  instruction, and time patterns. Arbitrary prose/Myanglish is not generally understood.
  Use commas, Burmese commas, semicolons, or newlines to separate labelled fields.
- GREEN: valid mobile format + matched township + unique trusted catalog street/landmark
  match scoped to that township + no unresolved ambiguity or normalization warning.
- AMBER: valid phone and township, with unverified/ambiguous location or conversion review.
- RED: missing/invalid/ambiguous phone or township, conflicting/invalid explicit COD,
  uncertain encoding, or conversion failure. Dispatcher/buyer confirmation is required.

**No trusted street/landmark dataset was supplied. Default deployment intentionally
returns AMBER or RED, never GREEN.** A server-injected reviewed `LocationCatalog` enables
the GREEN rule; synthetic test catalog entries are not installed as real locations.
There are no map calls or invented coordinates. Mentioning a landmark never verifies it.

`LANNPYA_PARSER_MODE=mock` preserves the fixed Phase 1 demo behavior with `is_mock=true`,
`provider=mock`, all null address fields, RED, and original mock reasons. The new metadata
fields default to null/empty/unverified in that mode. Rules mode does not call any AI
provider. No external AI provider is integrated.

## Phase 3 hybrid assistance and graceful degradation

Default mode is now `LANNPYA_PARSER_MODE=hybrid`. It retains actual Phase 2 extraction,
then optionally attempts sanitized address enrichment through a provider-neutral interface.
`rules` still provides the complete Phase 2 path, and `mock` still provides the Phase 1
fixed demo. Endpoint URLs, request schema, address fields/types, error envelope, and CORS
remain unchanged. The top-level `provider` remains `rules` in hybrid mode and `is_mock`
remains false because primary parsing is real. AI availability is reported separately.

New additive top-level fields:

| Field | Meaning |
| --- | --- |
| ai | AI availability/provenance object described below |
| manual_review_required | boolean; true for RED/AMBER, AI-filled/suggested fields, or an AI failure |

Example `ai` object for the installed local mock (no invented values):

```json
{
  "status": "mock",
  "provider": "mock",
  "is_mock": true,
  "attempted": true,
  "message": "Mock AI adapter: AI-derived fields are unavailable; no simulated values were merged.",
  "retry_after_seconds": null,
  "applied_fields": [],
  "suggested_fields": []
}
```

| ai field | Type / meaning |
| --- | --- |
| status | enum listed below; use this rather than matching message text |
| provider | public adapter identifier or null if no adapter was used |
| is_mock | boolean identifying mock enrichment; separate from the primary result's is_mock |
| attempted | boolean; true only when the adapter was invoked |
| message | non-sensitive human-readable availability/review explanation |
| retry_after_seconds | nullable integer, 1–86,400; rate-limit advice, not an automatic retry |
| applied_fields | array of enrichment field names filled from grounded suggestions |
| suggested_fields | array of field names with review-only ai_suggestion values |

Statuses:

| Status | Meaning |
| --- | --- |
| not_requested | rules/legacy mode, no needed fields, or no sufficiently safe/useful address fragment |
| mock | local mock invoked; AI-derived values unavailable and no simulated fields merged |
| disabled | configuration disables assistance; no adapter call |
| available | response passed schema/grounding checks; suggestions require human review; currently demonstrated only by injected local test adapters |
| timeout | configured AI timeout or adapter-reported transport timeout |
| rate_limited | provider reports throttling; deterministic results retained |
| invalid_response | malformed/oversized JSON, duplicate keys, schema violation, forbidden fields, or ungrounded evidence |
| unavailable | provider failure, invalid adapter metadata, or an external adapter blocked by Phase 3 policy |
| privacy_blocked | uncertain/failed encoding prevents safe preparation of model input |

Valid parse requests still return **HTTP 200 when AI fails**. Show deterministic fields,
triage reasons, and AI availability; do not treat absent AI as loss of the whole order.
Legacy mock-provider exceptions retain their original HTTP 502 behavior. Invalid client
requests still return 422. AI failures do not fabricate replacements for missing data.

The enrichment schema permits only `landmark`, `building_floor_unit`, and
`delivery_instructions`. Each suggestion must quote a unique unchanged span from a
sanitized input fragment, with its value contained in that quote. All suggestions are
validated before any merge. Extra fields—including phones, COD, townships, streets,
names, confidence, and coordinates—reject the AI response. Valid deterministic fields
cannot be overwritten. Competing deterministic evidence remains ambiguous and null;
AI may offer a labelled suggestion for dispatcher review. Mock suggestions are never merged.

AI-filled fields have `method=ai`, `provider`, `requires_review=true`, and normalized-text
evidence. They remain unverified even if a catalog name happens to match. Their presence
blocks automatic GREEN. Triage remains deterministic, with no numeric confidence.
An independently verified deterministic street can retain GREEN on AI failure, but
`manual_review_required` is true and the AI failure is explicit. Default catalog is still
empty, so the installed app produces no GREEN results.

The frontend can resubmit corrected `raw_text` to this stateless endpoint, or create and
correct persisted orders through the protected Phase 4 endpoints below. The parse endpoint
does not save records. Treat source/review metadata as server output, not writable fields
in either request contract; client-supplied verification flags are never accepted.

Provider settings (server only): `LANNPYA_AI_PROVIDER=mock` or `disabled`,
`LANNPYA_AI_TIMEOUT_SECONDS=3.0` (positive, maximum 30), and
`LANNPYA_AI_MAX_INPUT_CHARS=2000` (128–4,000, address-fragment characters).
External adapters are blocked before invocation. No API key or paid call is used.
The server removes phone/name/COD evidence, repeated reliably labelled names, long numeric
sequences, emails, URLs, and sensitive labelled clauses before preparing a small allowlist
of useful address fragments. It does not send the full raw order, source metadata, or
already extracted notes/units unnecessarily. This is conservative minimization, not a
guarantee that free-text addresses contain no PII. Unlabelled names inside address prose
can remain, so real external activation requires a separate privacy review.

See [Phase 3 verification](PHASE3_VERIFICATION.md) and
[actual sample responses](PHASE3_SAMPLE_RESPONSES.json). Injected test-double scenarios
in the latter are explicitly labelled and do not represent real AI model calls.

## Error contract

Application JSON errors have this envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {"location":["body","raw_text"],"message":"Field required","type":"missing"}
    ]
  }
}
```

| Status | code | Meaning |
| --- | --- | --- |
| 422 | VALIDATION_ERROR | Invalid body or malformed JSON; details identify fields |
| 502 | AI_PROVIDER_ERROR | Legacy mock-provider path failed or returned invalid/unsupported output |
| 404 / 405 | HTTP_ERROR | Unknown path / unsupported HTTP method |
| 500 | INTERNAL_ERROR | Unexpected server failure |

`details` is empty for non-validation errors. Locations contain strings and/or integers.
Do not depend on exact validation message wording; use status/code/location. Submitted
values and private upstream details are omitted. Browser CORS failures and network/proxy
errors may not have this JSON envelope; handle those separately. CORS preflight rejection
returns middleware HTTP 400 text, not the application JSON error format.

## JavaScript integration (vanilla or any framework)

```javascript
const API_BASE = "http://127.0.0.1:8000";

async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error(`Health check failed (${response.status})`);
  return response.json();
}

async function parseOrder(rawText) {
  const response = await fetch(`${API_BASE}/api/orders/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message ?? `HTTP ${response.status}`);
    error.code = data.error?.code;
    error.details = data.error?.details ?? [];
    throw error;
  }
  return data; // Render with textContent; show notice and a mock badge only if is_mock.
}

// Catch fetch/network errors and display an appropriate connectivity message in your UI.
```

## CORS for local development

Serve the frontend over HTTP. In backend environment settings, set a JSON array:

```dotenv
LANNPYA_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5500"]
```

Restart the backend after configuration changes. Origins include scheme, host, and port;
`localhost` and `127.0.0.1` differ. Do not include a path or trailing slash. Defaults:
`http://localhost:5173`, `http://localhost:3000`, `http://localhost:5500`,
`http://127.0.0.1:5500`. GET/POST/PATCH, Content-Type, Authorization and X-Dev-Access-Token are allowed for browser CORS
requests; preflight OPTIONS is handled automatically. Cookie credentials are disabled.
API URLs stay the same regardless of the frontend framework.
Retry-After is exposed to JavaScript. CORS also wraps sanitized unexpected-error responses
so approved origins can read JSON failures. Preflight never grants private data access.

## Phase 4: local order management access

All endpoints below require `X-Dev-Access-Token: <private local token>` on every request.
They work only when `LANNPYA_ENVIRONMENT=local` or `test`,
`LANNPYA_ORDER_MANAGEMENT_ENABLED=true`, and the actual connecting socket peer is loopback.
Set `LANNPYA_DEV_ACCESS_TOKEN` (at least 32 characters) and `LANNPYA_DEV_ACTOR_ID` in the
ignored backend `.env`. The bootstrap script has already configured this checkout and
created synthetic local dispatcher/merchant profiles. Never commit the token or put it
in a public frontend build. For local development, enter it at runtime and hold it only
in memory. This single token represents the server-configured actor, not a login system.
Client identity/role headers cannot select another actor. Do not expose this development
server through a tunnel or reverse proxy. Use `127.0.0.1` for the backend listener.

Merchant actors can create/list/read/correct only their own orders. Dispatcher and Admin
actors can manage local orders across merchants. Rider actors cannot access these order/user
APIs; Phase 6 adds separate rider APIs restricted to their own profile and queue.
Cross-merchant order lookup returns the same 404 as a missing order. Production configuration
always returns 503 for order management, even if its enable flag is true; no database is
opened in that configuration. All `/api/orders*` and `/api/users*` responses use
`Cache-Control: no-store`. CORS permits the token header but does not authorize requests.

## GET /api/users

Protected local lookup to obtain existing merchant IDs; no HTTP user creation is provided.
Optional `role=Merchant|Dispatcher|Rider|Admin`, `limit=1..100` (default 100).
Response 200: array of `{id, name, email, role, created_at, updated_at}`.
Merchants see only their own user profile; dispatchers/admins can see local profiles.
Use `GET /api/users?role=Merchant` to populate a local merchant selector.

## POST /api/orders

Protected. Response **201** is a saved `Order` object, described below. Supply an existing
merchant UUID and **exactly one** of `raw_text` or `structured`. Unknown fields are rejected.
All new records start at **DRAFT**, independent of confidence.

```json
{"merchant_id":"<merchant UUID>","raw_text":"09791234567, Hlaing, Baho Road, COD 25000"}
```

`raw_text` has the same 1..10,000 character/nonblank rules as `/parse`, is retained exactly,
and is normalized and parsed by the existing rules/hybrid pipeline. Phone/COD remain
deterministic. AI unavailability preserves deterministic results and allows saving. Even
when legacy parser mode is `mock`, persisted raw orders use real rules, never the fixed demo.
Oversized extracted fields exceeding storage limits return 422 rather than truncating.

Alternatively:

```json
{
  "merchant_id":"<merchant UUID>",
  "structured":{
    "customer_phone":"09791234567",
    "township":"Hlaing",
    "street":"Baho Road",
    "floor":"2",
    "cod_amount":"25000"
  }
}
```

Structured input requires at least one non-null editable field. Its original/normalized
messages are null, parsing mode is `structured`, and AI status is `not_requested`.
Supplied structured fields are marked manual correction, with no fabricated raw message.
Incomplete orders can be saved as RED drafts for correction.

## Editable fields and validation

The same editable fields apply inside `structured` and at the top level of correction PATCH:

| Field | Accepted value |
| --- | --- |
| customer_name | null or nonblank string, at most 200 characters |
| customer_phone | null or one valid Myanmar mobile number; Unicode digits/international form normalize to domestic string; at most 40 input characters |
| township | null or one supported controlled Yangon township alias (canonical name returned) |
| street / landmark | null or nonblank string, at most 1,000 characters each |
| building / floor / unit | null or nonblank string, limits 500 / 100 / 100 |
| cod_amount | null, JSON integer, or ASCII digit string, whole MMK 0..1,000,000,000; floats, booleans, negatives, commas and fractions rejected |
| latitude / longitude | both supplied together or both cleared to null; finite decimal strings/numbers, ranges -90..90 / -180..180, at most 7 decimal places |
| delivery_instructions | null or nonblank string, at most 2,000 characters |
| delivery_time_window | null or nonblank string, at most 500 characters |

Manual strings are trimmed. Omitted fields stay unchanged on PATCH; explicit null clears.
Coordinates are manually supplied data, never geospatial proof. Clients cannot set
confidence, sources, AI metadata, original/normalized messages, merchant, status, IDs,
timestamps or version through ordinary correction fields.

## Saved Order response

All fields below are present; unknown nullable values are null. This response is separate
from the unchanged `/parse` response (`phone_number` there becomes `customer_phone` here).

| Fields | JSON type / meaning |
| --- | --- |
| id, merchant_id | UUID strings |
| customer_name, customer_phone | nullable strings |
| original_message, normalized_message | nullable strings; original preserved for raw creation |
| township, street, landmark | nullable strings |
| building, floor, unit, building_floor_unit | nullable strings; combined parser text is retained without guessing a split |
| latitude, longitude | nullable decimal strings; never fabricated |
| cod_amount | nullable exact whole-MMK **digit string**, e.g. `"25000"`; `/parse` still returns an integer |
| delivery_instructions, delivery_time_window | nullable strings |
| confidence_level | GREEN / AMBER / RED, independent of lifecycle status |
| confidence_reasons | array of `{code, message}` |
| parsing_mode | rules / hybrid / structured |
| ai_availability_status | creation-time status, e.g. mock / disabled / timeout / rate_limited / unavailable / invalid_response / not_requested |
| field_sources | JSON keyed by persisted field names; parser provenance retained, manual changes use `method: "manual_correction"`, actor_id, corrected_at and original_source |
| parsing_metadata | normalization, location_verification, and AI details from creation where applicable; clients should tolerate additive keys |
| manual_review_required | boolean |
| status | lifecycle enum below |
| version | integer >=1; send latest value as expected_version for both PATCH endpoints |
| created_at, updated_at | UTC ISO 8601 timestamps |

Unedited deterministic fields retain source evidence. Manual location text is not verified
merely by editing it. Buyer-confirmation provenance is written by the implemented buyer
workflow; no client can submit provenance claims. Splitting building/floor/unit manually replaces
the combined display value; its original extraction source remains in provenance.
See [actual full HTTP responses](PHASE4_SAMPLE_RESPONSES.json), generated with synthetic
verification data. Do not reuse sample UUIDs as IDs from your own local database.

## GET /api/orders and GET /api/orders/{order_id}

Both protected. Detail returns an Order object (200), or 404 for unknown/out-of-scope IDs.
Malformed path UUIDs return 404. Body UUID validation failures return 422.

List query parameters:

| Parameter | Rule |
| --- | --- |
| page | integer 1..1,000,000; default 1 |
| page_size | integer 1..100; default 20 |
| status | exact lifecycle enum, optional |
| confidence | GREEN / AMBER / RED, optional |
| q | optional nonblank string, at most 100 characters; literal substring across customer name, phone, township, street and landmark |

Filters combine with AND and actor ownership scope. Newest creation first, UUID tie-break.
Response: `{"items":[<Order>,...],"total":42,"page":1,"page_size":20}`.
Out-of-range empty pages return empty items with the filtered total. Search is basic
database substring matching, not linguistic Burmese search; Unicode input is supported.
Query strings are stripped from standard Uvicorn access logs; avoid private search URLs
in browser history or shared logs.

## PATCH /api/orders/{order_id}

Protected. Requires the current `expected_version` and at least one editable field:

```json
{"expected_version":1,"floor":"2","unit":"B","landmark":"behind red gate"}
```

Response 200: updated Order. Recalculate deterministic confidence for the current values;
AI cannot overwrite validated phone/COD, and stale trusted location claims are invalidated.
No new AI call occurs. An actual correction increments version/updated_at, records manual
sources and an ORDER_CORRECTED event. A validated same-value no-op has no new event/version;
same-value confirmation of an AI/review-required field does replace its provenance.
Editing is allowed in DRAFT, NEEDS_REVIEW, AWAITING_CONFIRMATION, CONFIRMED,
READY_FOR_DISPATCH and FAILED. Any actual correction outside DRAFT resets status to
NEEDS_REVIEW and records that change in its correction event. Assigned, on-road and terminal
orders reject correction with 409. Reload latest Order after a 409 VERSION_CONFLICT;
review current data before resubmitting rather than blindly retrying.

## PATCH /api/orders/{order_id}/status

Protected, response 200: updated Order. Requires exact status and latest expected_version:

```json
{"expected_version":2,"status":"NEEDS_REVIEW"}
```

Allowed transitions:

| From | Allowed next statuses |
| --- | --- |
| DRAFT | NEEDS_REVIEW, CANCELLED |
| NEEDS_REVIEW | AWAITING_CONFIRMATION, CONFIRMED, CANCELLED |
| AWAITING_CONFIRMATION | NEEDS_REVIEW, CONFIRMED, CANCELLED |
| CONFIRMED | NEEDS_REVIEW, READY_FOR_DISPATCH, CANCELLED |
| READY_FOR_DISPATCH | NEEDS_REVIEW, ASSIGNED, CANCELLED |
| ASSIGNED | READY_FOR_DISPATCH, OUT_FOR_DELIVERY, CANCELLED |
| OUT_FOR_DELIVERY | DELIVERED, FAILED |
| FAILED | NEEDS_REVIEW, CANCELLED |
| DELIVERED / CANCELLED | terminal; no next status |

Merchants can target only NEEDS_REVIEW, AWAITING_CONFIRMATION, CONFIRMED, CANCELLED,
subject to the transition table. Operational transitions require Dispatcher/Admin.
CONFIRMED and READY_FOR_DISPATCH require a valid phone, matched township and non-RED triage.
CONFIRMED can be an operator assertion or the verified buyer AVAILABLE action described
below. It does not prove phone ownership or geospatial accuracy.

There is no trusted location dataset in this installation, so GREEN remains unavailable.
Dispatcher/Admin must explicitly send `"acknowledge_unverified_location":true` when
transitioning an AMBER order to READY_FOR_DISPATCH. This is recorded in the event and
does not change confidence or prove coordinates. Each successful transition increments
version and atomically records STATUS_CHANGED. Invalid/repeated transitions return 409.
Use the new assignment APIs below for real rider work. The original generic ASSIGNED
transition remains bookkeeping only and does not invent an assignment or populate a queue.
Generic DELIVERED now also requires explicit `cod_collected:true` for positive COD under
the default policy (409 COD_CONFIRMATION_REQUIRED otherwise). Null COD requires review;
zero means explicitly prepaid. This is a new completion precondition for earlier clients.
An optional strict boolean cod_collected is accepted only with DELIVERED and is recorded
in event metadata and parsing_metadata.delivery_completion for these legacy status updates.
For orders with actual assignments, generic start/deliver/fail transitions are rejected;
use rider actions so assignment state, events and COD confirmation remain consistent.

## GET /api/orders/{order_id}/events

Protected, same ownership rules as detail. `page` and `page_size` use list limits/defaults.
Response 200: `{"items":[<Event>,...],"total":3,"page":1,"page_size":20}`.
Events are chronological (created_at then UUID), with:
`id`, `order_id`, `event_type` (ORDER_CREATED / ORDER_CORRECTED / STATUS_CHANGED),
`previous_status` (nullable for creation), `new_status`, `metadata`, `created_at`.
Phase 5 adds BUYER_LINK_CREATED, BUYER_LINK_REVOKED, BUYER_SECURITY, BUYER_LOCATION,
BUYER_RESPONSE, LOCATION_REFERENCE and BUYER_REQUEST_REVIEWED event types.
Metadata contains actor ID, changed field names, parsing mode or location acknowledgement
where relevant; no customer field values. This history is not a complete old/new-value audit.

## Additional order-management errors

The earlier `{error:{code,message,details}}` envelope also applies here. Non-validation
details are empty; never rely on private database error text.

| HTTP | Codes / meaning |
| --- | --- |
| 401 | DEV_ACCESS_REQUIRED: missing/incorrect local token |
| 403 | LOCAL_ACCESS_ONLY, DEV_ACTOR_UNAVAILABLE, ROLE_FORBIDDEN, MERCHANT_SCOPE_FORBIDDEN |
| 404 | ORDER_NOT_FOUND, or HTTP_ERROR for invalid path/UUID |
| 409 | VERSION_CONFLICT, ORDER_NOT_EDITABLE, INVALID_STATUS_TRANSITION, ORDER_VALIDATION_REQUIRED, LOCATION_ACKNOWLEDGEMENT_REQUIRED, DATABASE_CONFLICT |
| 422 | VALIDATION_ERROR, INVALID_MERCHANT, ORDER_FIELD_TOO_LONG |
| 503 | ORDER_MANAGEMENT_DISABLED, DEV_ACCESS_NOT_CONFIGURED, DATABASE_UNAVAILABLE |

## JavaScript saved-order integration

This works with vanilla JavaScript, React or Next.js. Token below is runtime local input,
never a bundled constant or publicly deployed environment variable.

```javascript
async function ordersApi(path, token, { method = "GET", body } = {}) {
  const response = await fetch(`http://127.0.0.1:8000/api${path}`, {
    method,
    cache: "no-store",
    headers: {
      "X-Dev-Access-Token": token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message ?? `HTTP ${response.status}`);
    error.status = response.status;
    error.code = data.error?.code;
    error.details = data.error?.details ?? [];
    throw error;
  }
  return data;
}

async function localOrderExample(token, rawText) {
  const merchants = await ordersApi("/users?role=Merchant", token);
  if (!merchants.length) throw new Error("No local merchant available");
  const order = await ordersApi("/orders", token, {
    method: "POST", body: { merchant_id: merchants[0].id, raw_text: rawText },
  });
  const saved = await ordersApi(`/orders/${order.id}`, token);
  const corrected = await ordersApi(`/orders/${saved.id}`, token, {
    method: "PATCH", body: { expected_version: saved.version, floor: "2" },
  });
  const reviewed = await ordersApi(`/orders/${saved.id}/status`, token, {
    method: "PATCH",
    body: { expected_version: corrected.version, status: "NEEDS_REVIEW" },
  });
  const query = new URLSearchParams({ page: "1", page_size: "20", confidence: "AMBER" });
  const page = await ordersApi(`/orders?${query}`, token);
  const events = await ordersApi(`/orders/${reviewed.id}/events`, token);
  return { reviewed, page, events };
}
```

Catch errors and show validation reasons to the dispatcher. Render customer text using
textContent/framework escaping; never inject it as HTML. A 401 needs the correct local
token, 403 indicates access restrictions, and 503 indicates configuration/database readiness.

## Phase 5: buyer confirmation flow and security boundary

Buyer endpoints require no account and **never use the development token**. The link token
is a secret capability; verification grants a separate Bearer credential. This backend
continues to run only as a local/test foundation: all buyer APIs fail closed in production
until production authorization and deployment security are implemented. The public buyer
routes have no loopback-only guard, enabling isolated testing of anonymous clients, but
this does not authorize exposing this local development server.

The merchant/dispatcher sends links manually through an existing trusted conversation.
No SMS, Messenger or Viber integration is performed. Knowledge of four digits is a limited
verification step combined with possession of a high-entropy link, **not proof of phone
ownership**. Never present it as OTP verification or production user authentication.

### Generate and revoke links (dispatcher/merchant access)

`POST /api/orders/{order_id}/confirmation-link`, header `X-Dev-Access-Token`, no body.
Order must have a valid registered phone and status NEEDS_REVIEW, AWAITING_CONFIRMATION
or CONFIRMED. DRAFT orders need an explicit review transition first. Ownership and role
restrictions are the same as other order APIs. Response **201**:

```json
{
  "link_id":"<UUID>",
  "confirmation_url":"/confirm/<LINK_TOKEN>",
  "absolute_url":null,
  "expires_at":"2026-10-24T08:00:00Z"
}
```

The example timestamp is illustrative; actual expiry is creation + configured lifetime.
`confirmation_url` is a **frontend route**, not the API endpoint. Configure
`LANNPYA_BUYER_FRONTEND_BASE_URL` to get an absolute URL; it is never derived from Host.
Non-local absolute URLs require HTTPS and cannot contain credentials/query/fragment.
Token is returned once; only its SHA-256 hash is stored. Generation revokes all previous
links/sessions for that order, including locked links. Only protected operators can regenerate.

Default lifetime is **72 hours before delivery**, configurable 1..168 hours. On transition
to DELIVERED, a still-valid, unlocked, non-revoked link becomes **minimal view-only until
exactly 24 hours after delivery**. Sensitive actions stop immediately. Expired/revoked/locked
links are not revived; regenerate before delivery when necessary. CANCELLED revokes links.
Phone corrections permanently revoke existing links, even if the old phone is restored.

`POST /api/orders/{order_id}/confirmation-link/revoke` revokes all links for that order.
Protected; response 200 `{"revoked":true}`. Repetition creates no duplicate revocation event.

### GET /api/confirm/{token}: minimal public card

No authorization header. Response 200 contains **only**:

```json
{
  "order_reference":"<order UUID>",
  "shop_display_name":null,
  "delivery_status":"NEEDS_REVIEW",
  "state":"VERIFICATION_REQUIRED",
  "expires_at":"2026-10-24T08:00:00Z"
}
```

`state` is VERIFICATION_REQUIRED, LOCKED or VIEW_ONLY. Card retrieval does not grant
authorization. No phone, customer name, address, pin, COD, notes or internal token is
returned. Shop branding and item information are unavailable: the merchant system must
later supply trustworthy public display data; user-profile names are not treated as branding.
Unknown/revoked/phone-invalidated/cancelled links share 404 CONFIRMATION_UNAVAILABLE;
expired links return 410 CONFIRMATION_EXPIRED. Do not automatically regenerate publicly.

### POST /api/confirm/{token}/verify

JSON body has exactly `{"last_four":"4567"}`: four **ASCII digit characters**, not a number.
Malformed input returns 422 and consumes no failed guess, but is subject to the general
request limiter. Valid wrong guesses return generic 403 BUYER_VERIFICATION_FAILED, without
echoing submitted/stored digits or revealing remaining guesses. After **three failures**,
the link is locked; subsequent verification and sensitive actions return 423 CONFIRMATION_LOCKED.
Counters are persisted and serialized across concurrent requests, sessions and processes.
Successful verification does not reset the failed-attempt budget.

Success 200:

```json
{"access_token":"<BUYER_AUTHORIZATION>","token_type":"Bearer","expires_at":"2026-10-21T08:15:00Z"}
```

Store this credential **only in page memory**, never URLs, localStorage, analytics or logs.
Default expiry is 15 minutes (configurable 1..30) and never exceeds link expiry. Send
`Authorization: Bearer <BUYER_AUTHORIZATION>` for every sensitive buyer request. A new
successful verification invalidates older authorizations for that link. It is bound to
that link/order and cannot access dispatcher APIs. No cookies are used; cross-origin
credentials are disabled. A CSRF cookie mechanism is therefore not required in this phase.

### GET /api/confirm/{token}/details

Requires buyer Bearer credential. Returns order_reference, status, township, street,
landmark, building_floor_unit, latitude, longitude, delivery_time_window,
delivery_instructions, initial_pin_requires_review and policy. Nullable values stay null;
coordinates are decimal strings. No full phone, customer name, raw message or merchant
token is returned. This endpoint is unavailable once delivery has closed for buyer changes.

`policy` includes automatic_adjustment_meters (500), rescheduling_enabled,
leave_with_security_enabled, cutoff_hour_yangon, timezone (Asia/Yangon),
min_notice_minutes, max_schedule_days and cross_township_fee_mmk (nullable indicative fee).
No fee is charged or collected. `initial_pin_requires_review` is true when no attested
reference exists; even when false, missing boundary data can require review.

### PATCH /api/confirm/{token}/location

Requires buyer Bearer credential. Exact allowed body:

```json
{
  "request_id":"<new UUID generated by crypto.randomUUID()>",
  "latitude":"16.8000000",
  "longitude":"96.1000000",
  "initial_pin_acknowledged":true
}
```

Coordinates are required, finite, at most seven decimal places, latitude -90..90,
longitude -180..180. Booleans and extra fields are rejected. The acknowledgement means
"submit an initial pin for dispatcher review"; it grants no geospatial trust.

| Server-owned condition | Outcome |
| --- | --- |
| No independently checked reference anchor | 409 INITIAL_PIN_ACKNOWLEDGEMENT_REQUIRED without acknowledgement; otherwise store proposal as REVIEW_REQUIRED, leave dispatch coordinates unchanged |
| Reference plus trusted township boundary resolution, same township and <=500m from anchor | APPLIED automatically, source buyer_confirmation; never grants GREEN by itself |
| Same township, >500m | REVIEW_REQUIRED / ZONE_2_RESCHEDULE_REVIEW_REQUIRED; dispatcher evaluates courier rescheduling policy |
| Trusted resolver identifies another township | REVIEW_REQUIRED / CROSS_TOWNSHIP_APPROVAL_REQUIRED; dispatcher approval and possible courier fee required |
| Missing/ambiguous boundary data, stale township, or anchor mismatch | REVIEW_REQUIRED / TOWNSHIP_BOUNDARY_UNVERIFIED |

The default boundary resolver has **no dataset**, so automatic Zone 1 acceptance is not
enabled in this checkout. Server-side reviewed data can be supplied through
`create_app(township_boundaries=...)`. Clients cannot supply township, zone, distance,
source metadata, approval or trust flags. Existing manually entered order coordinates and
approved initial buyer pins do not become trusted anchors. Distance uses great-circle
Haversine meters from the immutable anchor, preventing repeated 500m hops.

### PATCH /api/confirm/{token}/response

Requires buyer Bearer credential. Allowed keys: request_id UUID, action, optional
time_window, optional instructions (nonblank string, <=2,000 characters).

```json
{"request_id":"<UUID>","action":"AVAILABLE","instructions":"Ring the gate bell"}
```

Actions:

- AVAILABLE: record availability; if no unresolved review or critical validation failure,
  transition NEEDS_REVIEW/AWAITING_CONFIRMATION to CONFIRMED. No fabricated pin or GREEN.
- RESCHEDULE: requires `time_window:{"start":"2026-10-23T09:00:00+06:30","end":"2026-10-23T11:00:00+06:30"}`.
- LEAVE_WITH_SECURITY: record request; review required unless courier policy explicitly enables it.
- INSTRUCTIONS: requires instructions; permitted pre-dispatch updates are buyer-sourced.

Time windows require explicit timezone offsets, start before end, duration 30 minutes..8
hours, and the same Yangon calendar day. Start must meet configured notice (default two
hours), end must be within the scheduling horizon (default seven days). Invalid/past windows
return 422 INVALID_DELIVERY_WINDOW. Examples must be replaced with future dates at runtime.

Rescheduling is disabled by default: a valid request is saved for review without changing
the order's delivery window. If enabled, it applies only before the daily cutoff (default
15:00 Asia/Yangon); at/after cutoff, review is required. Any unresolved buyer review also
forces subsequent response requests to review. All proposed field changes in one request
are applied together or all retained for review. Cross-township requests never silently
change the dispatch plan. Dispatcher approval is an explicit manual policy override, not
an automatic promise from the courier.

### Buyer mutation response, retries and lifecycle

Both PATCH endpoints return 200 for a recorded APPLIED **or REVIEW_REQUIRED** request:

```json
{
  "request_id":"<UUID>",
  "decision":"REVIEW_REQUIRED",
  "reason_codes":["INITIAL_PIN_REQUIRES_REVIEW"],
  "order_status":"NEEDS_REVIEW",
  "confidence_level":"AMBER",
  "submitted_at":"2026-10-21T08:00:00Z",
  "confirmed_at":null,
  "resolution":null
}
```

`confirmed_at` is set only for an applied request or later approval; review submission is
not confirmation. `resolution` later becomes APPROVE/REJECT when reviewed. Retain a
request_id when retrying the **same** body; it returns the existing request with current
order status and no duplicate event. Reusing that UUID for a different body/action returns
409 BUYER_REQUEST_CONFLICT. Generate a new UUID for a new user action.

Sensitive buyer actions require status NEEDS_REVIEW, AWAITING_CONFIRMATION or CONFIRMED.
READY_FOR_DISPATCH, ASSIGNED, OUT_FOR_DELIVERY, FAILED and terminal states reject edits.
Review-required changes set NEEDS_REVIEW and manual_review_required. Unresolved buyer
requests block protected CONFIRMED/READY_FOR_DISPATCH transitions with 409 BUYER_REVIEW_REQUIRED.
No buyer action changes registered phone, COD, merchant or independently verified confidence.

### Dispatcher reference attestation and review

These endpoints use the **development token**, never the buyer credential, and require
Dispatcher/Admin for writes. Merchants may read only their scoped request history.

- `POST /api/orders/{id}/location-reference` (201): body request_id UUID, latitude,
  longitude, township (controlled matching alias), source_reference (nonblank <=500),
  independently_checked:true. Operator must actually verify the reference externally.
  It must match the pre-dispatch order township. Anchor is immutable; repeat returns 409
  REFERENCE_ALREADY_SET. An attestation alone does not supply township boundary data or GREEN.
- `GET /api/orders/{id}/buyer-requests?page=1&page_size=20`: protected paginated history;
  limits match orders. Items include internal id, request_id, kind, decision, reason_codes,
  previous_values, submitted_values, resolution, resolution_reason, resolved_by,
  resolved_at and created_at. This sensitive audit data is never returned on the public card.
- `PATCH /api/orders/{id}/buyer-requests/{internal_request_id}`: body
  `{"expected_version":5,"decision":"APPROVE","reason":"Dispatcher reviewed customer proposal"}`
  or REJECT; reason 5..500 trimmed characters. Latest order version is required. Response
  `{request_id,resolution,order_version}`. Only pending pre-dispatch requests are eligible.
  Approval applies proposed fields with buyer provenance and approving actor, retaining
  previous values privately. A trusted resolver can update the target township on approval.
  Unknown township stays unverified. Past rescheduling windows cannot be approved.
  Rejection preserves order values. Both leave order NEEDS_REVIEW; dispatcher must then
  follow normal confirmation/dispatch transitions. Repeated identical decisions are idempotent.

### Errors and security states

All use the existing sanitized `{error:{code,message,details}}` envelope.

| HTTP | Buyer codes |
| --- | --- |
| 401 | BUYER_AUTHORIZATION_REQUIRED: missing, wrong-link, rotated or expired credential |
| 403 | BUYER_VERIFICATION_FAILED: generic failed digit check |
| 404 | CONFIRMATION_UNAVAILABLE; BUYER_REQUEST_NOT_FOUND for protected review |
| 409 | BUYER_CHANGES_CLOSED, CONFIRMATION_NOT_ELIGIBLE, INITIAL_PIN_ACKNOWLEDGEMENT_REQUIRED, BUYER_REQUEST_CONFLICT, BUYER_REVIEW_REQUIRED, BUYER_REQUEST_ALREADY_REVIEWED, BUYER_REVIEW_NOT_ELIGIBLE, BUYER_REVIEW_WINDOW_PASSED, REFERENCE_NOT_ELIGIBLE, REFERENCE_ALREADY_SET; existing VERSION_CONFLICT applies |
| 410 | CONFIRMATION_EXPIRED |
| 422 | VALIDATION_ERROR / INVALID_DELIVERY_WINDOW |
| 423 | CONFIRMATION_LOCKED; contact merchant for protected regeneration |
| 429 | BUYER_RATE_LIMITED; honor Retry-After: 60 |
| 503 | BUYER_CONFIRMATION_DISABLED / DATABASE_UNAVAILABLE |

General limit: default 60 public requests per actual socket peer per minute. Verification
additionally allows ten well-formed attempts/minute per peer, including successes. Counters
are atomic and database-backed across workers/restarts. Three failures/link is a separate
hard lockout; changing IP/session cannot reset it. Forwarded IP headers are not trusted by
the application. These fixed-window limits can allow boundary bursts and shared-network
users share a budget. Do not place this development server behind a forwarding proxy.

Buyer responses use no-store, no-referrer, noindex/nofollow and nosniff. Uvicorn access
logging redacts link paths and query strings; keep `--no-access-log` as documented and
configure any future frontend/proxy logs separately. Do not log request bodies/headers.
The future card page must send `Referrer-Policy: no-referrer`, avoid third-party scripts,
analytics and link-preview leakage, and remove the token from visible history after reading
it (keeping it only in memory). Never cache buyer API responses or credentials in a service worker.

### JavaScript buyer example

```javascript
async function buyerFlow(linkToken, readLastFour) {
  const base = `http://127.0.0.1:8000/api/confirm/${encodeURIComponent(linkToken)}`;
  let authorization; // Memory only; cleared on page exit or authorization expiry.
  async function call(suffix = "", method = "GET", body) {
    const response = await fetch(base + suffix, {
      method, cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer",
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(authorization ? { Authorization: `Bearer ${authorization}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error?.message ?? `HTTP ${response.status}`);
      error.status = response.status;
      error.code = data.error?.code;
      error.retryAfter = response.headers.get("Retry-After");
      throw error;
    }
    return data;
  }
  const card = await call();
  if (card.state !== "VERIFICATION_REQUIRED") return { card };
  const verified = await call("/verify", "POST", { last_four: await readLastFour() });
  authorization = verified.access_token;
  const details = await call("/details");
  // Call only after the user deliberately confirms their selected pin:
  async function submitPin(latitude, longitude, requestId = crypto.randomUUID()) {
    return call("/location", "PATCH", {
      request_id: requestId, latitude, longitude, initial_pin_acknowledged: true,
    });
  }
  async function respond(action, extra = {}, requestId = crypto.randomUUID()) {
    return call("/response", "PATCH", { ...extra, request_id: requestId, action });
  }
  return { card, details, submitPin, respond };
}
```

Show a pending-review message for REVIEW_REQUIRED, not a confirmed-location badge. Handle
401 by clearing authorization and asking for verification again, 423 by contacting the shop,
410/404 by stopping the flow, and 429 by waiting. Do not auto-retry digit guesses or obtain
new request IDs when retrying a failed network submission. Samples with all capabilities
redacted are in [PHASE5_SAMPLE_RESPONSES.json](PHASE5_SAMPLE_RESPONSES.json).

## Phase 6: rider access and delivery workflow

All rider/assignment endpoints require `X-Dev-Access-Token`, actual loopback access,
enabled local/test order management, and a server-bound actor. Production remains disabled.
Dispatcher/Admin can manage riders, assignments and rider queues. A Rider actor can list
only themselves, retrieve/update their own operational profile, fetch their own active
queue, and act on deliveries actually assigned to them. Merchant actors cannot access
these rider APIs. A buyer Bearer credential cannot access them. Client identity/role headers
never select an actor. Rider and order responses are no-store.

The existing local instance is bound to its configured dispatcher. This is not a multi-user
login service: a rider's local instance must be configured server-side for that Rider UUID
and its own secret. `scripts/smoke_delivery.py` demonstrates separate merchant, dispatcher
and rider instances on isolated loopback ports/database; it performs all setup itself.
Production tenant/rider authorization remains a later requirement. Never share dispatcher
secrets with riders or put either secret in a publicly deployed frontend bundle.

### Rider management

`POST /api/riders` (Dispatcher/Admin, 201):

```json
{"name":"<actual rider name>","operational_status":"AVAILABLE","contact_phone":"<optional valid Myanmar mobile>"}
```

Name is required, trimmed, nonblank, at most 200 characters. Optional email is at most 254
characters with basic email format validation; optional contact_phone is normalized like
order phones (maximum 40 input characters). Omit unavailable contacts rather than sending
placeholder strings. Operational status is AVAILABLE, ON_BREAK or OFFLINE; default OFFLINE.
No messages are sent. Names/identities reuse Users with role Rider. An omitted email uses
an internal `UUID@riders.invalid` identifier solely to satisfy the existing Users constraint;
the rider API returns email:null rather than claiming that identifier is contact information.

Rider response: `{id,name,email,contact_phone,operational_status,version,created_at,updated_at}`.
ID is the existing User UUID. Existing Rider users receive OFFLINE profiles during migration.

- `GET /api/riders?page=1&page_size=20&operational_status=AVAILABLE`: paginated
  `{items:[<Rider>],total,page,page_size}`. Same limits as order lists; optional status filter.
  Stable ordering by name then UUID; Rider actors see only themselves.
- `GET /api/riders/{id}`: one profile. Missing/out-of-scope UUID returns 404 RIDER_NOT_FOUND.
- `PATCH /api/riders/{id}`: `{expected_version:1,operational_status:"ON_BREAK"}`.
  Requires latest profile version. Rider may update only their own availability; no name,
  identity or contact edits through this endpoint. Dispatchers/Admin may update any profile.
  Availability is explicit, not automatically changed to BUSY by assignment. OFFLINE/ON_BREAK
  prevent assignment and starting new deliveries, but do not prevent completing work already
  out for delivery. Queue activity can increment the profile version: refresh before PATCH.

### Assignment APIs (Dispatcher/Admin)

`POST /api/orders/{order_id}/assign` (201):

```json
{"expected_version":5,"rider_id":"<Rider UUID>","stop_sequence":1}
```

Requires READY_FOR_DISPATCH, available rider, no active assignment, no unresolved buyer
requests, valid phone/township and non-RED validation. COD must be explicitly known; use
0 for prepaid orders. AMBER is permitted after the existing dispatcher readiness acknowledgement;
assignment never creates coordinates or changes confidence to GREEN. Default queue capacity
is 100 active deliveries per rider, configurable up to 200. Concurrent assignments cannot
exceed capacity or create two active assignments for one order.

Response: `{assignment:<Assignment>,order_status:"ASSIGNED",order_version:6}`.
Assignment contains id, order_id, rider_id, dispatcher_id, status, stop_sequence,
failure_reason, failure_note, cod_collected, assigned_at, updated_at and ended_at.
Assignment status is ACTIVE, UNASSIGNED, COMPLETED, FAILED or CANCELLED; it describes
assignment history, while Order.status remains the authoritative delivery lifecycle.

- `POST /api/orders/{id}/unassign`: `{expected_version:6}`. Allowed only while ASSIGNED,
  before start. Closes assignment as UNASSIGNED, returns order to READY_FOR_DISPATCH, and
  removes it from the queue. Reassignment creates a new record; history is retained.
- `PATCH /api/orders/{id}/assignment`: `{expected_version:6,stop_sequence:3}`.
  Sequence is 1..10,000 or explicit null; only ASSIGNED orders can be reordered. This is
  a dispatcher preference within the queue priority policy below, not route optimization.
- `GET /api/orders/{id}/assignments?page=1&page_size=20`: protected paginated assignment
  history, oldest first with UUID tie-break. Includes private failure notes; Rider actors
  cannot browse other orders/history through this endpoint.

The existing generic status endpoint also atomically closes a real assignment when moving
ASSIGNED -> READY_FOR_DISPATCH or CANCELLED, recording RIDER_UNASSIGNED. Real assigned
orders must use the rider endpoint for OUT_FOR_DELIVERY/DELIVERED/FAILED (otherwise 409
USE_RIDER_DELIVERY_ACTION). Old status-only records are not assigned to an invented rider.

### GET /api/riders/{rider_id}/queue

Protected, scoped, full active snapshot. Optional `cursor=<64 lowercase hexadecimal characters>`.
Only ACTIVE assignments whose order is ASSIGNED or OUT_FOR_DELIVERY are included.

```json
{
  "rider_id":"<UUID>","operational_status":"AVAILABLE",
  "cursor":"<opaque 64-character snapshot hash>","unchanged":false,
  "total":1,"items":["<QueueDelivery object>"],"generated_at":"<UTC timestamp>"
}
```

Each item contains assignment_id, order_id, status, order_version, stop_sequence,
customer_name, customer_phone, township, street, landmark (including Burmese text),
building_floor_unit, delivery_instructions, delivery_time_window, confirmed_window_start,
cod_amount (exact digit string/null), latitude/longitude (decimal strings/null),
coordinate_status, navigation_ready, navigation_url, confidence_level, location_verification,
buyer_confirmation and updated_at. Raw messages, AI context and link/session secrets are excluded.
Customer contacts are visible only to authorized dispatchers and the assigned rider.

`coordinate_status` is MISSING, UNCONFIRMED or BUYER_CONFIRMED. A manually entered pin is
not automatically confirmed. Buyer confirmation means the current canonical coordinates
were explicitly accepted through the buyer/dispatcher workflow; it does not mean independent
geospatial verification. Location verification/confidence remain separate and GREEN stays
restricted. Null coordinates remain null.

`buyer_confirmation` contains location (CONFIRMED/NOT_CONFIRMED), availability (AVAILABLE,
RESCHEDULE, LEAVE_WITH_SECURITY or NOT_CONFIRMED), pending_review (boolean) and
last_confirmed_at (nullable UTC time). Rejected/pending requests do not masquerade as applied.

Deterministic ordering, in priority order:

1. OUT_FOR_DELIVERY before ASSIGNED.
2. A buyer-confirmed, valid timezone-aware ISO delivery window before an unconfirmed/freeform
   window; among confirmed windows, earlier start first. Freeform text is still displayed.
3. Dispatcher stop_sequence ascending, with null after specified sequence values.
4. Assignment time, order creation time, order UUID, assignment UUID.

This is a queue priority policy, **not geographic route optimization**.

### Polling and buyer updates

The cursor hashes rider state and the full returned queue snapshot; it is not a timestamp
watermark or authorization token. It detects approved order updates, reordering, assignment,
completion, cancellation and removals. If unchanged, return 200 with unchanged:true,
items:[] and total equal to the current active count. **Keep the existing UI list** in that
case. If unchanged:false, **replace the entire list**, including when total is zero.
Cursor values are rider-specific; generated_at is informational and not used as a cursor.
This bounded full-snapshot endpoint is not paginated. The assignment cap keeps it small.

Poll every five seconds while the rider screen is active; pause when backgrounded and do
not overlap requests. Fetch again after an action. This is near-real-time REST polling,
not an instant push channel or durable change-event stream.

Phase 5 buyer rules stay intact: buyer edits/approval stop once dispatch is ready/assigned.
To accept a later pre-start correction, dispatcher must unassign, return order to NEEDS_REVIEW,
process/approve the buyer request, confirm readiness and reassign. Old queue sees removal;
new queue sees only the approved canonical details. On-road deliveries cannot be silently
edited or unassigned. No unapproved location proposal is sent as a navigation destination.

### Navigation

For BUYER_CONFIRMED coordinates only, navigation_ready:true and an encoded URL such as
`https://www.google.com/maps/dir/?api=1&destination=16.8000000%2C96.1000000&travelmode=driving`.
This is a synthetic example, not a generated address/pin. With missing/unconfirmed coordinates,
navigation_ready:false and navigation_url:null. Do not open Maps automatically; use a user
navigation action. URL contains coordinates/mode only, no customer name, phone, private notes,
API key or tracking location. The backend makes no Google API request and purchases no service.
Format follows [Google Maps URL documentation](https://developers.google.com/maps/documentation/urls/get-started).

### Rider delivery actions

`PATCH /api/riders/{rider_id}/deliveries/{order_id}/status`, own assigned rider or Dispatcher/Admin:

```json
{"request_id":"<new UUID>","expected_version":6,"action":"START"}
```

START: ASSIGNED -> OUT_FOR_DELIVERY, requires AVAILABLE rider.

```json
{"request_id":"<new UUID>","expected_version":7,"action":"DELIVERED","cod_collected":true}
```

DELIVERED: OUT_FOR_DELIVERY -> DELIVERED, closes assignment COMPLETED and removes it from
the queue. For positive COD, true is mandatory under default policy; absence/false returns
409 COD_CONFIRMATION_REQUIRED. Null COD requires dispatcher review (409 COD_AMOUNT_REQUIRED).
Prepaid zero does not require collection. This records an actor's collection assertion,
**not payment processing or proof of payment**. Courier configuration can explicitly disable
the requirement with LANNPYA_RIDER_REQUIRE_COD_CONFIRMATION=false; the API never invents true.

```json
{
  "request_id":"<new UUID>","expected_version":7,"action":"FAILED",
  "failure_reason":"CUSTOMER_UNAVAILABLE","failure_note":"<optional private follow-up>"
}
```

FAILED: OUT_FOR_DELIVERY -> FAILED and closes assignment FAILED. Required reason enum:
CUSTOMER_UNAVAILABLE, ADDRESS_NOT_FOUND, CUSTOMER_REFUSED, ACCESS_BLOCKED,
COD_NOT_COLLECTED or OTHER. Optional note is nonblank, <=500 characters, stored privately
on the assignment and excluded from event metadata/navigation. Failure fields are forbidden
for other actions; cod_collected is a strict boolean accepted only for DELIVERED.

Success 200 contains request_id, assignment_id, order_id, rider_id, status,
assignment_status, order_version, cod_collected, failure_reason and updated_at.
Send the latest queue/action version. Retain the exact body/request_id for network retries;
same actor/request/body returns the stored original result, including after completion,
with no duplicate event. Changed payload using that UUID returns 409 RIDER_REQUEST_CONFLICT.
A new request targeting an ended/non-owned assignment returns 404 ASSIGNED_DELIVERY_NOT_FOUND.
Replayed acknowledgements are historical results; refresh the queue for current state.

Each successful operation commits order, assignment, event, queue version and receipt
atomically. Concurrent duplicate completions create one completion event. Terminal deliveries
cannot be reopened by rider actions. FAILED orders use the existing dispatcher review/retry
lifecycle and receive a new assignment when eligible.

Events add RIDER_ASSIGNED, RIDER_UNASSIGNED, RIDER_SEQUENCE_CHANGED, DELIVERY_STARTED,
DELIVERY_COMPLETED and DELIVERY_FAILED. They retain actor_id, actor_role, rider_id,
assignment_id, previous/new order status and applicable reason/COD boolean. Existing buyer
approval events retain their operator actor ID. No private failure note is copied into events.

### Additional rider errors

The existing sanitized JSON error envelope applies. 401 missing/incorrect local token;
403 ROLE_FORBIDDEN/LOCAL_ACCESS_ONLY; 404 RIDER_NOT_FOUND/ASSIGNED_DELIVERY_NOT_FOUND;
422 VALIDATION_ERROR for bad bodies, UUIDs in bodies, cursors, filters or pagination.
Malformed path UUIDs remain 404. 409 codes include VERSION_CONFLICT, RIDER_NOT_AVAILABLE,
ORDER_NOT_ASSIGNABLE, UNASSIGN_NOT_ALLOWED, RIDER_QUEUE_FULL, ORDER_VALIDATION_REQUIRED,
BUYER_REVIEW_REQUIRED, INVALID_STATUS_TRANSITION, COD_AMOUNT_REQUIRED,
COD_CONFIRMATION_REQUIRED, RIDER_REQUEST_CONFLICT, USE_RIDER_DELIVERY_ACTION and
DATABASE_CONFLICT. Database/configuration errors remain 503 and never expose SQL/credentials.

### JavaScript polling example

```javascript
async function pollRiderQueue(apiBase, riderId, localToken, render, signal) {
  let cursor;
  while (!signal.aborted) {
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const response = await fetch(`${apiBase}/api/riders/${riderId}/queue${query}`, {
      headers: { "X-Dev-Access-Token": localToken },
      cache: "no-store", credentials: "omit", signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message ?? `HTTP ${response.status}`);
    if (!data.unchanged) render(data.items); // Replace; [] means remove all displayed stops.
    cursor = data.cursor;
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}
```

Keep the development token in runtime memory. Render notes with textContent/framework
escaping. Stop polling on authorization errors and use AbortController on screen exit.
Use the existing fetch helper for POST/PATCH, supplying the latest expected_version and
a new crypto.randomUUID() per intentional delivery action. Do not automatically repeat
conflicting updates with a new version. Actual redacted responses are in
[PHASE6_SAMPLE_RESPONSES.json](PHASE6_SAMPLE_RESPONSES.json).

## Three-role workspace: atomic preparation

The local Admin/Customer/Rider workspace uses the same orders and assignments.
`POST /api/orders/{order_id}/prepare-assignment` is an Admin/Dispatcher operation,
with the existing local-development access gate. Body:

```json
{
  "request_id": "<new request UUID retained for identical retries>",
  "expected_version": 1,
  "rider_id": "<available rider UUID>",
  "receive_at_hub": true,
  "acknowledge_unverified_location": true
}
```

Supply exactly one of rider_id or route_id. Rider selection creates a new draft
route for the parcel's saved delivery day; route selection appends to an existing
matching-day draft. Missing acknowledgement or invalid choice is rejected. All
native critical-field, location, pending-customer-review, incident, physical hub
receipt, rider availability and capacity checks run. This operation is not a
customer-request approval or independent map verification.

Success 200: `{order, assignment, route}`. Preparation/status transitions, explicit
receipt, route creation and assignment use one database transaction. Any failure
rolls all of them back; the previous status/version and custody remain unchanged.
The most recent preparation receipt records actor/request/body identity. Identical
retries do not assign twice; changed content for that receipt returns 409
REQUEST_CONFLICT. Stale/new attempts return 409 VERSION_CONFLICT rather than
silently taking the latest version. Refresh and review after conflicts.

No automatic departure occurs. Separately POST the route DISPATCH action with its
latest version after confirming physical readiness. Future-day planning is allowed;
departure and delivery day/window guards still apply. Delivery completion requires
actual cash, including zero for prepaid. Rider HANDOVER and admin RECEIVE_CLOSE
remain distinct custody events; returns and unresolved differences still block
closeout. See [the workspace guide](../../API_INTEGRATION.md) and
[the complete endpoint list](FRONTEND_HANDOFF.md) for the short UI walkthrough.
