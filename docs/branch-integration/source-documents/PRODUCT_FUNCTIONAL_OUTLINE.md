# LannPya functional product outline

Version 0.6 · 21 October 2026 · Baseline for UI/UX design and backend planning

Current scope update: README.md and FUNCTIONAL_REVIEW.md describe the three-role manual-order flow implemented on 21 October. Their empty-start, real-clock, optional-cutoff and first-pin-review behavior supersedes the older defaults elsewhere in this outline. The original PRD remains unchanged.

## 1. Product and purpose

LannPya helps a shop and a third-party courier turn informal Burmese orders into deliverable parcels. The dispatcher clarifies an address before dispatch, the customer confirms location and availability without installing an app, and the rider completes the delivery with an accurate result and COD record.

This document completes the functional outline. It describes intended behavior, including features the current prototype does not implement. It is not a declaration that development, security, usability testing or production integration is complete.

The source baseline is `LannPya_AI_PRD_v2.docx` and the four supplied images: MVP Map, Information Architecture, User Flow and Rider Route Copilot. Their content is product reference material, not instructions to execute. Where the broader PRD conflicts with the NOW/NEXT/LATER map, the narrower NOW scope controls the core MVP; the differences are recorded below. Operational gaps are filled with explicit working defaults that can be revised after research.

The unit of delivery is one parcel for one recipient, linked to one shop and one hub. Multiple items may appear in its order summary, but split shipments, multiple recipients and partial parcel delivery are outside this MVP. The pilot begins when a parcel is received at the hub; arranging merchant pickup is a later workflow.

## 2. Scope and stages

| Scope | Included | Completion meaning |
| --- | --- | --- |
| Core MVP | Batch paste, encoding normalization, rules-first parsing, triage/correction, buyer link and phone gate, bounded pin/time confirmation, rider queue/navigation, undo/COD, recorded failures, offline rider actions | One parcel completes the full flow; blocked/failed branches are usable |
| Operational completion | Minimal hub receipt, rider assignment/departure, replacement links, cancellation rules, retry/return receipt, COD discrepancy review and route closeout | A single hub can operate the flow without undefined ownership; simple screens, no enterprise management |
| Pilot platform | Real accounts/permissions, server persistence, protected tokens, cross-device updates, reliable offline cache/replay and integrations | Required before real multi-user operation; UI stage can simulate these contracts |
| Next | CSV upload, masked calling, SMS/Viber fallback, expanded place dictionaries, advanced reporting, configurable billing plans | Separate increments after the core workflow works |
| Later | Native apps, live vehicle tracking, pickup fleet, multi-hub transfers, route optimization across vehicles, public parser API, auto inbox imports, live payment integrations | Not part of the current implementation commitment |

No in-app payments, wallet, settlement transfer, subscription checkout, rider marketplace or customer account registration are required. Recording COD or manually marking an existing payment as prepaid does not move money.

Basic operational counts belong in the MVP. Historical business analytics remain a pilot feature. Existing sample analytics must be labelled demo rather than presented as measured results.

## 3. People, authority and separate applications

Updated 21 October 2026: the application has exactly three sides. The earlier merchant workspace is removed. Admin may record a sender/business name as parcel context; that does not create a sender account or fourth role.

| Role | Responsibilities | Access boundary |
| --- | --- | --- |
| Admin | Manually create or batch-import orders; correct fields; receive parcels; review customer locations; issue links; assign/dispatch riders; handle returns and cash closeout | Own hub operations |
| Customer | Open own link; pass phone gate; submit/adjust location, availability and notes; view delivery result | Token-scoped order only; the local preview list is a test convenience, not production account access |
| Rider | View assigned dispatched work; navigate; record handoff/COD or failure; submit returns and cash handover | Assigned routes/stops only |

Admin entry is `#/dispatch`, with manual creation at `#/manual`. Customer entry is `#/customer`, opening the selected private `#/track/:token` link. Rider entry is `#/ride`. Navigation selects the correct side; no mixed merchant/dispatcher/rider actor dropdown is required.

Normal operation uses the real Yangon clock. Manual orders default to Any time. Daily customer cutoff enforcement is optional; dispatch always freezes customer edits. A customer can propose the first pin without an existing anchor; that proposal cannot clear the location hold until admin approval. The 500 m limit applies after an approved anchor exists.

Existing browser-local records and drafts are intentionally cleared once on the first v4 load. No sample orders, default route or legacy import is automatically restored. Newly created orders survive subsequent refreshes.

## 4. Complete parcel journey

