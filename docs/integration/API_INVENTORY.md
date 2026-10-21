# Backend API inventory

Generated from FastAPI 0.7.0 application OpenAPI on 2026-10-21. The snapshot [OPENAPI.json](OPENAPI.json) is generated from `create_app(Settings(_env_file=None, order_management_enabled=False)).openapi()`; it contains schemas/routes only, no live database rows or credentials.

**Actual operations: 29.** Request/response properties, parameter constraints, enum values and response codes are in the snapshot. Authentication is also indicated by each operation's OpenAPI security field.

## Runtime and safety notes

- Base URL: `http://127.0.0.1:8000`; append the full path shown below. `/health` is liveness only.
- Protected management routes require `X-Dev-Access-Token`, local/test config, enabled local DB, server-bound actor, and actual loopback peer. Production fails closed.
- Buyer capability routes are accessible by secret link and verification; sensitive mutations/details need Bearer authorization. These are not dispatcher credentials.
- Stateless parse has no database side effect. Public buyer rate limit and confirmation/link operations use configured local/test database; persistent order/rider routes use SQLite/PostgreSQL sessions.
- Error responses follow `ErrorResponse`; validation returns 422, stale or invalid state commonly 409, unauthorized 401/403, expired 410, locked 423, throttled 429, unavailable 503. Consult per-operation OpenAPI response list.
- Integration-ready means schemas and local HTTP behavior are implemented; it does not mean production authentication or access from another computer is available.

## Complete endpoint inventory

Columns: purpose (route summary), auth (from OpenAPI security + route dependencies), request (Pydantic schema/query), response (success status/schema), errors (documented codes), effects/database (implementation review), readiness (integration boundary).

