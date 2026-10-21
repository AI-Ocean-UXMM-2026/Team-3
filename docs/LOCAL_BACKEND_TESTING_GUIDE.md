# Local backend testing dashboard

This is a disposable engineering tool, not LannPya's product frontend. Use fictional data
only. The teammate's `frontend/` directory is untouched. No cloud, public tunnel, paid AI,
external map assets or messaging service is involved.

## Start and stop

From the repository root in Windows PowerShell:

```powershell
.\tools\backend-test-dashboard\start.ps1
```

Open **http://127.0.0.1:8765**. Use that exact host, rather than `localhost`: Host and Origin
checks intentionally require the configured address. If the port is occupied:

```powershell
.\tools\backend-test-dashboard\start.ps1 -Port 8766
```

The launcher never kills another process. It checks the existing virtual environment and
imports, creating/installing project-pinned development dependencies only if missing.
No execution policy or firewall settings are changed. If script execution is unavailable,
the equivalent command from `backend` uses the already installed environment:

```powershell
.\.venv\Scripts\python.exe -m tools.backend_test_dashboard --port 8765
```

No separate normal backend server is required. Ctrl+C in the foreground launcher, or
**Stop local tool** in the sidebar, gracefully closes backend contexts and removes the
temporary database. Closing the browser tab alone does not stop the server. Restarting
starts an empty test order database with a fictional merchant, dispatcher and available rider.
An abrupt process kill can leave an OS temporary folder; it never deletes project data.

## Architecture and isolation

Implementation lives in `backend/tools/backend_test_dashboard/`: vanilla HTML/CSS/ES-module
JavaScript, a small loopback FastAPI shell, and a server-side proxy. The shell starts the
**existing application factory**, routes, services, providers and SQLAlchemy persistence
against a newly generated temporary SQLite database, with Alembic migrations applied.
Calls are dispatched through TestClient's ASGI transport. This is the actual backend
application, not browser-simulated responses or storage; there is no separate port 8000
backend instance. HTTP between browser and shell is real; the internal API hop is in-process.

Each backend role has its own server-bound actor and private development credential.
The initial fictional merchant/dispatcher are fixture users (there is no merchant-signup
API); riders, orders and lifecycle actions then use real implemented APIs. No backend
architecture, model, migration or public contract was changed. The regular `.env` and
database are not loaded as the sandbox's connection. Mock AI and conservative courier
policies are explicitly fixed for this tool.

The database exists only for this running process. **Reset this sandbox** requires typing
`RESET FICTIONAL DATA`. It closes clients/engine and removes only the temporary directory
owned by this runtime, then migrates a fresh one. It accepts no path or database URL.
All order IDs, buyer handles and credentials from before reset become unusable. Local
browser sessions share this one fictional sandbox; resetting affects every tab. This is
a single trusted developer's tool, not a multiuser administrator service.

## Workflows

### Parser and orders

1. Choose an editable Burmese, Myanglish or incomplete fictional example. The default
   constructed phone ends `0000`; it is test data, not a claimed reserved phone number.
2. **Parse address** calls `POST /api/orders/parse`. The response shows actual extraction,
   reasons, sources, normalization and AI availability. Parsing does not save an order.
3. **Create saved test order** calls `POST /api/orders` with the seeded merchant ID and
   current raw text. It selects the returned persistent DRAFT order.
4. Browse/filter/search saved records, with ten orders per page. Click a row to select it.
   Manual correction accepts a JSON object of actual editable fields. The tool refreshes
   the order and sends its latest `expected_version`; the backend still rejects conflicts.
5. The status selector uses the existing lifecycle map. Choose NEEDS_REVIEW before buyer
   confirmation. Rules may reject an allowed transition when critical information is
   missing, requests are pending or explicit location acknowledgment is absent. RED cases
   must be corrected, not forced through. Completion actions belong on the Rider tab.
6. **Delivery event history** fetches persistent events; original messages and provenance
   are inspectable in the response panel. Test details are visible transiently, so do not
   enter real personal information or share screenshots containing it.

The parser conservatively rejects ambiguous COD strings: for predictable demos use
`COD 25000 MMK,` rather than ambiguous decimal-like punctuation. Such outcomes are shown
as actual validation results; the dashboard does not guess or alter the parser's rules.

### Buyer confirmation and review

Generate a link for an eligible selected order. The backend creates its real hashed-token
record, but the proxy retains the secret URL. The UI gets a browser-session-bound handle
and a local `/#buyer=...` URL. Refreshing this same session restores its handles; another
browser session cannot reuse them. These local URLs are not shareable production buyer
links and cannot be sent to a real customer. Actual link delivery is unsupported.

Use **Public card** before verification to see safe context. Enter the synthetic recipient
phone's last four digits, then **Verify buyer**. The returned authorization stays server-side;
the response panel displays verification/expiry only. **Verified details**, pin and response
requests use that separate short-lived credential automatically. No privilege is inferred
from the frontend's displayed state.