1. **Capture.** Shop/dispatcher pastes chat orders separated into reviewable records. Review boundaries before confirming batch creation; a name or phone alone is not a reliable separator.
2. **Normalize.** Preserve original text, convert encoding to Unicode, extract deterministic fields and match supported places. Send only approved redacted address text for optional AI extraction.
3. **Review.** Show per-order progress, structured fields, provenance, vague phrases and rule reasons. Fix missing/uncertain fields; rerun triage only on affected records.
4. **Clarify.** Green location records may proceed without a buyer reply. Amber records need a buyer confirmation or explicit dispatcher verification of location. Red records remain held until their failed rules are corrected.
5. **Receive and assign.** Dispatcher records parcel physically at hub, assigns a rider and draft route, and checks time/payment/location readiness.
6. **Depart.** Rider sees assigned work; dispatcher marks route dispatched only after route readiness is confirmed. This freezes customer self-service changes for that route.
7. **Deliver.** Rider selects a stop, sees verified instructions, opens navigation or reads the landmark aloud. Parcel handoff triggers two-second undo, then COD/prepaid confirmation.
8. **Handle failure.** A failed attempt records reason and either an eligible retry or a return request. It does not become a completed delivery.
9. **Close.** Hub receives physical returns and reconciles recorded cash. Delivered customer links remain view-only for 24 hours, then expire. Route closes only when unresolved work is accounted for.

No reply is not consent. No map permission is not a failed delivery. Opening a buyer link is not confirmation. Opening navigation is not proof of arrival or delivery. Marking a return is not proof of hub receipt. Recording collected cash is not proof that the hub received it.

## 5. Shared state model

Avoid encoding everything in one Green/Amber/Red status. These independent dimensions have different meanings.

| Dimension | Values | Meaning |
| --- | --- | --- |
| Address triage | `unprocessed`, `green`, `amber`, `red` | Quality of deterministic address checks; never the AI's own confidence |
| Location resolution | `unresolved`, `dictionary_matched`, `buyer_confirmed`, `dispatcher_verified` | Why an actionable location can be trusted |
| Buyer link | `not_created`, `active`, `locked`, `revoked`, `expired` | Link availability; viewing and sharing are separate events |
| Buyer response | `pending`, `at_home`, `reschedule`, `leave_with_security` | Latest accepted delivery preference, independent of triage |
| Parcel lifecycle | `draft`, `held`, `ready`, `assigned`, `out_for_delivery`, `retry_pending`, `return_pending`, `returned`, `delivered`, `cancelled` | Operational custody and progress |
| Route | `draft`, `dispatched`, `in_progress`, `closing`, `closed` | Route execution; dispatched is the customer edit boundary |
| Cash collection | `not_due`, `due`, `recorded`, `discrepancy` | What the rider actually recorded |
| Cash reconciliation | `not_started`, `submitted`, `received`, `disputed` | Hub acknowledgement of handover, not payment processing |
| Write delivery | `local_draft`, `pending_sync`, `acknowledged`, `conflict`, `failed` | Whether a user action is durable on the server |

A buyer confirmation changes response/location resolution and readiness; it must not simply overwrite triage as Green or reset a failed delivery to queued. Original triage and attempt history remain visible. A Green order with an unresolved payment amount or a parcel not at hub is not ready to leave.

### Lifecycle transitions and allowed actors

| From | Trigger and actor | To | Preconditions/result |
| --- | --- | --- | --- |
| draft | Validate intake, system | held or ready | Holds apply until every readiness gate passes |
| held | Correct fields/confirm location, authorized actor | ready | Rerun relevant checks; no silent bypass |
| ready | Assign to rider/route, dispatcher | assigned | Same hub, active rider, no duplicate active assignment |
| assigned | Dispatch route, dispatcher | out_for_delivery | Parcel received, route validated, self-service changes frozen |
| assigned | Remove assignment, dispatcher | ready | Route has not departed; audit reason |
| out_for_delivery | Confirm handoff and cash, assigned rider | delivered | Two-second undo finished; COD/prepaid confirmation accepted |
| out_for_delivery | Record failed attempt, assigned rider | retry_pending or return_pending | Reason and next disposition required |
| out_for_delivery/retry_pending | Coordinate cancellation or service incident, dispatcher | return_pending | Rider acknowledged custody/instructions; no fabricated failed attempt or automatic physical return receipt |
| retry_pending | Schedule eligible retry, dispatcher/system under policy | assigned or out_for_delivery | Future eligible window; same dispatched route may append retry; new route otherwise |
| return_pending | Physically receive parcel, hub dispatcher | returned | Record who received it and when |
| draft/held/ready/assigned | Cancel, authorized shop/dispatcher | cancelled | No departed route; reason retained, link revoked |
| returned | Approve new delivery cycle, dispatcher | draft | New cycle/route record preserves old attempts and return receipt |

