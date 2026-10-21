# GitHub checkpoint — admin-to-rider workflow

Branch: `checkpoint/admin-rider-workflow`

This branch captures the complete three-sided project: Admin, Customer and Rider.
It includes the API-backed workspace, separate device-local prototype, source,
tests, documentation and original PRD. The earlier Git history is retained.

The repository root is now the application root. The existing backend and API
documentation live under `lannpya-ai/` to preserve the app's current relative paths.
The `main` branch is not changed by this checkpoint branch.

Private runtime credentials, environment files, customer/order databases, local
backup archives, virtual environments and browser-local data are not uploaded.
`CHECKPOINT.md` describes a separate private local backup; its files are deliberately
absent here. Source test fixtures and documentation examples are not live order data.

## Fresh checkout

Use Node.js 20+ and Python 3.12. In PowerShell, from this repository root:

```powershell
npm test
npm run check
cd lannpya-ai/backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m scripts.run_workspace
```

Open `http://127.0.0.1:8000/api.html`. The launcher creates a new local database and
fresh per-role credentials under ignored `lannpya-ai/backend/data/`. Read that
credential file privately; never upload or share it. See
[API_INTEGRATION.md](API_INTEGRATION.md) for the workflow and connection instructions.

Verification at this point: 85 JavaScript tests, syntax checks and 447 backend
tests passed. Real-browser/mobile visual QA is still outstanding. API mode is
online-only and local-development-only; this is not a production deployment.
