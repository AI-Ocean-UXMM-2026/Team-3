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

- [Frontend handoff](docs/FRONTEND_HANDOFF.md)
- [REST API contract](docs/API_CONTRACT.md)
- [OpenAPI schema](docs/OPENAPI.json)
- [Repeatable local demo](docs/DEMO_GUIDE.md)
- [Phase 7 verification](docs/PHASE7_VERIFICATION.md)

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
