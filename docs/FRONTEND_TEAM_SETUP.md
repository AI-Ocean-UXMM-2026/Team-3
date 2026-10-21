# Frontend team setup

The shared repository is https://github.com/ZawLwinHtoo/lannpya-ai.
The existing backend and docs are ready for local integration. `frontend/.gitkeep`
reserves the frontend directory; an application has not been imported or integrated.
No frontend framework has been selected by this preparation work.

## Join and contribute safely

The owner must grant repository write access through GitHub before a teammate can
push a branch. No invitation or permission changes were made here. A teammate without
write access can use a fork and pull request. Account access uses their own GitHub
credentials; never share the backend development token as GitHub authentication.

For a new local checkout:

```powershell
git clone https://github.com/ZawLwinHtoo/lannpya-ai.git
cd lannpya-ai
git switch main
git pull --ff-only origin main
git switch -c frontend/import-existing-app
```

Bring the existing application into `frontend/` on that branch. Preserve the original
project copy until review. Copy source, static assets, package manifest and its matching
lockfile, if present. Exclude the old `.git` directory, `.env` secrets, dependencies,
build output, caches, customer data and credentials. Keep one shared repository root;
do not initialize another repository inside `frontend/`. Inspect the files first if a
teammate has already populated the folder. Keep the placeholder until the import is ready.

```powershell
git status --short
git diff --check
git diff
git add -- frontend
git diff --cached --stat
git diff --cached
git commit -m "Import existing frontend application"
git push -u origin frontend/import-existing-app
```

Open a pull request into `main` for review by the backend developer and a frontend
teammate. These are contribution instructions; Phase 8A did not push or open a PR.
Do not force-push or resolve conflicts by discarding another person's changes.

Use short task branches such as `frontend/buyer-card` and `frontend/rider-queue`.
Before a new task, return to a clean `main`, pull with `--ff-only`, then create a new
branch. On an active branch, fetch and merge `origin/main` after committing your work.
If a merge conflicts, review both changes with the file owner before resolving it.
Coordinate shared files rather than making several competing API-contract edits.

## Ownership and API changes

Frontend work belongs in `frontend/`. Integration notes may be updated in `docs/`
with backend review. Coordinate changes to `backend/`, root configuration, `.gitignore`,
API examples and `docs/OPENAPI.json`. Never edit migrations, access checks, validation,
schemas or lifecycle rules merely to bypass an integration failure.

Propose a contract change with endpoint, existing behavior, proposed JSON/status code,
UI use case and compatibility impact. Agree on it before implementation. The backend
developer updates routes/schemas, tests, API contract and generated OpenAPI together;
the frontend handles the agreed contract on its feature branch.

## Local backend on each developer's computer

Python 3.11+ is required. In PowerShell from the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe scripts\init_local.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

The bootstrap generates private local configuration, applies migrations and seeds
synthetic merchant/dispatcher profiles. It does not overwrite an existing `.env`.
It does not create production accounts or a login endpoint. Open
http://127.0.0.1:8000/docs to inspect schemas. The normal instance represents one
server-bound actor. For the full merchant/dispatcher/rider workflow, stop that command
and use the isolated demo in a backend terminal:

```powershell
.\.venv\Scripts\python.exe scripts\demo_mvp.py --serve --frontend-origin http://localhost:5173
```

It starts three separate loopback instances sharing a fresh fictional SQLite database.
The printed ignored run directory contains `private_access.json` with matching role
URLs, IDs, local credentials and a fresh buyer link. Ports vary per run. Keep this file
private and outside the frontend document root. Ctrl+C stops the instances. See
[DEMO_GUIDE.md](DEMO_GUIDE.md) for fixture caveats and how the demo differs from real delivery.

## Start the existing frontend

For a plain HTML/CSS/JavaScript application with no build step, from the repository root
in a separate terminal:

```powershell
python -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

Open http://localhost:5173. This serves only `frontend/`, not the repository or private
backend data. A static server does not provide SPA route fallback: a buyer link such as
`/confirm/<token>` needs the frontend's own router/server fallback or an agreed local
entry-page mapping. Never log or persist the token to implement that mapping.

If the existing app has package scripts/build tooling, use its documented package
manager and lockfile instead. Its exact install/start command cannot be specified until
its source is available. Do not add React, Next.js or another framework for backend access.
Use a public configuration value only for the API base URL, never for a private token.

## Separate computers and development access

`localhost` always means the machine running the browser. Your teammate's browser at
`http://127.0.0.1:8000` reaches their own computer, not the backend developer's computer.
The supported arrangement today is a local backend plus local frontend on each laptop,
using independent synthetic data. Git synchronizes code, not SQLite data or credentials.
This does not require sharing the backend developer's private `.env`.

For local testing only, manually supply that laptop's generated role token at runtime
in a local developer UI or private tooling and keep it in memory. Do not commit or bundle
it, put it in an HTML file, public environment variable, URL, localStorage or analytics.
Buyer pages use only their link and short-lived buyer bearer credential, never a role token.
Private APIs additionally check the actual peer is loopback. CORS changes and `--host
0.0.0.0` do not grant safe LAN access. Do not use an unauthenticated tunnel or proxy.

A shared online API is not available. It requires authenticated tenant/role authorization,
HTTPS, a reviewed deployment and validated PostgreSQL setup. An authenticated BFF could
keep upstream credentials server-side, but would itself need session authorization,
role/tenant enforcement, CSRF protection where cookies are used, rate limits, and log
redaction. Merely forwarding everyone through a local proxy defeats the development
boundary. No such proxy was implemented or approved by this preparation.

## What the frontend teammate should provide

- Their source/import branch and current package manager, framework (if any) and start command.
- The exact local frontend origin/port, expected buyer-card route, and API base configuration approach.
- First screens to integrate and any mismatches found against the existing contract.
- Whether the next demonstration is local on one laptop or a shared online demo requiring authentication.

## Message to send

> The backend is in our shared lannpya-ai repo. Please clone it and import your existing
> app under frontend/ on a frontend/import-existing-app branch, then open a PR. Keep
> your old .git, .env, dependencies and build output out of the import. Start with
> docs/FRONTEND_TEAM_SETUP.md and docs/PHASE8_FRONTEND_INTEGRATION.md. You can run the
> backend and isolated demo locally on your laptop now. Let me know your start command,
> frontend port and buyer route. Keep private dev tokens out of browser builds; shared
> online testing needs proper authentication before we expose private APIs.
