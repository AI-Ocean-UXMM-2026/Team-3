# API keys and service inventory

No credentials were created or printed. This worktree has example environment files,
no live `.env`, and no `LANNPYA_*`, `GEMINI_*` or `DATABASE_*` process configuration
was present during verification. No external AI or cloud database call was made.

| Service | Used in verified local workflow? | Configuration / credential boundary | Status and failure behavior |
| --- | --- | --- | --- |
| Python rules parser | Yes | No key | Real deterministic extraction; uncertainty remains explicit |
| AI mock | Yes | `LANNPYA_AI_PROVIDER=mock`; backend only | No external calls; AI is labeled mock |
| Prepared Python AI adapters | No | `LANNPYA_AI_PROVIDER`, `LANNPYA_AI_MODEL`, `LANNPYA_AI_API_KEY`, `LANNPYA_AI_ENDPOINT` (JSON HTTP only), `LANNPYA_AI_EXTERNAL_REQUESTS_ENABLED` | Explicit external opt-in remains false; sanitized input and deterministic fallback retained |
| TS Gemini research adapter | No | `GEMINI_API_KEY`; server research tooling only | Not the live Python provider boundary; no key configured |
| Leaflet 1.9.4 | Yes | Vendored browser library; no key | Interactive coordinate selection works without remote tiles |
| OpenStreetMap raster tiles | Opt-in; intercepted with synthetic tiles in existing browser tests | `https://tile.openstreetmap.org/{z}/{x}/{y}.png`; no key | User chooses Load street tiles; visible attribution; errors retain coordinates/manual controls |
| Optional Google Maps / Places | Not activated or live-verified | `LANNPYA_GOOGLE_MAPS_BROWSER_KEY`; intentionally public, restricted browser key | Existing optional path preserved. Missing key selects Leaflet; script error/8-second timeout falls back |
| Google Maps directions link | URL generated and checked, navigation not executed against external service | No key; opens directions website | Coordinates only; unavailable until backend marks navigation ready; no phone/private note in URL |
| Geocoder / reverse geocoder | No | None implemented | No invented estimates or township boundaries |
| Route optimization service | No | None implemented | Backend queue ordering and dispatcher-defined sequences only |
| SQLite | Yes | Local file owned by workspace launcher; no credential | Separate from ordinary `LANNPYA_DATABASE_URL` database |
| PostgreSQL / Supabase | No live connection | `LANNPYA_DATABASE_URL`, optional `postgres` Python extra; server only | Prepared dialect/DDL, no account or database provisioned |
| Development access | Yes, inside local BFF only | Generated server-side credentials; direct API variables are `LANNPYA_DEV_ACCESS_TOKEN`, `LANNPYA_DEV_ACTOR_ID` | Never delivered as browser headers/config; production fails closed |
| Buyer authorization | Yes | Link capability in buyer URL; separate short-lived bearer retained by BFF | Hashes in SQL; native bearer not exposed to browser; reverify after a new local session |
| Messaging/payment/telecom | No | None | No automatic SMS/Viber sends, payments, masked calling or remittance |
| Google Fonts | Existing optional UI resource | Public CSS/fonts, no key | System-font fallback; optional font network was stubbed in new browser tests |

## Map decision and policy

Preserve Leaflet; do not add a paid Maps SDK to display a map. A tile-free initial
view is intentional: its Yangon browsing centre is never selected or submitted
as a customer location. Street tiles require an explicit user action.

[OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/) requires
visible attribution and responsible use; it prohibits bulk/offline tile downloading.
The app does no tile prefetch or service-worker tile caching. Tiles retain provider
HTTP caching, use the standard HTTPS URL and an origin referrer. There is no assumed
unlimited quota or availability guarantee. Production traffic needs a reviewed provider.

An optional Google key must come from a separately approved Google Cloud project,
with API and website/referrer restrictions and billing/quotas reviewed first.
See [Google's security guidance](https://developers.google.com/maps/api-security-best-practices).
No Google key or billing setup is needed for the verified Leaflet workflow.
No price or free quota is promised here; any activation needs current provider terms.

Device GPS uses the browser, not a paid positioning API. It runs only on a button
click and requires user permission in a supported secure context (loopback is suitable
for local development). See [MDN geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition).
Denial, unavailable position and timeout retain manual pin entry; no background tracking.

## Safe configuration

[backend/.env.example](../../backend/.env.example) contains placeholders and defaults.
Put private credentials only in ignored server configuration or a future secret store.
No frontend environment token is needed: live mode uses same-origin `/dashboard/*`.
Static `runtime-config.js` explicitly selects simulation; the loopback server supplies
LIVE_BACKEND. Missing runtime configuration produces CONNECTION_ERROR, never demo fallback.

The local integrated launcher forces mock AI and owns SQLite even if a separate API's
database settings exist. It is not a PostgreSQL or production-authentication launcher.
