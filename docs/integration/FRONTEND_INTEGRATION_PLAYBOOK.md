# Frontend integration playbook (vanilla JavaScript / Vite)

This guide is for the Vite 6.4.4, vanilla ES module, CSS and Leaflet 1.9.4 architecture
described in `LANNPYA_AI_IMPLEMENTATION_GUIDE.md`. That guide was found and read locally.
The actual frontend files described by it are not in this repository, so its claims about
the running Vite app, button tests, fallback and HTTP calls remain unverified.

## Start services on one development computer

Backend base URL has no `/api` suffix:

```text
http://127.0.0.1:8000
```

In PowerShell, from the repository's backend directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

Use the frontend teammate's existing Vite package scripts from the directory containing
its `package.json`; the implementation guide states `npm run dev` and port 3000, but the
package file is not present to confirm this. Vite's usual default is 5173, and the backend
allows localhost 3000, 5173 and 5500 origins by default. If the frontend uses a different
origin, set `LANNPYA_CORS_ORIGINS` in ignored backend `.env` to an exact JSON array and
restart the backend. Example:

```dotenv
LANNPYA_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

Origin includes protocol, hostname and port. `localhost` and `127.0.0.1` are distinct.
Do not use `file://`, wildcard origins, cookie credentials, a public bind address or a
tunnel. `GET /health` does not prove a database write can succeed.

## Modes and credentials

Use the explicit states in [LIVE_VS_DEMO_MODE.md](LIVE_VS_DEMO_MODE.md):
`LIVE_BACKEND`, `DEMO_SIMULATION`, and `CONNECTION_ERROR`. A failed live operation remains
a connection/API error. Offer demo mode separately and label every simulated value.

Only `VITE_LANNPYA_API_BASE_URL` is safe for Vite build-time configuration. `VITE_*`
variables are included in public browser output. Never set a development token, DB
credential, AI key or buyer Bearer there. The backend local role token is a temporary
developer credential bound to one server actor; a local-only browser may receive a manually
entered credential at runtime and keep it in memory. Do not commit it, bundle it, put it
in localStorage, URLs or logs. Public parse/health do not need it. Saved order/rider APIs do.