| Method | Full route | Purpose | Auth | Request | Success response | Error statuses | Effects / DB | Integration readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | Health | Public stateless | ? | 200 HealthResponse | ? | No DB; parse is stateless. | Ready: liveness only. |
| POST | `/api/orders/parse` | Parse an order with rules-first hybrid assistance (external AI disabled) | Public stateless | ParseRequest | 200 ParseResponse | 422, 502 | No DB; parse is stateless. | Ready locally; stateless; no save. |
| POST | `/api/orders` | Create Order | Local dev token; loopback; server-bound actor | CreateOrder | 201 OrderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/orders` | List Orders | Local dev token; loopback; server-bound actor | ?page:query, page_size:query, status:query, confidence:query, q:query | 200 OrderPage | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/orders/{order_id}` | Get Order | Local dev token; loopback; server-bound actor | ?order_id:path | 200 OrderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| PATCH | `/api/orders/{order_id}` | Correct Order | Local dev token; loopback; server-bound actor | CorrectOrder + order_id:path | 200 OrderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| PATCH | `/api/orders/{order_id}/status` | Change Status | Local dev token; loopback; server-bound actor | ChangeStatus + order_id:path | 200 OrderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/orders/{order_id}/events` | Get Events | Local dev token; loopback; server-bound actor | ?order_id:path, page:query, page_size:query | 200 EventPage | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/users` | List Users | Local dev token; loopback; server-bound actor | ?role:query, limit:query | 200 UserResponse[] | 401, 403, 404, 409, 422, 503 | Reads bounded users list from local/test DB. | Ready on same-machine local dev only; no production auth. |
| POST | `/api/orders/{order_id}/confirmation-link` | Generate Link | Local dev token; loopback; server-bound actor | ?order_id:path | 201 LinkResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes order, link/reference/request/event records in local/test DB; mutations transactional. | Ready on same-machine local dev only; no production auth. |
| POST | `/api/orders/{order_id}/confirmation-link/revoke` | Revoke Link | Local dev token; loopback; server-bound actor | ?order_id:path | 200 RevocationResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes order, link/reference/request/event records in local/test DB; mutations transactional. | Ready on same-machine local dev only; no production auth. |
| POST | `/api/orders/{order_id}/location-reference` | Location Reference | Local dev token; loopback; server-bound actor | SetLocationReference + order_id:path | 201 LocationReferenceResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes order, link/reference/request/event records in local/test DB; mutations transactional. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/orders/{order_id}/buyer-requests` | Buyer History | Local dev token; loopback; server-bound actor | ?order_id:path, page:query, page_size:query | 200 BuyerHistoryPage | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes order, link/reference/request/event records in local/test DB; mutations transactional. | Ready on same-machine local dev only; no production auth. |
| PATCH | `/api/orders/{order_id}/buyer-requests/{request_id}` | Review Buyer Request | Local dev token; loopback; server-bound actor | ReviewBuyerRequest + order_id:path, request_id:path | 200 BuyerReviewResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes order, link/reference/request/event records in local/test DB; mutations transactional. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/confirm/{token}` | Card | Link capability; Bearer on sensitive actions | ?token:path | 200 BuyerCardResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Rate-limit + read minimal link/order card from local/test DB. | Ready with valid buyer capability/session; public deployment needs security review. |
| POST | `/api/confirm/{token}/verify` | Verify | Link capability; Bearer on sensitive actions | VerifyBuyer + token:path | 200 BuyerAuthorizationResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes hashed link/session/rate-limit/request/order/event records in local/test DB; mutation is transactional. | Ready with valid buyer capability/session; public deployment needs security review. |
| GET | `/api/confirm/{token}/details` | Details | Link capability; Bearer on sensitive actions | ?token:path, authorization:header | 200 BuyerDetailsResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads link/session/order from local/test DB. | Ready with valid buyer capability/session; public deployment needs security review. |
| PATCH | `/api/confirm/{token}/location` | Location | Link capability; Bearer on sensitive actions | BuyerLocation + token:path, authorization:header | 200 BuyerActionResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes hashed link/session/rate-limit/request/order/event records in local/test DB; mutation is transactional. | Ready with valid buyer capability/session; public deployment needs security review. |
| PATCH | `/api/confirm/{token}/response` | Response | Link capability; Bearer on sensitive actions | BuyerResponse + token:path, authorization:header | 200 BuyerActionResult | 401, 403, 404, 409, 410, 422, 423, 429, 500, 503 | Reads/writes hashed link/session/rate-limit/request/order/event records in local/test DB; mutation is transactional. | Ready with valid buyer capability/session; public deployment needs security review. |
| POST | `/api/riders` | Create Rider | Local dev token; loopback; server-bound actor | RiderCreate | 201 RiderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/riders` | List Riders | Local dev token; loopback; server-bound actor | ?page:query, page_size:query, operational_status:query | 200 RiderPage | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/riders/{rider_id}` | Get Rider | Local dev token; loopback; server-bound actor | ?rider_id:path | 200 RiderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| PATCH | `/api/riders/{rider_id}` | Patch Rider | Local dev token; loopback; server-bound actor | RiderPatch + rider_id:path | 200 RiderResponse | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/riders/{rider_id}/queue` | Rider Queue | Local dev token; loopback; server-bound actor | ?rider_id:path, cursor:query | 200 QueueResponse | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| POST | `/api/orders/{order_id}/assign` | Assign Order | Local dev token; loopback; server-bound actor | AssignOrder + order_id:path | 201 AssignmentResult | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| POST | `/api/orders/{order_id}/unassign` | Unassign Order | Local dev token; loopback; server-bound actor | UnassignOrder + order_id:path | 200 AssignmentResult | 401, 403, 404, 409, 422, 503 | Reads/writes order and event records through SQLAlchemy local/test DB session. | Ready on same-machine local dev only; no production auth. |
| PATCH | `/api/orders/{order_id}/assignment` | Sequence Order | Local dev token; loopback; server-bound actor | SequencePatch + order_id:path | 200 AssignmentResult | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| GET | `/api/orders/{order_id}/assignments` | Assignment History | Local dev token; loopback; server-bound actor | ?order_id:path, page:query, page_size:query | 200 AssignmentPage | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |
| PATCH | `/api/riders/{rider_id}/deliveries/{order_id}/status` | Delivery Action | Local dev token; loopback; server-bound actor | DeliveryAction + rider_id:path, order_id:path | 200 ActionResult | 401, 403, 404, 409, 422, 503 | Reads/writes rider profile/assignment/order/action receipt/event/queue snapshot in local/test DB. | Ready on same-machine local dev only; no production auth. |

## Implementation dependencies and behaviors

- Route registrations: `backend/app/main.py`, `app/api/routes.py`, `app/api/order_management.py`, `app/api/buyer_confirmation.py`, `app/api/riders.py`.
- Validation: `app/schemas/orders.py`, `management.py`, `buyer.py`, `riders.py`; unknown body fields are forbidden on mutation schemas.
- Authorization: `app/core/dev_access.py`, `buyer_access.py`; per-route role/merchant/rider scope lives in service layer.
- Persistence: SQLAlchemy models/migrations under `app/db/` and `migrations/versions/`; alembic head `0003_rider_copilot`.
- Lifecycle: `app/domain/lifecycle.py`; assignment state is distinct from order status; optimistic versions guard mutations.
- CORS: exact configured origins, GET/POST/PATCH, Content-Type/X-Dev-Access-Token/Authorization; no cookie credentials.
- Exceptions: `app/main.py`; error envelope is `{error:{code,message,details}}`; input values and DB internals are suppressed.
- AI extraction interface is mock/disabled only; no provider API call or paid SDK is activated.

## Requirements traceability (source guide/PRD and implemented evidence)

| Requirement | Status | Evidence / boundary |
| --- | --- | --- |
| Middleware for existing merchants/couriers | Implemented foundation | REST order/rider workflows; no courier SaaS integration or merchant onboarding. |
| Burmese/Myanglish parsing | Implemented; local tests | Deterministic phone/COD/digit/township parsing; landmarks/instructions conservative, AI mock only. |
| Secure buyer confirmation | Implemented; local tests | Hashed links, lockout, bounded Bearer, proposals/review; no messaging sender or phone ownership proof. |
| Rider Copilot | Implemented; local tests | Scoped queue, assignments, navigation URL if coordinates exist, delivery/COD assertion. No GPS/route optimizer. |
| Frontend Vite/Leaflet architecture | Documented only | Guide says Vite 6.4.4, vanilla ES modules, Leaflet 1.9.4; frontend sources absent. |
| Offline browser fallback | Documented only; unverified | Must be explicit demo simulation and cannot turn a failed live write into success. |
| 500m geofence from approximate AI location | Unsupported as described | Backend uses trusted reference/boundary only; no default trusted dataset. |
| 99% confidence after pin | Inconsistent and must not be implemented | Server emits categorical deterministic confidence, no percentages; pin does not create trusted proof. |
| Masked calling, gate photo, route polyline, COD remittance | Missing / simulation only | No matching API/service/storage integration. |
| Separate information architecture / use-case diagram | Not found | No separate IA or diagram file was found in inspected workspace/accessible project dirs. PRD and implementation guide are present. |

No frontend source or executable package was available, so Vite commands, browser behavior, actual request transformation, and dual-engine fallback have not been verified.
