# LannPya AI - integrated local application

The hardened backend, selected ZLH admin/customer/rider UI and native route/cash workflows
share one authoritative database. Private credentials stay server-side. Real rules parsing;
AI enrichment remains MOCK. No final AI provider is selected.

```powershell
npm.cmd start
```

Open http://127.0.0.1:8780. [Startup](docs/final-integration/LOCAL_STARTUP_GUIDE.md),
[architecture](docs/final-integration/FINAL_ARCHITECTURE.md),
[branch review](docs/branch-integration/BRANCH_COMPARISON.md),
[demo](docs/final-integration/DEMO_WORKFLOW.md),
[tests](docs/final-integration/TEST_RESULTS.md),
[blockers](docs/final-integration/REMAINING_BLOCKERS.md).

- frontend/: styled vanilla-JS application; prototype.html is DEMO_SIMULATION.
- backend/: FastAPI, migrations, buyer/rider services and preserved QA tools.
- order-parser/: optional TypeScript AI/parser research; not the live API.
- scripts/: local startup, Python environment selection and static frontend build.
- docs/: contracts, source provenance and final verification.

Local use only. No public deployment or remote push.

## Previous backend notes (historical)

# LannPya AI (လမ်းပြ)

AI-assisted last-mile delivery middleware for Myanmar merchants and couriers,
built for UXMM Hackathon Myanmar.

## Repository structure

```text
lannpya-ai/
├── backend/     # FastAPI application, migrations, scripts, and tests
├── frontend/    # Reserved for the frontend team's application
├── docs/        # API contract, integration guides, and verification reports
└── README.md
```

## Backend

The Python backend includes deterministic Burmese address parsing, a replaceable
mock AI interface, persistent order management, secure buyer confirmation,
dispatcher review, and rider delivery queues. It uses FastAPI, Pydantic,
SQLAlchemy, and Alembic. SQLite supports local development; PostgreSQL is the
production database target.

See [backend setup and commands](backend/README.md) to install dependencies,
initialize a local database, start the API, and run tests.

## Frontend integration

- [Frontend team setup and Git workflow](docs/FRONTEND_TEAM_SETUP.md)
- [Phase 8 integration preparation](docs/PHASE8_FRONTEND_INTEGRATION.md)
- [Frontend handoff](docs/FRONTEND_HANDOFF.md)
- [REST API contract](docs/API_CONTRACT.md)
- [OpenAPI schema](docs/OPENAPI.json)
- [Repeatable local demo](docs/DEMO_GUIDE.md)
- [Phase 7 verification](docs/PHASE7_VERIFICATION.md)
- [Phase 8B integration audit and API inventory](docs/integration/README.md)
- [Overnight reliability verification](docs/OVERNIGHT_VERIFICATION_SUMMARY.md)

The frontend directory is a placeholder. No frontend framework is required by
the backend API.

## Development boundaries

AI enrichment remains mocked. Production authentication, live PostgreSQL
verification, and trusted geospatial verification are pending. Private APIs
fail closed in production; local development access is not production
authentication. See [production blockers](docs/PRODUCTION_BLOCKERS.md) before
planning a public demo.

Local environment files, credentials, databases, virtual environments, and demo
access files are excluded from version control. Use `backend/.env.example` as
the configuration reference.