The isolated demo is the easiest local full workflow:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\demo_mvp.py --serve --frontend-origin http://localhost:3000
```

It prints a private ignored run directory path. Role URLs and fresh credentials are in
that directory's `private_access.json`, which must not be copied under a static frontend
root or committed. The demo uses synthetic data and separate local instances. Stop with
Ctrl+C. See [DEMO_GUIDE.md](../DEMO_GUIDE.md).

## Dispatcher workflow examples

Public parse is stateless; it does not save an order:

```js
const API = import.meta.env.VITE_LANNPYA_API_BASE_URL ?? "http://127.0.0.1:8000";
const parseResponse = await fetch(`${API}/api/orders/parse`, {
  method: "POST", credentials: "omit", cache: "no-store",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ raw_text: form.rawMessage }),
});
const parsed = await parseResponse.json();
```

For same-machine local dev, runtime credential only:

```js
const localHeaders = {
  "Content-Type": "application/json",
  "X-Dev-Access-Token": tokenEnteredAtRuntime,
};
const created = await fetch(`${API}/api/orders`, {
  method: "POST", credentials: "omit", cache: "no-store",
  headers: localHeaders,
  body: JSON.stringify({ merchant_id: selectedMerchantId, raw_text: form.rawMessage }),
});
```

Create body must contain exactly one of `raw_text` or `structured`, plus `merchant_id` UUID.
HTTP 201 returns `OrderResponse` with `id`, `status:"DRAFT"`, `version`, `customer_phone`,
`cod_amount` digit string/null, confidence, provenance, validation reasons and timestamps.
Use `parsed.address` to review but do not send the entire parse result as create data.

Correction: `PATCH /api/orders/{id}` body has latest `expected_version` and at least one
editable field, e.g. `{expected_version:1,delivery_instructions:"Call on arrival"}`.
Transition: `PATCH /api/orders/{id}/status` body `{expected_version:2,status:"NEEDS_REVIEW"}`.
Use `version` returned by each mutation. Statuses and transitions are in API_CONTRACT.
AMBER readiness requires explicit `acknowledge_unverified_location:true`; no client flag
can create geospatial trust.

Generate link with `POST /api/orders/{id}/confirmation-link`; success 201 contains
`confirmation_url` (a frontend `/confirm/<token>` path), optional `absolute_url`, and
`expires_at`. Backend does not send Messenger/Viber messages. Never log the link.

## Buyer flow

1. Call `GET /api/confirm/{token}`; show the minimal card and `state` only.
2. `POST /api/confirm/{token}/verify`, JSON `{last_four:"4567"}`. It returns an opaque
   short-lived `access_token`, `token_type:"Bearer"`, expiry. It is not JWT.
3. Hold Bearer in memory. `GET /api/confirm/{token}/details` with Authorization header.
4. `PATCH /api/confirm/{token}/location` with Bearer and body, for example:
   `{request_id:crypto.randomUUID(),latitude:16.8,longitude:96.1,initial_pin_acknowledged:true}`.
   Coordinates are only an example shape, not a real customer location. Do not hardcode
   this point. An initial point is pending review.
5. `PATCH /api/confirm/{token}/response` with `{request_id,action:"AVAILABLE"}`, or
   `action:"INSTRUCTIONS",instructions:"..."`, or `action:"RESCHEDULE",time_window:{start,end}}`.
   Time values need explicit offsets and valid policy windows.
6. Show `decision:"REVIEW_REQUIRED"` as pending; only a later dispatcher decision affects
   canonical dispatch data. Clear Bearer when leaving the card. Three failed checks lock link.

No phone number, name, GPS or private note is present on the pre-verification card. Buyer
authorization cannot access dispatcher APIs. Don't use analytics/third-party resources on
the token page; configure SPA routing to load `/confirm/<token>` without leaking referrers.

## Rider queue and polling

`GET /api/riders/{rider_id}/queue` uses the matching rider local instance. Query can include
`cursor=<previous response cursor>`. Poll every five seconds without overlapping requests.
If `unchanged:true`, keep current list even though returned `items` is empty. If false,
replace the list completely, including an empty result after completed stops. Abort when
leaving the screen and refresh after actions.

Queue order is deterministic status/window/dispatcher stop sequence/stable ties, not shortest
route. Use navigation only when `navigation_ready` and URL is non-null. Keep
`coordinate_status`, buyer confirmation and independent verification separate. Deliver:
`PATCH /api/riders/{rider_id}/deliveries/{order_id}/status` with
`{request_id,expected_version,action:"DELIVERED",cod_collected:true}` when a positive COD
was collected. No money processing occurs. Failure uses `action:"FAILED"` and an actual
enum `failure_reason`. Reuse request UUID and identical body for a network retry.

## Request errors and handling

Errors follow `{error:{code,message,details}}`. Validation is 422; development token absent
is 401; role/local denial is 403; stale version/lifecycle conflict 409; link expiry 410;
link lock 423; throttling 429 with `Retry-After`; disabled or DB failure 503; sanitized
unexpected failure 500. CORS/network/preflight problems may have no JSON. Render validation
field locations and preserve user input; reload on 409 and ask before repeating. Don't
blindly retry order creation after timeout (no create idempotency key); reconcile first.

Fetch should use `credentials:"omit"`, `cache:"no-store"`, and not log request bodies,
headers, raw messages, links, or buyer coordinates. Don't render private user strings with
`innerHTML`; use textContent or safe framework text binding.

## Frontend capabilities vs presentation

The actual code guide names Dispatcher Hub, Customer Pinning Studio and Rider HUD. The API
supports parsing, order management, buyer pin proposals/review, rider assignments/queues,
navigation link construction and delivery/COD assertions. API does not provide actual
confidence percentages, geocoding, arbitrary 500m ring, route polylines, rider GPS, photos,
masked calls, messaging, payments or remittance. Visuals for these should be clearly marked
simulated. Confidence is categorical and does not rise automatically when a pin is selected.

## Separate computers

`127.0.0.1` on your teammate's laptop points to their own laptop. It cannot reach the
backend on another developer's laptop. Each developer can clone/run their own backend and
frontend against synthetic local data; Git shares source, not DB files or tokens. Current
private APIs also require the actual network peer to be loopback, so LAN requests are
rejected even if CORS were expanded. Do not open firewall ports or create a tunnel.

A shared browser/online demo requires proper production login and role/tenant enforcement,
HTTPS deployment and a reviewed server-side access boundary/BFF. Current token must not be
sent in a public build. No remote service exists in this phase.

## Suggested order and handoff

1. Import the frontend project under `frontend/` on its own branch. Confirm package scripts,
   actual Vite origin and SPA route handling.
2. Integrate liveness, parser response, validation and explicit live/demo/error state.
3. Add dispatcher create/list/edit/review/status/link using the actual local workflow.
4. Add buyer card, verification, details, proposals and pending-review UI.
5. Add rider queue polling, navigation readiness and explicit completion/failure/COD controls.
6. Exercise full browser journey with the isolated demo. Plan auth before shared demo.

Copyable teammate message is in [FRONTEND_TEAM_SETUP.md](../FRONTEND_TEAM_SETUP.md).