After departure, a shop cancellation becomes an operational return request; it cannot delete a rider's delivery task or rewrite a completed handoff. A delivered parcel requiring later refund/return is a separate after-sales process, outside MVP. Terminal outcomes cannot be changed with a normal edit button; corrections use a dated correction record and reason.

Route transitions are draft → dispatched after dispatcher readiness review, dispatched → in_progress on rider acknowledgement, in_progress → closing when all stop dispositions are declared, and closing → closed only after return/cash/sync checks pass. A rejected closeout stays closing. All-prepaid routes explicitly acknowledge zero cash; they do not need a fictitious cash transfer. A route with unresolved work can hand it into a named next route with custody acknowledgement before closing, rather than mislabelling it delivered or returned.

### Readiness gates

An order can leave only if the hub has the parcel, the recipient phone is valid, township is supported, a usable location is resolved, the payment mode and exact amount are known, any selected window is valid, the order is not terminal, and a rider/route assignment exists. Eligibility is recomputed after each relevant change. Ready before assignment means all gates except assignment pass.

Amber can clear its location hold through a bounded buyer confirmation anchored to a credible initial location or dispatcher verification with a recorded reason. A township centroid alone is not a verified starting address. Missing phone or unsupported area must be corrected before a confirmation link can clear the record. A locked customer link does not itself cancel the parcel; an otherwise eligible Green record can still proceed under dispatcher control.

## 6. Dispatcher and merchant functional inventory

| ID / screen | Inputs and actions | Result / acceptance condition |
| --- | --- | --- |
| A01 Intake | Paste multiple orders; edit separators; preview record count; load labelled sample set | Empty input rejected; batch boundaries confirmed; original text retained per record |
| A02 Parser progress | Start, show per-record progress, cancel unstarted records, retry failed records | Results appear independently; one failure does not erase completed records or duplicate them on retry |
| A03 Order board | Search ID/name/phone within authorized scope; filter triage, readiness, lifecycle, date and rider | Counts derive from actual records; empty/filter-no-results states differ |
| A04 Order detail | Read original/normalized text; view field sources and reasons; correct fields and rerun checks | Manual values do not get overwritten on unrelated AI retry; edits have actor/time/history |
| A05 Customer link panel | Create/copy link; mark manually shared; inspect opened/confirmed/locked; revoke/reissue | Copy success is not message delivery; old links fail after replacement; lock appears as an operational exception |
| A06 Hub queue and assignment | Mark parcel received; select eligible orders; choose rider/route; unassign before departure | Held orders stay outside rider work; duplicate assignment is rejected; eligibility blockers are explicit |
| A07 Route review and departure | Review window warnings, stops, rider and unresolved holds; dispatch; see buyer-change badges | Route cannot depart with blocking records; departed route exposes view-only customer state |
| A08 Exceptions | Review held addresses, late requests, lockouts, retry limits, return pending, COD discrepancies, sync conflicts | Each exception has owner, next action and history; resolving it does not erase its cause |
| A09 Operational closeout | Receive returns; review expected/recorded/handed-over cash; acknowledge or dispute | Returned means physical receipt; cash differences require a reason; unresolved discrepancies prevent final closure |
| A10 Policies | Set supported area, cutoff, windows, retry limit and link lifetime through hub policy | Policy version/effective date recorded; edits do not retroactively move departed parcels |

Minimal merchant editing is scoped to own orders and stops at departure. The hub controls assignment, route departure, exception disposition and cash receipt. Pilot sign-in/setup is defined later with backend access; the UI prototype can use named demo actors.

### Parsing and address rules

- Normalize Myanmar digits to numeric equivalents for phone/amount extraction while preserving original text. Convert Zawgyi before extraction. If detection/conversion is uncertain, retain source and surface review rather than corrupting text.
- Extract phone, amount and place identifiers through deterministic rules and supported dictionaries. Normalize phone formatting; retain a review reason if multiple candidate phones or amounts exist. Never invent missing COD or infer prepaid from a missing amount.
- AI may propose landmark, floor/unit and delivery instructions only. Validate output against an allowed schema; attach source snippets and `ai` provenance. Do not accept AI output as evidence that a street/landmark exists on a map.
- Remove customer names, phone numbers, invoice/payment details and unnecessary chat content before an AI request. If redaction cannot confidently isolate the address, skip the external call and request manual review. The UI preview shows the approved payload and never claims perfect redaction from a simple regex.
- Green: valid phone, supported township and reliable street/landmark match with actionable location. Amber: valid phone/township but location ambiguity remains. Red: invalid/missing phone or unsupported/unknown area. Exact reason codes are stored alongside icon and label.
- Ambiguous payment mode/amount adds a separate payment hold even if address triage is Green. Prepaid is an explicit merchant assertion with source/reference, not a live payment-provider verification.
- The dispatcher can correct street/landmark/pin within supported coverage; a material location correction invalidates the old customer confirmation and existing link, then creates a fresh anchor and reissued link. Small notes do not reset the entire record.
- Duplicate detection warns on the same shop + external order reference, or a likely phone/address/item match. It never silently deletes legitimate repeated purchases. Confirm merge/discard/create-separately before committing a duplicate batch row.
- AI unavailability offers manual review or labelled sample fallback. Demo responses must not silently enter live records. Exact-model choice and pricing remain an integration decision; cost claims in the PRD are assumptions, not verified current prices.

