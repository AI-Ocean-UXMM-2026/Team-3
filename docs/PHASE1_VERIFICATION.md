# Phase 1 verification — 2026-10-20

Environment: Windows PowerShell, Python 3.14.7, project-local `backend/.venv`.
Resolved dependency versions are recorded in `backend/requirements-dev.lock`.

## Final results

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 30 passed in 0.75s; no warnings |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 18 files already formatted |
| `python -m pip check` | No broken requirements found |
| `python scripts/smoke_http.py` | Passed against a real Uvicorn loopback server |
| Live `GET /health` | HTTP 200, exact expected service/status body |
| Live `POST /api/orders/parse` with supplied Burmese sample | HTTP 200, Pydantic-validated mock response |
| Live parsing with whitespace-only text | HTTP 422, validation error |

The smoke script launched its own server on an available local port and stopped it
after verification. No persistent server is left running by this verification.

Initial lint found two long lines; formatting resolved them. Initial tests passed
with a Starlette HTTP client deprecation warning. Replaced the development HTTP
client with Starlette's supported `httpx2` client, then reran tests, lint, formatting,
dependency checks, and HTTP smoke verification successfully.

No unresolved test failures or local setup blockers. Missing PRD/IA/use-case documents
and scope assumptions are recorded in `PHASE1_DECISIONS.md`. No real extraction,
dispatch confidence, persistence, or production readiness is claimed.
