# Integrated frontend contract

Backend application OpenAPI now has 35 operations: all 29 existing operations plus six
additive session/route/workflow operations. Generated snapshots: docs/OPENAPI.json and
docs/integration/OPENAPI.json. See API_CONTRACT.md and FRONTEND_HANDOFF.md for core schemas.

Browser integration uses GET /dashboard/bootstrap and POST /dashboard/api with same-origin
HttpOnly session cookie, CSRF header and allowlisted {method,path,body,actor,rider_id,buyer_handle}.
No development token or buyer Bearer is returned. Local API errors retain actual HTTP
status, backend code and field locations. This is a development boundary, not production auth.

New native operations: GET /api/session; GET and POST /api/routes;
POST /api/routes/{route_id}/actions; POST /api/orders/{order_id}/operations;
POST /api/orders/{order_id}/prepare-assignment. They require existing role authorization.

Legacy create requests retain merchant_id and exactly one raw_text/structured input.
Additive parcel requests may omit merchant_id for an Admin/Dispatcher-bound owner:

```json
{"raw_text":"09790000000, Hlaing, COD 25000","parcel":{"item":"Fictional parcel","delivery_day":"2026-10-21","hub_received":false}}
```

Use today's Yangon date when executing, not a hardcoded date from this report. The UI's
Save original chat order preserves original_message and parser provenance. Manual entry
and correction remain separate. Canonical Kamayut/San Chaung values are mapped from older
Kamaryut/Sanchaung aliases. Reviewed buyer requests use history row IDs and current versions.

Buyer links contain native public capability tokens by design; never publish or log them.
The proxy keeps short-lived buyer Bearer authorization per browser session on the server.
Another browser or a backend restart requires verification again; native links remain
valid through their database hash/expiry. The old temporary dashboard keeps its stricter
session-owned test handles. Missing coordinates remain null; no confidence percentages.
