# Safe future live-routing activation

No Google/ORS request, billing activation or account creation was performed.
The default is explicitly acknowledged offline test routing. Activation requires
separate owner approval and valid server credentials; do not paste keys into
browser configuration, Git, screenshots or logs.

Configuration names (all prefixed `LANNPYA_`):

| Variable | Default / purpose |
|---|---|
| ROUTING_PROVIDER | `offline`; alternatives `disabled`, `google`, `ors` |
| ROUTING_EXTERNAL_REQUESTS_ENABLED | `false`; independent outbound-request gate |
| GOOGLE_ROUTES_API_KEY | Empty server secret for Google Routes |
| ORS_API_KEY | Empty server secret for hosted ORS |
| ROUTING_TWO_WHEELER_ENABLED | `false`; Google-only explicit mode |
| ROUTING_REQUEST_TIMEOUT_SECONDS | `10`; shared provider budget, maximum 30 |
| ROUTING_MAX_STOPS | `25`; maximum 50, matrix includes hub |
| ROUTING_REQUESTS_PER_MINUTE | `10` per privileged actor, maximum 60 |
| ROUTING_PLAN_TTL_MINUTES | `15`; maximum 60 before preview expiry |

Safe placeholders are in `backend/.env.example`. Standalone FastAPI Settings can
read its normal environment file; the integrated loopback sandbox deliberately
ignores `.env` files. For that launcher, configure approved values in the parent
process environment/secret manager before startup. It continues forcing mock AI
and its own isolated SQLite database. Changing routing does not activate AI.

After approval:

1. Obtain an appropriately restricted key from the chosen provider using your
   approved account. For Google, enable Routes API and establish billing/quota
   controls in that account; this task did not do so. Restrict server credentials
   by API and deployment environment as applicable.
2. Set the chosen provider, server secret, explicit outbound gate and limits.
   Keep unused provider keys empty. Do not reuse the public browser Maps key as a
   private backend credential.
3. Start only a loopback development workspace. Inspect protected
   `GET /api/routes/provider-status`; it reveals configuration booleans, not keys.
   `live_verified` intentionally remains false; it is not a connectivity probe.
4. With separate authorization for metered calls, request one small route/matrix
   using fictional/test locations and verify regional road quality, errors,
   quotas, response geometry and provider terms. No such live smoke test occurred
   in Phase 22.
5. Enable a Google browser Maps key only if displaying Google geometry, with
   appropriate referrer/API restrictions. The Leaflet offline/ORS path needs no
   Google key. External Google Maps navigation links need no API key.
6. Never expose privileged APIs publicly until real authentication, scoped
   authorization, deployment hardening and paid-call budget controls are reviewed.

Disabling the outbound gate or selecting `disabled` fails explicitly; neither
switch silently produces test routes. Routes use TRAFFIC_UNAWARE. TWO_WHEELER has
documented Myanmar coverage, but actual Yangon road/mode usability remains
unverified. No traffic-aware ETA or guaranteed arrival is implemented.
