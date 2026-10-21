# Dashboard end-to-end test report

Verified locally on 2026-10-21. Historical counts were not used as current results.
No deployment, Git push, paid service, production connection or teammate frontend change.

## Final results

| Check | Actual result |
| --- | --- |
| Complete Python regression | **812 passed**, zero failed/errors/skipped, 76.60 seconds |
| Dashboard Python subset | 37 cases included above; four added in this assignment |
| JavaScript combined suite | **17 passed**, zero failed: four existing client-adapter cases, four dashboard unit/harness cases and nine HTTP-suite cases |
| Strengthened HTTP subset | Nine cases passed again after adding canonical instruction/window/pin assertions |
| Ruff lint | Passed |
| Ruff formatting | 95 Python files already formatted |
| Dependency check | No broken requirements found |
| Dashboard ES module syntax | Passed |
| Public backend contract | Existing snapshot tests passed: 29 application operations preserved |
| Running dashboard | 127.0.0.1:8765 responded; proxied health 200; TEST MODE and mock AI confirmed |
| Real browser/screenshots | Not performed: current browser inventory returned no registered browsers |

Node's nine HTTP cases consist of one parent test and eight workflow subtests. These counts
are framework-reported cases, not counts of HTTP requests or independent production trials.
Do not add the repeated affected subset to the unique test total. One intentional bug
reproducer failed before the fix; it passes now. Initial harness assumptions about display
labels, explicit refresh and closed-assignment 404 were corrected to actual behavior.
There are no unresolved test failures.

## Environment and isolation

The existing dashboard was already listening only on 127.0.0.1:8765. Its page, bootstrap,
health, order list and served JavaScript were checked through actual HTTP. The saved order
count was zero. No existing records were reset or changed during this check. The updated
JavaScript is served directly from disk, so no destructive server restart was necessary.

Mutating end-to-end experiments used separately launched dashboard processes on ephemeral
loopback ports. Each process creates its own generated temporary SQLite database, applies
the existing migrations, and removes its owned temporary directory on graceful shutdown.
The regular project connection is never supplied. Existing reset/isolation tests verify
normal database/configuration hashes remain unchanged, reject arbitrary reset inputs and
remove only the sandbox's directory. The HTTP tests use the existing launcher module;
the still-open dashboard at 8765 was left available.

The browser-to-dashboard HTTP connection is real. The dashboard's server-side backend hop
uses the actual existing FastAPI application through TestClient's ASGI transport. It uses
real routes, validation, services, authorization and SQLite transactions, not mock order
storage. Only AI enrichment is mock or explicitly failure-injected. The fictional merchant
is fixture-seeded; the dispatcher creates its merchant-owned order. No unsupported merchant
registration or production identity workflow is implied.

## Parser checks

The real JavaScript parsing control submitted six fictional valid-shape requests and
three invalid requests to actual HTTP endpoints:

| Input category | Expected and observed behavior |
| --- | --- |
| Burmese Unicode/numerals | Phone extracted, COD 25,000, Hlaing matched, AMBER |
| Myanglish with prepaid wording | Phone/township matched, COD null, AMBER; null was not silently replaced with zero |
| Mixed Burmese/English | COD 5,000 and labeled instructions extracted; AMBER |
| Missing phone | RED; explicitly missing contact |
| Unknown township | RED; valid phone did not override unknown address |
| Multiple distinct phones | RED with ambiguity; no arbitrary phone chosen |
| Empty, 10,001-character and NUL-containing input | 422 without false parsing success |

Original messages and field-source objects were asserted. Known COD values and explicit
English instructions were compared to the supplied text. The complete Python suite also
reran the existing labeled corpus, malformed Unicode and provider-independence checks.
These are deterministic extraction/regression checks; no real AI accuracy was measured.

## Complete control-driven delivery workflow

`dashboard-http.test.cjs` executes the actual `app.js` event handlers through a small DOM
harness while forwarding their network calls to a real disposable dashboard server.
The flow verified:

1. Burmese parsing, merchant-owned order creation, saved list selection and manual correction.
2. DRAFT → NEEDS_REVIEW using actual allowed transitions and current versions.
3. Confirmation-link generation, privacy-safe public card and rejection of private details
   before verification. Actual backend link/authorization remain on the server.
4. A wrong-code rejection followed by successful synthetic last-four verification.
5. Invalid latitude rejection, then initial artificial 0,0 pin proposal with explicit
   acknowledgment and REVIEW_REQUIRED. No home coordinates were invented.
6. Dispatcher request history and explicit approval; canonical order coordinates checked.
7. Rescheduling request, dispatcher approval, availability and changed instructions.
8. Explicit acknowledgment of unverified location before READY_FOR_DISPATCH.
9. Assignment, actual rider identity, queue retrieval and delivery start.
10. Missing COD confirmation rejected; explicit collection assertion permitted completion.
11. Another completion attempt rejected with 404 after the active assignment closed;
    event history contained exactly one DELIVERY_COMPLETED event.
12. Canonical DELIVERED order read back after separate API requests.