The initial `0,0` input is an artificial test coordinate, not a location claim. Acknowledge
the initial unverified pin before submitting. With no trusted reference/boundary dataset,
expect REVIEW_REQUIRED. Pending requests do not silently overwrite canonical order data.
Use Dispatcher → Load buyer requests → APPROVE/REJECT with a reason. Inspect order details,
history and rider queues after approval. Buyer confirmation does not automatically make GREEN.

AVAILABLE, INSTRUCTIONS, RESCHEDULE and LEAVE_WITH_SECURITY call the actual response API.
The default schedule is tomorrow 04:00–05:00 UTC. Windows require explicit offsets and
valid lengths; notice/cutoff policies remain active. Automatic courier rescheduling and
leave-with-security are disabled in this sandbox, so unsupported changes require review.
An AVAILABLE action may move an eligible order directly to CONFIRMED under existing rules;
refresh the order before choosing its next lifecycle step.

Expiry/lockout controls are explicitly test-only:

- **Expire test link/authorization** changes only the selected temporary fixture's expiry
  timestamp. There is no production expiry-bypass API. The next actual buyer request must
  demonstrate 410/401 respectively.
- **Submit 3 incorrect guesses** sends real valid-format wrong digits, never updates a
  lock flag directly. Default `1111` is deliberately different from the default `0000`.
  If the digits succeed, the tool stops and reports that instead of claiming lockout.
  Wrong guesses return generic 403, including the third; the public card then shows LOCKED,
  and subsequent verification returns 423. Generate a fresh link to continue.
- Existing request limits remain enabled (including ten verification calls/minute on the
  shared local buyer peer); 429 is a real rejection. The proxy exposes Retry-After and
  never silently retries a state-changing action.

### Dispatcher and rider

Resolve pending buyer requests, then confirm and mark READY_FOR_DISPATCH. Explicitly
acknowledge an unverified location if required. Create available fictional riders or use
the initial one, then assign the selected eligible order with an optional stop sequence.
Unassignment and assignment history use their existing APIs.

On Rider, select an identity and retrieve its queue. Calls are made as that actual
server-bound rider, not a dispatcher pretending a request field grants rider permission.
Choose a queue delivery, START, then DELIVERED with explicit COD collection where required,
or FAILED with a supported reason. COD is only a test collection assertion, not payment.
Wrong rider, completed delivery, unavailable rider and invalid status checks remain active.

Queue polling runs every five seconds while enabled and the page is visible, without
overlapping actions. It uses the backend cursor and retains results on `unchanged:true`.
It is REST polling, not push synchronization or geographic routing. Navigation URLs are
available in actual JSON only when the backend reports navigation ready; the tool does
not automatically send notes or coordinates to an external map service.

## Responses, timeline and errors

The response panel displays actual JSON via text rendering, never `innerHTML`. Private
development tokens, buyer tokens, authorization and private confirmation URLs are removed
server-side. Errors do not become simulated successes. Examples: 401 verification/session
required, 403 wrong digits/scope, 404 missing record, 409 state/version/review conflict,
410 link expired, 422 validation, 423 locked, 429 rate limit. Unexpected local errors are
generic and do not echo exceptions or SQL parameters.

The memory-only timeline retains at most 100 method/endpoint/status/duration/outcome rows.
It contains no request bodies, queries, submitted digits, private result text or credentials.
Buyer capability paths are shown as `/api/confirm/{token}`. Duration measures the internal
API hop, not network round-trip or human work. Reset/reload clears the browser timeline.
There is no localStorage, sessionStorage, analytics, third-party asset or persistent browser log.
The sanitized response panel can be cleared separately. HTTP client request logging is
suppressed inside this tool so private buyer URLs are not emitted at INFO/DEBUG levels.

## Security boundary and limits

- Socket binds only `127.0.0.1`. Actual peer, exact Host/Origin and Fetch Metadata are checked;
  forwarded IP headers are not trusted. No LAN access, CORS grant or firewall change.
- Private routes need an HttpOnly SameSite=Strict local session cookie. Mutations additionally
  need the matching CSRF header and JSON. Sessions expire after eight hours and are bounded.
- The proxy accepts allowlisted methods/paths only, with no upstream URL, arbitrary headers,
  filesystem path or database connection. Requests are bounded to 64 KiB.
- Content Security Policy, no-store, no-referrer and frame denial apply. Use only this exact
  local origin. A malicious local OS user is outside this single-user development boundary.
- The API console is limited to supported test routes. Trusted-reference attestation,
  merchant signup, production authentication, real AI, external messaging, map widgets,
  photos and payment processing are intentionally unsupported.
- Graceful reset/shutdown removes data; restart persistence is intentionally not supported.
  Persistence during the process is real SQLite persistence, verified by API and database tests.

## Verification

```powershell
# From backend
.\.venv\Scripts\python.exe -m pytest -q tests/test_backend_dashboard.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
# From repository root
node --test tools/backend-test-dashboard/dashboard.test.cjs
```

See [actual verification results](LOCAL_BACKEND_TESTING_VERIFICATION.md). Automated API,
real HTTP launcher and Node DOM-harness checks are distinct from a visual browser test.