## 7. Customer functional inventory

| ID / screen | Inputs and actions | Result / acceptance condition |
| --- | --- | --- |
| C01 Public context | Open token link; see shop/avatar, invoice, item/photo, COD/prepaid and limited status | No address, pin, phone, raw chat, rider-private details or other orders before verification |
| C02 Phone gate | Enter exactly last four digits; retry up to three incorrect submitted checks | Malformed input does not consume a try; three wrong checks lock server-side; wrong browser/new device cannot bypass the lock |
| C03 Location | See original anchor and visible 500 m boundary; drag/select pin; use accessible nudge/reset controls | Both radius and township rules pass; permission denial still allows manual input; no request to move into unsupported area |
| C04 Availability | At home / Reschedule / Leave with security; select offered window; optional note | Chosen mode/time/note saved together; confirmation is explicit; COD handover rule still applies |
| C05 Confirmation | Review pin, time, answer and note; save; view summary; edit before deadline | Success appears only after write acknowledgement; unsaved/pending states are distinct; queue receives an update |
| C06 Change restriction | Reopen after cutoff/departure, request help via shop | Existing summary is view-only; late request does not silently reroute rider or promise a new time |
| C07 Delivery result | View delivered, retry planned or return requested/received result | Customer-friendly text hides operational/private notes; delivered includes recorded collected amount where relevant; cancelled orders use the revoked-link help path and shop communication |
| C08 Link/error recovery | Wrong digits, locked, invalid, revoked, expired, offline, no GPS or failed save | Explain permitted next action; invalid tokens reveal no order; locked user contacts shop; unsent changes never show confirmed |

The customer never chooses a courier fee, edits parcel value/payment mode, sees a rider's personal number or accesses a full tracking dashboard. A public link's shop context improves familiarity but is not proof of identity; the four-digit check is a lightweight accidental-forwarding control.

### Location and editing rules

- The 500 m radius is measured from the original dispatcher-approved anchor, not the buyer's last moved pin. Repeated 499 m moves cannot walk the delivery across town.
- The moved point must remain within the supported original township as well as inside the circle. Township crossing is blocked even if geographically close. If boundary data is uncertain, hold the change for dispatcher review rather than silently accepting it.
- No credible original anchor: customer pin self-service is unavailable until dispatcher locates the parcel. Do not invent coordinates or impose a 500 m circle around a township center and call it verified.
- Customer self-service closes at the earlier of the configured cutoff or route dispatch. The supplied map suggests free rescheduling before departure; the PRD also specifies a default 09:00 cutoff. This outline uses the earlier boundary as a conservative working default, with assisted dispatcher handling afterwards.
- After dispatch, customer may view the summary/result and contact the shop; no self-service pin, time or note write. Dispatcher can record a late request and coordinate with rider; substantial rerouting moves to a later route.
- Cross-township changes show a clear blocked message and shop contact path in MVP. The PRD's suggested +1,500 MMK accept/request flow is deferred with courier fee policy; no fake fee or payment is collected.
- Leave with security names who can receive it in the note. For COD, security must be able to pay the full amount; otherwise use another response/window. The rider cannot leave an unpaid COD parcel solely because this option was selected.
- Time windows express agreed availability, not a guaranteed live ETA. Only current/future offered windows are selectable. Browser timezone does not change the hub's operating day.

## 8. Rider functional inventory

| ID / screen | Inputs and actions | Result / acceptance condition |
| --- | --- | --- |
| R01 Today queue | See assigned route/day, completion count, pending actions, sync age and change badges | Only assigned eligible work appears; no duplicate parcel; empty/no-assignment/route-complete states differ |
| R02 Stop detail | Select stop; see Burmese landmark first, verified pin, time, floor/unit, note, COD/prepaid | Source/change indicators visible; missing details never replaced with an invented generic landmark |
| R03 Navigation/read-aloud | Open Google Maps; read displayed landmark; stop speech | Real destination provided; missing GPS/voice/internet has a readable fallback; no false claim that navigation opened if it failed |
| R04 Delivered/undo | Tap Delivered after handoff; undo for two seconds | Local pending state only; undo creates no delivered record; navigation/reload cannot accidentally finalize handoff |
| R05 Cash confirmation | Confirm full expected amount, or enter actual different amount and reason; prepaid acknowledgement | Single atomic result/cash write; nonnegative whole MMK; prepaid accepts zero only; discrepancy remains visible to hub |
| R06 Failed attempt | Choose one of four reasons, then retry/return | One attempt recorded with time; future retry policy checked; returned is not set until hub receipt |
| R07 History/closeout | View completed/return tasks; record cash handover submission; see hub acknowledgement | Original values retained; no direct edits to terminal stops; cash received by hub is separate from rider declaration |
| R08 Connectivity | Work from downloaded queue; see pending/sent/conflicted actions; retry failed sync | No lost/duplicate delivery on reconnect; no claim of synced until server acknowledges; rejected writes have an actionable resolution |

