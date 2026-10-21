# User journey to implemented APIs

Routes and request shapes below are from live app registration/OpenAPI. Local protected
routes currently require server-bound development access from loopback; buyer routes use
the token/session boundary shown. “Pending” is a persisted buyer proposal, not an approved
delivery change.

## A. Dispatcher

| Step | API | Contract and outcome |
| --- | --- | --- |
| Receive Messenger/Viber text | External source, no connector | Manual operator input only; no Messenger/Viber ingestion exists |
| Parse | `POST /api/orders/parse` | Public/stateless `{raw_text}` -> structured response, reasons, field sources; no save |
| Review extracted fields | Client presentation | Read response; edit/confirm inputs manually; never send source metadata back as trust flags |
| Create | `POST /api/orders` | Local role auth; `{merchant_id,raw_text}` or `{merchant_id,structured}` -> 201 DRAFT Order |
| Correct | `PATCH /api/orders/{order_id}` | Local role auth; editable field(s) plus `expected_version`; manual provenance/retriage |
| Read/filter/search | `GET /api/orders`, `GET /api/orders/{order_id}` | Local role auth; pagination, status/confidence/search; merchant scope enforced |
| Start review | `PATCH /api/orders/{order_id}/status` | Latest version; DRAFT -> NEEDS_REVIEW, with role/lifecycle rules |
| Generate buyer link | `POST /api/orders/{order_id}/confirmation-link` | Local role auth; eligible phone/order; creates hashed link record/event; returns frontend route and expiry; caller must send manually |
| Review buyer changes | `GET /api/orders/{order_id}/buyer-requests`, `PATCH /api/orders/{order_id}/buyer-requests/{history_id}` | Local role auth; review history and approve/reject with latest version/reason; approval leaves review |
| Confirm/ready | `PATCH /api/orders/{order_id}/status` | Explicit transition; AMBER needs dispatcher acknowledgment; unresolved requests block readiness |
| Assign rider | `GET/POST/PATCH /api/riders...`, `POST /api/orders/{order_id}/assign` | Local Dispatcher/Admin; choose rider, version and stop sequence; creates separate assignment |
| History | `GET /api/orders/{order_id}/events`, `GET .../assignments` | Local role auth; paginated audit history |

Gaps: no message connector, merchant onboarding endpoint, notification sender, branded shop
record or external CRM integration. `GET /api/users` is a protected limited lookup, not user
creation or production identity management.

## B. Buyer

| Step | API | Contract and outcome |
| --- | --- | --- |
| Open link/card | `GET /api/confirm/{token}` | Link capability; minimal status/reference/expiry, no private address/phone/GPS |
| Verify last 4 | `POST /api/confirm/{token}/verify` | `{last_four:"1234"}` -> short-lived opaque Bearer; max three failed guesses locks link |
| Read sensitive card | `GET /api/confirm/{token}/details` | Link + Bearer; permitted delivery details/policy, excludes full registered phone/name |
| Submit doorstep pin | `PATCH /api/confirm/{token}/location` | Link + Bearer; request UUID and coordinates; initial pin requires acknowledgment and may await review |
| Availability/instructions | `PATCH /api/confirm/{token}/response` | `AVAILABLE`, `INSTRUCTIONS`, `LEAVE_WITH_SECURITY` |
| Request schedule | Same `/response` route | `RESCHEDULE` plus explicit-offset time window; cutoff/unsupported requests can require review |
| Observe result | Action response, later fresh details/card | `REVIEW_REQUIRED` is not canonical order update; dispatcher resolution is separate |

Gaps: no email/SMS/Messenger delivery, no buyer notification of dispatcher decision, no
photo upload, no credential account or strong proof of phone ownership. Four digits plus
secret link is the implemented flow, with documented limitations.

## C. Rider

| Step | API | Contract and outcome |
| --- | --- | --- |
| Retrieve assigned deliveries | `GET /api/riders/{rider_id}/queue` | Server-bound Rider actor (or Dispatcher/Admin); bounded snapshot, only active eligible assignments |
| Read verified/current delivery information | Same queue; optionally `GET /api/orders/{id}` for privileged dispatcher only | Queue separates buyer-confirmed coordinates from independent location verification; only appropriate notes/fields |
| Navigate | Queue `navigation_ready`, `navigation_url` | Optional URL only when backend has coordinates accepted by queue rules; user click; no route optimization |
| Poll updates | Same queue with last `cursor` | Five-second suggested polling, no overlap; unchanged preserves list, changed replaces whole list |
| Start | `PATCH /api/riders/{rider_id}/deliveries/{order_id}/status` | `{request_id,expected_version,action:"START"}`; authorized assignment/state required |
| Deliver/COD | Same endpoint | `DELIVERED` and explicit `cod_collected:true` where COD required; no payment/remittance service |
| Report failure | Same endpoint | `FAILED`, enumerated failure reason, optional private note; event/assignment close |
| Observe history | `GET /api/orders/{id}/events`, `GET .../assignments` | Local protected scope; audit records persist |

Gaps: no live rider GPS, push/WebSocket, photo, masked calling, external navigation handoff
receipt, payment/remittance, route polyline or courier webhook. Queue polling is not instant
real-time sync.