The rider queue was checked for the approved pin's BUYER_CONFIRMED provenance, canonical
instructions, confirmed time-window start and AMBER classification. Approval did not
fabricate GREEN or independent geospatial verification. After buyer actions, the test uses
the UI's Load order control before choosing a new transition, as documented.

A second workflow created another rider, rejected a nonexistent rider assignment with
404, rejected delivery start by the wrong rider with 404, and allowed the assigned rider
to start and record a failed delivery with an explicit supported reason.

## Failure, persistence and security checks

| Scenario | Evidence |
| --- | --- |
| Wrong phone digits | Generic 403; no stored digits returned |
| Three incorrect attempts | Three real failed requests, public card LOCKED, later attempt 423 |
| Expired link | Explicit temporary-fixture expiry followed by actual buyer API 410 |
| Expired buyer authorization | Temporary-fixture expiry followed by details 401 |
| Unauthorized order correction | Direct backend call without server credential returned 401; version, fields and event count unchanged |
| Invalid coordinates | 422; no successful pin mutation |
| Invalid lifecycle transition | Existing regression test rejects and preserves stored state |
| Duplicate completion | Rejected; one completion event, no second completion mutation |
| Missing COD | 409; subsequent explicit COD completion succeeds |
| Invalid rider / wrong rider | 404, preserving assignment privacy |
| AI unavailable | Injected local adapter failed; deterministic phone/COD remained, AMBER/manual review explicit, order saved with unavailable status |
| Mid-transaction DB failure | Event INSERT fault after order work returned safe 503; zero orders and zero events survived; same sandbox accepted a subsequent valid order |
| Independent DB connection | A newly opened engine read committed original text, order status/version and two order/history events |
| Reset | Wrong confirmation rejected; correct reset replaced test actors/database and cleared orders/handles |
| Timeline | Bounded to 100 rows; no phone digits, submitted notes, authorization or private URLs |

The database fault was injected at SQLAlchemy's event-INSERT boundary and removed in a
finally block. It was not a pretend error response. The unavailable-AI adapter was local
and made no external calls. Neither fault injection was installed on the running dashboard.

The full regression reran cookie/CSRF requirements, exact Origin/Host checks, loopback peer
checks, forwarded-header resistance, allowlisted paths/SSRF rejection, session-bound buyer
handles, rate limiting, sensitive error suppression, token hashing/expiry, concurrency,
transaction rollback and production fail-closed cases. No private credential is embedded
in the static application. Existing server-side HTTP logging suppression remains active.

## Confirmed bug and fix

**Quiet API errors were hidden from the response panel.** `api()` skipped rendering when
`options.quiet` was set, but still marked a rejected response as already displayed.
`guard()` therefore suppressed the error. Startup reads and polling/refresh failures could
leave old success output visible even though an operation had failed.

The regression test first reproduced the issue: a quiet startup rider read returning 503
left the status panel empty. The minimal fix changes the rendering condition to
`!options.quiet || !response.ok`. Successful background reads stay quiet; rejected reads
always show the actual backend error. No endpoint, schema, authorization rule or business
service was changed. The reproducer and complete regression now pass.

## Dashboard coverage and limits

Verified actual handlers for parser, order create/list/select/correction, versioned status,
buyer link/card/verification/details, pins, rescheduling, availability/instructions,
review approval, rider create/assign/queue/start/complete/fail, COD, event history,
authorization/link expiry, lockout, API console, timeline and reset. Existing Python tests
cover request rejection/revocation and other backend policy variants.

There was **no real browser session and no screenshot collection**. The current browser
automation inventory was empty, so this task used the explicitly permitted fallback.
The DOM harness is intentionally limited: CSS/layout, browser-specific rendering,
accessibility behavior and native cookie/Fetch Metadata behavior are not visually certified.
HTTP headers/session checks are tested through real clients and regression tests.

Production authentication is still absent. Real AI, PostgreSQL production behavior,
trusted geospatial data, messaging, maps/photos and payment settlement remain unavailable
or unverified. COD is a collection assertion. The temporary dashboard is for one trusted
local developer and synthetic data; it must not be publicly exposed. Product frontend
integration has not been tested because that application was not supplied.

## Files and repeat commands

Updated: `backend/tools/backend_test_dashboard/static/app.js` (one rendering-condition fix),
`backend/tests/test_backend_dashboard.py` (four additional cases), dashboard test file and
launcher README. Added `tools/backend-test-dashboard/harness.cjs`,
`tools/backend-test-dashboard/dashboard-http.test.cjs`, this report and the machine-readable
[results](CODEX_END_TO_END_TEST_RESULTS.json). Existing unrelated uncommitted work was preserved.

```powershell
# From backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
# From repository root
node --test docs/examples/lannpya-client.test.mjs tools/backend-test-dashboard/dashboard.test.cjs tools/backend-test-dashboard/dashboard-http.test.cjs
```

The backend and local dashboard work within the tested local scope, including complete
delivery processing. The important discovered display bug is fixed. Controlled frontend
integration can begin against the existing contract; public privileged access still needs
proper authentication and deployment/database validation.