Primary rider actions need at least 56 px touch targets and sit within thumb reach. Burmese instructions need sufficient line height. Light theme is the default; optional night theme must preserve readable contrast. Riders use the screen while stopped. Neither masked calling nor background GPS is assumed available in the MVP.

### Route ordering and update rules

1. Only ready, assigned work enters a route. A Green row is not automatically a rider assignment.
2. Before departure, order by valid window start, then dispatcher base sequence. A changed buyer time moves a stop into its new bucket. Stable ties retain the existing sequence.
3. After departure, keep the rider's active stop stable. Updates for other stops show a badge and explicit refresh/review; do not jump the current stop underneath a tap.
4. A missed window becomes a warning requiring contact/dispatcher disposition; never silently mark delivered or move to tomorrow.
5. A same-day retry goes after eligible unattempted work in its approved future window. It cannot point to a past window. No future same-day window or exhausted retry limit means return/replan.
6. Default is one original attempt plus one same-day retry. A second failed attempt requires return/replan by dispatcher, not unlimited loops.
7. Queue order is a workflow schedule, not shortest-path optimization or a reliable arrival-time forecast. Do not show fabricated distance/time remaining.

### Delivery, cash and closure rules

The two-second undo precedes permanent delivery submission. After it expires, show COD/prepaid confirmation. Cancelling the cash dialog leaves the stop incomplete. A reload during undo leaves it incomplete. An interrupted amount entry restores an explicit draft/pending action, never a hidden completed record.

Expected COD is fixed at dispatch. Whole-number MMK values are recorded without float rounding. An actual mismatch requires a reason and creates a discrepancy while preserving that the parcel was physically handed over. Dispatcher reconciliation cannot silently rewrite the rider's original collection entry. No partial delivery of parcel items is supported.

Expected COD must be a positive known amount; prepaid has expected collection zero. Actual cash on an already handed-over COD parcel may be zero, but this is a discrepancy requiring a reason, not proof of prepaid status or a clean success. A cancelled handoff before delivery is instead handled through the attempt/return flow.

Offline delivered means recorded on this device and awaiting confirmation, not globally acknowledged delivered. A duplicate client operation ID must not add a second collection or attempt. If authorization/assignment changed while offline, the event goes to a conflict queue for dispatcher review; do not drop the rider's observed handoff.

Route closeout accounts for every parcel as delivered, received-returned, or explicitly handed into a documented next route/custody. Pending sync, unresolved cash discrepancy, missing cash acknowledgement or unreceived returns prevent final closure. No native payment/remittance action is involved.

## 9. Policies and working defaults

These are proposed operating defaults, not facts about a particular courier. They complete the outline without requiring the business to finalize every setting now.

| Policy | Working default | Validation/change path |
| --- | --- | --- |
| Coverage | One Hledan demo hub; only explicitly listed Yangon townships | Confirm pilot boundary data with hub; no implicit nationwide support |
| Hub timezone | Asia/Rangoon | Hub-day grouping and cutoff use this zone; store instants independently |
| Customer pin radius | 500 m from fixed approved anchor | Courier policy, plus same-township constraint |
| Self-service deadline | Earlier of 09:00 on delivery day or route dispatch | Validate against actual shop intake/departure hours before pilot; late orders use assisted confirmation |
| Window choices | 10:00–12:00, 12:00–14:00, 14:00–16:00, 16:00–18:00 | Offer only available future windows; dispatcher manages capacity |
| Customer note limit | 300 characters | Count/validation consistent in UI and backend |
| Phone failure limit | Three incorrect well-formed checks per active token | Reissue revokes old token; repeated reissues are visible and rate-limited |
| Undelivered link lifetime | Proposed seven days from issue, revocable sooner | Completes a gap in PRD; confirm with hub before live use |
| Delivered link lifetime | Expires 24 hours after delivery, never extends an already expired link | Earlier revocation always wins; token expiry enforced server-side |
| Cancellation link behavior | Revoke immediately on cancellation; replace on material recipient/address changes | No personal data on revoked link |
| Retry limit | One same-day retry after initial failure | Future window and dispatcher policy required |
| COD | MMK whole amounts, explicit COD or prepaid | Unknown is a hold; zero is allowed only with explicit payment mode |
| Record retention | Configurable; no production default approved yet | Set dispute/retention/deletion period before real customer data is onboarded |

