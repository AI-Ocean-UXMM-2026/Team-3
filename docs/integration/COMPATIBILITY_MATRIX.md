# Frontend and backend compatibility matrix

Reviewed against the local implementation guide and live FastAPI 0.7.0 schemas on
2026-10-21. Frontend source is not present; its actual request code and fallback behavior
remain unverified. The guide's API table is a partial, stale contract.

| Frontend guide operation or assumption | Actual backend contract | Classification | Required integration behavior |
| --- | --- | --- | --- |
| `GET /health` | Public `GET /health`; liveness only, no DB/provider readiness | Exact path; semantics differ | Use as connection/liveness probe, never infer DB persistence from health alone |
| `POST /api/orders` with normalized Burmese text | Protected; JSON is `{merchant_id,raw_text}` OR `{merchant_id,structured}`; 201 `OrderResponse`, DRAFT | Compatible with request transformation; auth mismatch | Keep original raw text and selected merchant UUID; authenticate local caller on same machine; don't post parse response wholesale |
| `POST /api/orders/parse` | Public/stateless parser; `{raw_text}`; 200 `ParseResponse`; saves nothing | Missing from guide, backend capability | Parse first for review, then explicitly create order |
| `PATCH /api/orders/{id}/status` | Protected, `{expected_version,status,...}`; explicit lifecycle enum; 200 Order | Request transformation; frontend lifecycle enum stale | Use response `version`; `READY_FOR_DELIVERY` is not valid; readiness is `READY_FOR_DISPATCH` with AMBER acknowledgment and workflow checks |
| `POST /api/orders/{id}/confirmation-link` | Protected; 201 link result containing opaque URL/token reference and expiry; DB record/event | Path match; response and auth mismatch | Treat `confirmation_url` as a frontend route. Backend contract uses a separate secret capability; never put role token in the link |
| `POST /api/confirm/{token}/verify` | Public link capability; body `{last_four: "1234"}` (four ASCII digits); returns opaque short-lived Bearer | Request path matches; credential type mismatch | It is not JWT. Hold Bearer in memory; three failures lock link; do not infer 4 digits prove phone ownership |
| `PATCH /api/confirm/{token}/location` | Link + buyer Bearer; `{request_id,latitude,longitude,initial_pin_acknowledged?}`; creates action/proposal; may return `REVIEW_REQUIRED` | Request transform and response semantics mismatch | Coordinates are decimal/range validated; initial pin is not applied as trusted canonical location until review; no photo field |
| Buyer `GET /api/confirm/{token}` and `/details` | Public card is minimal; details require buyer Bearer | Extra backend capability absent from guide | Show only returned fields; no customer name, phone, address or pin before verification |
| Buyer `PATCH /api/confirm/{token}/response` | Buyer Bearer; `AVAILABLE`, `INSTRUCTIONS`, `RESCHEDULE`, `LEAVE_WITH_SECURITY`; policy can defer action for review | Missing from guide | Use request IDs and render `REVIEW_REQUIRED` as pending, never as a saved dispatch change |
| Dispatcher review | Protected `GET buyer-requests`, `PATCH buyer-requests/{history id}` with expected version, decision and reason | Missing from guide | Use history record path ID; approval keeps order in review and does not establish geospatial trust |
| Rider queues/navigation | Protected `GET /api/riders/{rider_id}/queue`; returns assignment snapshot, optional map URL only for available coordinates | Missing from guide | Poll documented cursor; don't claim live GPS/turn-by-turn; coordinates can be absent/unverified |
| Rider starts/completes/fails | Protected rider status PATCH with request UUID/version/action; explicit COD assertion required when applicable | Missing from guide; status semantics differ | Use rider endpoint to keep assignment/order/event atomic; COD flag is an attestation, not remittance/payment |
| Automatic mock fallback after failed API request | Not a backend contract; frontend behavior not inspected | Frontend assumption unverified; unsafe if silent | Surface `CONNECTION_ERROR`; only enter `DEMO_SIMULATION` through explicit user-selected demo mode |
| Confidence score rises to 99% after buyer pin | Backend emits GREEN/AMBER/RED rule classification; no percentages; pin doesn't create independent verification | Incompatible | Show distinct location provenance/review state; never turn pin placement into 99% or GREEN |
| 500m ring around approximate AI location | Movement policy uses a real stored trusted reference and configured boundary resolver; no fabricated origin | Incompatible unless reference exists | Don't display an enforced 500m geofence unless an actual backend-trusted origin/policy is supplied |
| Gate photo, masked calls, routes, hub balance/COD remittance | No corresponding backend APIs or persisted fields/services | Unsupported/simulated | Clearly label presentation simulation; do not imply external call, image upload, route service or remittance occurred |
| Frontend Vite origin `localhost:3000` | Default CORS includes 3000, 5173 and 5500 loopback spellings; origins configurable | Compatible locally | Exact scheme/host/port must be allowed; private APIs also require the connection to arrive from loopback |

## Data mappings

| Frontend concept | Backend field/value |
| --- | --- |
| Parsed buyer phone | Parse `address.phone_number`; stored Order `customer_phone`; domestic normalized digit string |
| Merchant/store ID | Required UUID `merchant_id`; not a free-form shop label |
| COD | Parse response whole integer/null; persisted order/queue exact MMK digit string/null; null is not zero |
| Township | Canonical controlled dictionary name (e.g. `Hlaing`); input aliases normalized by backend |
| GPS point | Decimal latitude/longitude pair or null; buyer pin response can be pending review |
| Confidence | `GREEN`, `AMBER`, `RED`; independent from delivery status |
| Order lifecycle | `DRAFT`, `NEEDS_REVIEW`, `AWAITING_CONFIRMATION`, `CONFIRMED`, `READY_FOR_DISPATCH`, `ASSIGNED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `FAILED`, `CANCELLED` |
| Buyer authorization | Opaque Bearer credential, short-lived; not JWT; separate from development access |
| Rider assignment | Separate assignment record; order status alone does not create a queue item |
| Timestamp/version | ISO 8601 UTC plus monotonic optimistic `version` for mutations |

The frontend guide's statement that text is parsed and saved in one `POST /api/orders`
is partly supported: raw text is parsed server-side during create, but the response remains
DRAFT and dispatch review is still required. Parse-first and create-raw are both available.
