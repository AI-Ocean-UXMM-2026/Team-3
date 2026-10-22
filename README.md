# LannPya AI - MTT local integration

Development reference: `mtt`. This feature worktree connects MTT's Signboard
dispatcher/customer/rider UI to the existing FastAPI/SQLAlchemy backend through the
protected local BFF. Private credentials stay server-side. Real rules parsing;
AI enrichment remains MOCK. No final AI provider is selected.

```powershell
npm.cmd start -- --port 8781 --state mtt-local
```

Open http://127.0.0.1:8781 (loopback only).
[Mapping/routing MVP](docs/mapping-routing/ARCHITECTURE.md) adds explicit simulated
route previews, OR-Tools multi-rider optimization and separate assignment commits.
Live routing remains disabled pending approved server credentials and provider verification.
[MTT startup and workflows](docs/mtt-integration/WORKFLOWS_AND_STARTUP.md),
[baseline audit](docs/mtt-integration/MTT_BASELINE_AUDIT.md),
[database](docs/mtt-integration/DATABASE_ARCHITECTURE.md),
[services and keys](docs/mtt-integration/API_KEYS_AND_SERVICES.md),
[verification](docs/mtt-integration/PHASE19_VERIFICATION.md).

- frontend/: preserved MTT Signboard; root is LIVE_BACKEND under the local launcher,
  prototype.html is DEMO_SIMULATION; static-only hosting is explicitly simulation.
- backend/: FastAPI, migrations, buyer/rider services and preserved QA tools.
- order-parser/: optional TypeScript AI/parser research; not the live API.
- scripts/: local startup, Python environment selection and static frontend build.
- docs/: contracts, source provenance and final verification.

The advanced developer API UI remains at `/api.html`. Earlier final-integration and
phase reports below describe their original snapshots. Production authorization,
live PostgreSQL and trusted geospatial validation remain blockers. Local use only.

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