Policies must be versioned. A policy change does not alter existing dispatched orders without an authorized operational action. The static demo's historical clock/windows do not establish live eligibility.

## 10. Operational exceptions and recovery

| Trigger | Customer sees | Dispatcher/rider action |
| --- | --- | --- |
| Unsupported township/missing phone | No editable location until resolved | Hold, correct or reject service area; never dispatch on AI guess |
| Multiple candidate COD amounts | Correct public context only after review | Select source-backed amount or mark explicit prepaid; record correction |
| AI/model timeout | No broken customer promise | Finish rules-only result with manual-review reason; retry without overwriting edits |
| Customer never replies | Pending confirmation | Keep Amber held; resolve manually; eligible Green may proceed |
| Three wrong checks | Link locked; contact shop | In-app exception; review recipient, reissue link and revoke old one |
| Duplicate or forwarded link | Safe public context then gate | Token bound to one parcel; no global customer search |
| Pin outside radius/township | Blocked explanation; keep original pin | No automatic fee, acceptance or tomorrow promise |
| Cutoff/departure crossed while form open | Save rejected; refresh summary and contact shop | Preserve user's draft separately; do not overwrite departed route |
| No GPS/map/voice availability | Manual pin/text or shop assistance | Keep known coordinates; read instructions visually; no fake geocoding |
| Buyer not answering/not home | Attempt/retry summary after accepted result | Record reason, future retry or return; attempts retained |
| Can't find place/buyer refused | Appropriate failed-delivery status | Same failure flow; dispatcher sees cause and disposition |
| COD amount differs | Recorded amount on delivery summary | Discrepancy flagged, actual preserved, reason/reconciliation required |
| Duplicate/replayed request | Existing accepted result | Idempotent acknowledgement; no repeated cash/attempt count |
| Stale buyer/rider edit | Changed details/review needed | Reject stale version, show newer state, resolve with authorized actor |
| Rider reassigned while offline | No internal assignment details exposed | Preserve local outcome and raise conflict; do not silently discard or accept unauthorized changes |
| Server save fails/offline | Pending/failed, never false success | Persist permitted local draft/action; show retry and acknowledgement state |
| Return marked but not at hub | Return in progress | Hub physically acknowledges receipt before `returned` |
| Parcel lost/damaged | Contact shop/hub status, no invented outcome | Record manual incident and place on hold; dispatcher must resolve before route close; claims/refunds are outside MVP |

No automated SMS/shop notification is implied by an in-app exception. MVP notifications are dashboard/in-app signals plus manual shop chat sharing. A toast that says notified is insufficient evidence of external delivery.

## 11. Record and event contract

This describes shared business information for design/backend alignment; it does not prescribe a hosting vendor or database.

| Record | Minimum information |
| --- | --- |
| Workspace/hub policy | IDs, supported geography, timezone, cutoff/windows, retry/radius rules, policy version |
| Shop | ID/hub relationship, display name/avatar, trusted chat context, contact/support path |
| Order/parcel | ID, shop/hub, external reference, source text/access scope, normalized fields, payment mode, expected COD, item/context, custody/lifecycle, version |
| Address field | Value, origin `rule/dictionary/ai/manual/buyer`, source snippet/reference, reason codes, reviewed actor/time |
| Location | Original anchor, anchor evidence/quality, current coordinate, township ID, confirmation/verification and timestamp |
| Customer link | Opaque token reference, order ID, status/expiry, failure count, issue/revoke history; no raw token in normal logs |
| Customer response | Answer, window/date, note, pin, response version, submitted/accepted time, policy version |
| Route/stop assignment | Route ID, rider/hub, delivery day, base sequence, active stop, accepted sequence version, departure time |
| Delivery attempt | ID, order/cycle/route/rider, outcome, reason, observation time, receipt time, retry/return disposition, operation ID |
| Collection | Attempt/order, expected vs actual MMK, prepaid marker, discrepancy reason, immutable original entry and correction trail |
| Return/cash handover | Sender/receiver, declared vs received parcel/cash counts, acknowledgement time, dispute reason |
| Event | Unique event/operation ID, actor/role, record ID/version, type, times, changes/reason, server acknowledgement |

Commands include create batch, normalize/review order, correct field, issue/revoke link, verify phone, submit confirmation, receive parcel, assign/unassign, dispatch route, submit delivery result, record failure, plan retry, request/receive return, submit/acknowledge closeout and record correction. Each command has actor authority, expected record version, idempotency identity, validated payload and an accepted/rejected result.

