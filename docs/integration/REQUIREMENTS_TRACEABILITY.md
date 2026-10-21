# Requirements traceability

Sources reviewed: PRD v2 at `C:\Users\ZL_shit_H\Downloads\LannPya_AI_PRD_v2.docx`,
the workspace [implementation guide](../../LANNPYA_AI_IMPLEMENTATION_GUIDE.md), the
existing API contract/handoff, and the actual FastAPI app/schemas/services. The PRD lives
in Downloads, not Git. The workspace contains no separate IA or use-case diagram after
searching available project files. No frontend source package is present. This matrix
classifies demonstrated backend evidence; it does not claim the frontend is implemented.

| Requirement | PRD / guide intent | Backend status | Evidence / limitation |
| --- | --- | --- | --- |
| Middleware for social shops and existing couriers | Orders pass from merchants/dispatchers to third-party delivery | Implemented foundation; integrations missing | Order/rider REST and IDs; no courier adapters, tenant auth, onboarding, or external tracking connector |
| Burmese/Myanglish parse and encoding normalization | Unicode/Zawgyi handling; structured address; inline correction | Implemented and locally tested | Deterministic rules, controlled Yangon township dictionary, source metadata; arbitrary free text remains ambiguous |
| Phone and COD | Deterministic extraction, validation, no model fabrication | Implemented and locally tested | Rules parser and typed schemas; phone format does not prove ownership; COD null remains distinct from zero |
| AI enriches difficult address fields | Model extracts landmarks/floor/instructions behind switchable adapter | Interface implemented; external provider missing, mock behavior verified | Mock adapter intentionally supplies no simulated address values; no paid SDK or model calls |
| Explainable triage | GREEN map verified, AMBER needs buyer, RED critical missing | Implemented; default green impossible without trusted data | Deterministic reasons/category in response; no numeric score. Synthetic test catalog is test-only |
| Dispatcher edits/persists order | Parse, review, correct and manage order | Implemented and tested locally | Protected APIs, version checks, provenance/events; dev-only auth, no production identity |
| Secure buyer card | Link, minimal pre-verification context, last-four check and lockout | Implemented and tested locally | Hashed link, attempts, short Bearer, expiry/revoke; branding/item absent, messaging unsent, phone ownership not proved |
| Buyer location/time/instructions | Pin and availability, courier zones/cutoffs, request feedback | Implemented with review gates | Changes may be pending; default boundaries unavailable; initial pin not canonical verification; policies configurable |
| Rider queue/delivery | Assigned queue, navigation, start/deliver/fail, COD | Implemented and tested locally | Snapshot cursor, optional Maps URL, events/receipts; no rider GPS, route optimization, call or remittance |
| Browser Vite/Leaflet app | Vanilla modules, Vite, map, 3 main views | Documented only; unverified | Guide names stack; frontend source/package not found in repository; no Vite/browser run performed |
| Dual live/fallback engine | Switch to in-memory mock if API offline | Documented only; potentially unsafe as worded | Backend has no mode protocol; must explicitly show demo and never convert failed live mutation to simulated success |
| 500m map boundary and approximate AI point | Buyer pin ring around guessed point | Unsupported without real reference | Backend refuses fabricated origin; only trusted reference/boundary policy can support decisions |
| Confidence 68% -> 99% | Percent animation after buyer pin | Inconsistent with backend and safe requirements | No percentages; pin does not prove independent location accuracy or upgrade confidence |
| Gate photos, masked calls, message send, route polyline | Present in visual/pitch concept | Missing backend / simulation only | No APIs, uploads, telecom, map routing service, message provider or cash ledger |
| Accessibility, usability and speed metrics | AA, touch targets, under-2-second and pilot metrics | Documented only / unverified | Cannot assess without source and usability/performance test data |
| Business price and savings | SaaS/pay-per-parcel estimates | Product assumptions only | No subscriptions, billing, outcome measurement or verified ROI data |
| Separate information architecture/use-case diagram | Project design deliverables | Not found | PRD text has system flow; no separate diagram file was identified |

## Resolution order

Use the implemented OpenAPI contract and server-side rules for API behavior. Treat the
frontend implementation guide as product/UI intent where it conflicts with implemented
schemas or security: e.g. JWT vs opaque Bearer, `READY_FOR_DELIVERY` vs
`READY_FOR_DISPATCH`, committed pin vs review proposal, and percent confidence vs
categorical triage. Product/UI-only features can remain visibly simulated until product
decisions and backend services exist.
