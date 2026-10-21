# Security review for frontend integration

Reviewed local application code/configuration and routes. This is an integration review,
not a penetration test or production security certification.

## Access boundaries

| Route group | Access boundary |
| --- | --- |
| `GET /health`, `POST /api/orders/parse` | Public, stateless. Parse echoes/extracts submitted text; treat response as sensitive because it may contain personal data. |
| Order/user/dispatcher APIs under `/api/orders`, `/api/users` | Development token, local/test config, enabled management, actual loopback peer, and a server-bound user actor. Role/merchant scoping is checked server-side. |
| Rider and assignment APIs | Same development-only loopback token and server-bound actor, with rider/dispatcher/admin role checks and rider ownership scope. |
| `GET /api/confirm/{token}` and `/verify` | Secret-link capability; minimal card and last-four challenge; failed guesses lock the record; rate limiting is persisted. |
| Buyer details/location/response | Link plus separate short-lived Bearer credential bound to confirmation/order. No dispatcher authority. |

Responses for orders/users/riders/confirmation are `no-store`; confirmation routes also
set `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow` and `nosniff`.
The example JS helper uses `credentials: omit`, redirects errors, hides tokens from URLs,
and stores buyer authorization in closure memory. Application errors omit submitted values
and DB exception details. The order access logger filters sensitive query values.

## Browser feasibility and critical blocker

Same-laptop local browser to loopback backend can work with CORS and a runtime-entered
local token. CORS alone does not authorize requests. `require_dev_access` checks the network
peer is loopback and compares token in constant time. A browser running on another computer
cannot use the first developer's `localhost`; a LAN request would also fail the backend's
loopback peer check. Do not bind the server to `0.0.0.0`, create a tunnel, disable the peer
check, or place a shared token in frontend source/build output.

Production management APIs fail closed: `environment` must be local/test and active DB
required; production requests receive unavailable responses regardless of enable flags.
The development token is not a login system, has one server-configured actor, and has no
user/tenant session management. Sharing one token/browser bundle would grant that one
actor's local privileges to every recipient. This is a **critical blocker before any shared
online demo or real customer data**.

Recommended next step is a server-side identity/session boundary with user login, tenant
scoping, role authorization, short session lifetime/rotation/revocation, rate limits and
audit controls. If a BFF is used, keep credentials server-side, bind its own authenticated
sessions to a user/tenant, enforce CSRF protection for cookie sessions, and redact logs.
Never implement an unauthenticated token-forwarding proxy. Deploy only behind HTTPS and a
reviewed trusted proxy configuration; do not trust client-supplied forwarded IP headers.

Buyer links are bearer capabilities, not proof of phone ownership; the 4-digit challenge
is an additional check, not strong authentication. Real messaging, link delivery, abuse
monitoring, retention/deletion and privacy notices require product/security decisions.

## Configuration and data handling

- Keep `backend/.env` and real deployment secrets server-side. `.env.example` is placeholders.
- Browser build values (including Vite `VITE_*`) are public. They may contain an API base
  URL only, never `LANNPYA_DEV_ACCESS_TOKEN`, DB URLs/passwords, signing keys or API keys.
- Use exact `LANNPYA_CORS_ORIGINS` origins. Disable cookie credentials as currently done.
  CORS is not authentication and does not make a private API safe for public deployment.
- Do not log raw order messages, phone, buyer link/token, Bearer, last-four, buyer notes,
  coordinates, development headers or private payloads. Store buyer authorization in
  memory and clear it when the user leaves the flow.
- Do not place confirmation tokens in analytics, referrer-bearing third-party requests,
  service-worker caches or local storage. Keep buyer page assets first-party and minimal.
- The existing generic public parser accepts order text; do not treat it as persistence or
  send sensitive text to an unapproved AI service. Current AI is mock/disabled only.

No production auth feature was added and no external deployment/network exposure occurred.