Representative events include `order_created`, `address_triaged`, `field_corrected`, `buyer_link_issued`, `buyer_link_locked`, `buyer_confirmed`, `parcel_received`, `rider_assigned`, `route_dispatched`, `delivery_completed`, `attempt_failed`, `retry_scheduled`, `return_requested`, `return_received`, `cash_discrepancy_recorded`, `cash_handover_received` and `route_closed`.

Sensitive payloads are not copied into general analytics events. Unauthenticated responses do not return protected fields for the browser to hide; backend response projection is required.

## 12. Connectivity and consistency behavior

- Customer reads public context online; after verification, an unsent draft may be preserved only with a defined expiry/privacy policy. Offline save is visibly pending and does not reorder a remote rider until accepted.
- Rider explicitly downloads their assigned queue. Cache includes the minimal assigned stop details needed for offline work and supports app restart after first successful preparation. First-ever offline access explains that no queue has been downloaded.
- Each action has one stable operation ID across retries. Reconnect sends pending commands, receives accepted/conflict results and updates only acknowledged projections.
- Server validates token/role/assignment, current version, operational deadline and payment/geography rules. Device time is never authoritative for cutoff/expiry.
- A stale customer change must not reopen delivered/returned/cancelled work. A stale route refresh must not erase a pending delivery result.
- Pending sync and last accepted sync time appear explicitly; browser online status alone cannot show Synced. Conflicts require an owner and retry/review path.
- One app/device losing storage warns that local unsent data may be unavailable; it does not imply a server record was erased. Sign-out removes protected downloaded records after accounting for pending actions.

## 13. Screen states and UX constraints

Every data screen needs initial/loading, ready, empty, failed-load and retry states. Every write needs draft, validating, saving/pending, accepted and rejected states. Disabled actions explain the blocking reason.

Customer adds public/gated, incorrect digits, locked, revoked/expired, invalid token, no GPS, unavailable map, out-of-boundary, cutoff/departed, confirmed and terminal variants. Rider adds no assignment, offline-ready, never-cached, changed stop, undo, prepaid, cash mismatch, attempt disposition, pending-sync/conflict and completed-route variants. Admin adds parser progress, partial batch failure, manual review, duplicate warning, no eligible orders and unresolved closeout variants.

UI design must verify Burmese and English labels, non-color status cues, keyboard/form focus, screen-reader errors and responsive behavior. Brand/item imagery needs meaningful fallbacks. The customer card performance goals from the PRD are under 200 KB for initial content and first content under two seconds on 3G; define map/font lazy loading and measure them rather than claim success now. Initial parser response under two seconds and 50 orders under five minutes are test targets, not current results. Customer/rider flows must remain usable without relying on a specific map app or installed Burmese voice.

Live-map tracking, exact rider location, fabricated ETAs and unmeasured ROI should not appear in the core UX. Pilot metrics need explicit definitions: first-attempt success is parcels delivered on their first recorded attempt divided by parcels with a first attempt in the period; cancelled/unattempted parcels are excluded and reported separately. Green rate is Green at initial parse divided by successfully parsed sample orders, before manual edits. Report sample size and date range.

## 14. Acceptance scenarios for the functional prototype

These are workflow acceptance requirements, not a list of certified production tests. Current domain/controller tests exercise local business behavior and application handlers. See `FUNCTIONAL_REVIEW.md` for the walkthrough and the browser/provider/backend verification limits.

