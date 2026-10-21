# Local testing dashboard verification

Executed locally on 2026-10-21. Existing prior-phase uncommitted changes were preserved.
This task changed only the isolated tool, its tests/launcher and its documentation; no
backend application source, models, migrations, public API contracts or product frontend
were changed. No new dependency, paid service, push, deployment, tunnel or firewall change.

## Actual results

| Check | Result |
| --- | --- |
| Baseline before implementation | 775 Python tests passed in 58.94 seconds |
| New dashboard Python cases | 33 passed in 13.74 seconds |
| Complete final Python regression | **808 passed**, zero failed, 71.35 seconds |
| JavaScript | **7 passed**, zero failed: four existing adapter tests and three new dashboard DOM-harness tests |
| Lint | Ruff passed |
| Formatting | 95 Python files already formatted |
| Dependency consistency | `pip check`: no broken requirements |
| JavaScript syntax | `node --check` passed for dashboard ES module |
| PowerShell launcher | Parser syntax passed; dependency-repair branches reviewed, not executed because dependencies already exist |
| OpenAPI compatibility | Existing snapshot regression passed, preserving 29 application operations |
| Real HTTP launcher test | Startup, cookie/CSRF session, health, create, reset and graceful shutdown passed |
| Port conflict | Rejected without stopping the socket owner |
| Real HTTP running dashboard | Complete buyer/dispatcher/rider/COD flow passed on 127.0.0.1:8765 |
| Visual browser check | **Blocked**: no CUA browser registered; native computer-use pipe unavailable on initial attempt and retry |

The Node harness executes the actual JavaScript against a small DOM fixture and mocked
network responses. It verifies startup/control wiring, safe text rendering and connection
failure handling. It is not a real browser, screenshot/layout test or production frontend
integration. Actual backend behavior is covered separately by TestClient and real HTTP.

## Functional evidence

The 33 Python cases cover startup/static assets/test indicator, real extraction of both
editable language examples, invalid parsing, order creation/correction/provenance/events,
status validation, buyer public/private boundaries, short-lived authorization, initial pin
proposal and explicit approval, reschedule rejection, invalid coordinates, expired link,
expired authorization, three-guess lockout, browser-handle ownership, rider assignment,
queue propagation, wrong-rider rejection, delivery failure, missing COD rejection and
successful COD completion. They also cover cookie/CSRF/JSON/size checks, Origin/Host/peer
protection, path/SSRF rejection, private-value-safe errors, HTTP log suppression, reset,
normal environment/database hash preservation and shutdown cleanup.

An additional actual HTTP exercise against the left-running dashboard created fictional
orders, verified a buyer, submitted an artificial initial pin, approved it, confirmed
availability, assigned a rider, read the queue, started delivery, rejected completion
without COD, then completed with COD asserted. Eleven delivery events were read back.
A separate fixture demonstrated expired-link 410, three generic verification failures,
LOCKED card and subsequent 423; incorrect CSRF produced 403. The sandbox was reset through
the protected reset action afterward and its order list verified empty.

Runtime behavior learned and respected, rather than changing the backend:

- Conservative COD parsing can reject decimal-like punctuation. Test examples use clear
  markers/currency, with outcomes shown faithfully.
- AVAILABLE can move an eligible order to CONFIRMED. UI transitions refresh canonical state.
- Wrong phone guesses all return generic 403; the third persists lockout, and later attempts
  return 423. The tool reads the actual public card instead of inventing a lock flag.
- A non-assigned rider receives 404 to avoid revealing private assignments.

No existing application defect required a fix. During tool development, mismatched test
assumptions were corrected to the implemented contract. Tool safeguards added include
HTTP-client URL log suppression, server-only capability/authorization storage, session-owned
handle restoration, CSRF/Origin/Host guards, safe text output and temporary-directory-only reset.

## Files created

- `backend/tools/backend_test_dashboard/__init__.py`
- `backend/tools/backend_test_dashboard/__main__.py` — loopback launcher and port handling
- `backend/tools/backend_test_dashboard/runtime.py` — temporary DB, fixtures and role contexts
- `backend/tools/backend_test_dashboard/server.py` — guarded local session/proxy/fixture actions
- `backend/tools/backend_test_dashboard/static/index.html`, `style.css`, `app.js`
- `backend/tests/test_backend_dashboard.py`
- `tools/backend-test-dashboard/start.ps1`, `README.md`, `dashboard.test.cjs`
- `docs/LOCAL_BACKEND_TESTING_GUIDE.md`, this report and `LOCAL_BACKEND_TESTING_RESULTS.json`

## Running state and limitations

The final server was started hidden on **http://127.0.0.1:8765**, with fresh empty test orders
and the seeded fictional merchant/dispatcher/rider. Its process is local only; use **Stop
local tool** for graceful cleanup. Availability depends on the local process continuing
to run. No browser was automatically opened because browser automation was unavailable.

No external AI, map widget/geocoding, trusted reference injection, customer messaging,
production authentication, merchant signup or payment settlement is provided. Buyer local
handles are session-bound and cannot be sent as real buyer links. Existing production
fail-closed behavior remains intact. Do not enter real customer data or expose this tool
through a LAN binding, reverse proxy or tunnel. See the [testing guide](LOCAL_BACKEND_TESTING_GUIDE.md).
