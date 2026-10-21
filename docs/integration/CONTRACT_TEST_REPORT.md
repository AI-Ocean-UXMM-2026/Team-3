# Contract and reliability test report

Contract tests use the actual application OpenAPI/schema output and isolated temporary
SQLite databases. Test records use generated UUIDs and fictional values. No production
database or paid provider is involved.

## Added contract coverage

`backend/tests/test_api_contract.py` verifies:

- Checked-in integration OpenAPI snapshot equals a fresh application OpenAPI document and
  contains 29 operations.
- `/health` response keys match `HealthResponse`.
- Valid parse request returns the schema fields and extracts the supplied township/COD;
  missing required body returns the structured 422 error.
- Protected order read/create and rider queue reject unauthenticated calls with 401.
- With management deliberately disabled, an invalid buyer capability returns a safe
  unavailable/not-found style response without order data.
- Temporary migration-created SQLite only; generated actor ID and no real fixture data.

These focused tests complement rather than duplicate the existing buyer/rider/order suites.
Existing regression tests cover phone lockout, expired/revoked links, buyer access boundaries,
location movement/reference rules, review behavior, role scoping, lifecycle transitions,
COD confirmation, assignment/queue ordering and polling, mutation idempotency, migration
consistency, error privacy, and persisted history.

## Current run results

| Pass | Command/workflow | Result |
| --- | --- | --- |
| Existing regression + new contract cases | `python -m pytest -q` | **426 passed in 58.46s** (423 existing + 3 new) |
| Contract cases alone | `python -m pytest -q tests/test_api_contract.py` | **3 passed in 2.10s** |
| Node client helper | `node --test ../docs/examples/lannpya-client.test.mjs` from backend | **4 passed**, no failures/skips |
| Dependencies | `python -m pip check` | No broken requirements |
| Lint/format | `ruff check .`, `ruff format --check .` | All checks passed; **72 files already formatted** |
| Actual HTTP demo | Isolated local HTTP demo through 3 backend processes | **68 cases passed**; persistence reopened and verified |
| HTTP demo persistence | Isolated SQLite reopen after servers stopped | 5 orders, 3 buyer requests, 3 assignments, 4 action receipts, 32 events, 3 links |
| OpenAPI | Fresh app object compared to `docs/integration/OPENAPI.json` | **29 operations**, exact equality covered by test |

The full demo does real HTTP requests and reopens isolated SQLite. It is not browser
automation.

## Scope of claims

The checked-in OpenAPI file is compared to the live FastAPI application object. It does not
prove client-side Vite behavior. HTTPX/TestClient checks API contract and authorization
dependencies; the demo validates local process/CORS/storage behavior. No browser, real
frontend package, remote-machine connectivity, PostgreSQL server, production auth, real AI,
messaging provider or licensed geospatial catalog was tested.