| Test | Given / action | Required result | Coverage |
| --- | --- | --- | --- |
| T01 | Paste 20 separated mixed-encoding samples | 20 preview records; original text retained; Unicode output | A01–A02 |
| T02 | Missing phone/unsupported area | Red with reason; no dispatch eligibility | A03–A04 |
| T03 | Valid phone/place but vague landmark | Amber plus highlighted phrase and manual/buyer resolution | A04, C03 |
| T04 | AI returns phone/COD or unsupported fields | Reject unsupported AI fields; rules/manual values retained | A02–A04 |
| T05 | AI unavailable midway through batch | Completed records stay; failed rows retry/manual; demo fallback labelled | A02 |
| T06 | Duplicate intake/retry | Warning or same operation result; no silent duplicate parcel | A01–A02 |
| T07 | Correct phone/place/payment | Rules rerun; blockers clear only when all gates pass | A04, A06 |
| T08 | Copy customer link | Copy success; no unsupported sent/received claim | A05 |
| T09 | Open unverified customer link | Shop/item/payment/status only; protected fields absent | C01–C02 |
| T10 | Submit malformed vs incorrect four digits | Malformed consumes no try; third incorrect attempt locks | C02 |
| T11 | Open locked link on another device; reissue | Still locked; new link works; old link revoked | A05, C08 |
| T12 | Move pin repeatedly near radius limit | Every move measured from original anchor; >500 m blocked | C03 |
| T13 | Move within radius across township boundary | Block/review; no automatic fee or route change | C03 |
| T14 | Anchor is unknown or GPS denied | Unknown anchor held; GPS denial permits manual known-anchor adjustment | C03, C08 |
| T15 | Confirm At home/window/note | One saved response; rider sees accepted version and changed badge | C04–C05, R01–R02 |
| T16 | Select Leave with security for COD | Requires recipient able to pay; rider still collects actual amount | C04, R05 |
| T17 | Save while cutoff/departure occurs | Reject stale write; retain draft; show read-only latest summary | C06 |
| T18 | Assign held or already assigned order | Reject with explicit blocker | A06 |
| T19 | Dispatch valid received/assigned parcels | Record departure; customer edits freeze; rider work is available | A07, R01 |
| T20 | Buyer reschedules before departure | Stable future-window ordering; no false ETA | A07, R01 |
| T21 | Current rider stop while other records update | Active stop remains; changes require visible refresh/review | R01–R02 |
| T22 | Google Maps or voice unavailable | Usable coordinate/text fallback; no fabricated navigation/voice success | R03 |
| T23 | Delivered then Undo within two seconds | No completion/cash event; same stop remains | R04 |
| T24 | Undo expires then cash dialog cancelled/reload | Stop incomplete or explicit draft; no hidden delivered state | R04–R05 |
| T25 | Confirm exact COD; submit same operation twice | One completion and one collection | R05 |
| T26 | Enter invalid/negative/fractional or nonzero prepaid cash | Reject; actual zero on COD requires discrepancy reason; no accidental completion | R05 |
| T27 | Record COD mismatch with reason | Handoff recorded; discrepancy visible; closure requires resolution | R05, A08–A09 |
| T28 | Failed attempt then eligible retry | Attempt retained; next future window; count not reset | R06 |
| T29 | Retry limit reached/no future window | Return/replan path; no endless/past-window retry | R06, A08 |
| T30 | Rider requests return | Return pending until named hub receiver acknowledges | R06–R07, A09 |
| T31 | Shop cancels before vs after departure | Before: cancel/revoke. After: operational return request | A04, A08 |
| T32 | Offline handoff then reconnect twice | Pending indicator then single accepted completion/collection | R08 |
| T33 | Rider reassigned while action is offline | Preserve observed action, raise review conflict, no silent cash loss | R08, A08 |
| T34 | Stale confirmation arrives after delivery | Rejected; delivered record unchanged | C06, R08 |
| T35 | Handover cash/returns with mismatch | Submission distinct from receipt; dispute blocks closeout | R07, A09 |
| T36 | Close route with pending action/return/cash | Reject closure with next action; fully accounted route closes | A09 |
| T37 | Link reaches expiry/revocation/invalid token | Safe unavailable page; no protected record data | C08 |
| T38 | Merchant/rider requests unrelated order | Access denied, including direct URL/API request | All role boundaries |
| T39 | Keyboard/mobile/Burmese form run | Readable labels/line height, correct focus/errors and reachable actions | All screens |
| T40 | Metrics shown with demo data | Labelled samples; counts and denominators defined; no measured ROI claim | A03, reporting |

## 15. Completion gates and next work

**Functional outline complete:** every core/operational feature has an owner, action, state, business rule, error/recovery and acceptance scenario. This document establishes that baseline; courier defaults remain changeable and are explicitly marked.

**Functional prototype gate:** the local intake-to-closeout workflows and recovery controls are now implemented; `IMPLEMENTATION_BACKLOG.md` records current coverage and `FUNCTIONAL_REVIEW.md` explains how to walk them. T01–T40 remain the acceptance baseline. Provider/server-dependent cases are explicit simulations or integration checks; local tests do not certify server guarantees. Browser/device review is still required before calling the UX verified.

**UI/UX ready for backend:** review all role screen variants, complete one successful and one failed parcel journey, test with shop/dispatcher/rider participants, finalize field copy and resolve the top usability issues. Confirm coverage/cutoff/retry/contact/retention defaults with the pilot hub. Separate customer/rider shells are designed now; native app decisions wait for actual device needs.

**Backend and pilot ready:** implement authenticated role boundaries, real persistence and validated state transitions, secure token/expiry controls, parser/maps integration, idempotent offline synchronization and conflict handling. Verify on separate devices, a budget Android phone and supported desktop/mobile browsers. No local demo test proves any of these server guarantees.

The next gate is a functional walkthrough of the implemented admin intake/review/assignment, customer deadline/link recovery and rider return/cash closeout. Fix defects found in that review, then refine UI/UX and implement the backend against these contracts.
