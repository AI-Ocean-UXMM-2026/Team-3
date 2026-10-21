# Security boundary

Safe local integration only. One 127.0.0.1 origin, actual loopback peer and exact Host/Origin
checks; forwarded headers untrusted. SameSite=Strict HttpOnly local cookie, bounded session
lifetime and CSRF on JSON mutations. Static assets are allowlisted; backend/source/data/
node_modules/private files are not served. Content Security Policy, no-store, no-referrer
and frame denial apply. Privileged credentials exist only in server-bound role clients.

The UI selects local developer identities, not authenticated production accounts. All
underlying dispatcher/rider scopes and versions remain enforced; private backend requests
without credentials still fail. Core production configuration fails closed and the unified
launcher/factory refuses production mode. Never put this developer proxy on a LAN/tunnel.

Buyer URL tokens are public bearer capabilities shared with their intended recipient;
short-lived verification Bearers stay server-side and are isolated by browser cookie.
Three-failure lockout, DB-backed throttling, expiry, revocation and pin review remain.
Tokens are hashed in DB; native capability text was checked absent from persisted SQLite.
HTTP client logging is suppressed; private URLs/errors are not written to access logs.

Demo cache handling was fixed to exclude live HTML, /api/ and /dashboard/ and only offer
prototype fallback for prototype navigation. No failed live write becomes a fake success.
Production auth/RBAC, trusted deployment, tenancy, abuse monitoring and data retention need
separate design/review. Last-four plus secret link remains a light check, not proof of identity.
