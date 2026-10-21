# Start the integrated application

From the integration worktree (not the original main worktree):

```powershell
cd C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI-integration
npm.cmd start
```

Open http://127.0.0.1:8780. Use 127.0.0.1 exactly. npm.cmd avoids this machine's restricted
PowerShell npm.ps1 shim without changing execution policy. On other shells, npm start works.
The launcher validates/builds the unchanged vanilla ES-module assets, locates an existing
installed Python environment in Git worktrees or bootstraps backend/.venv from pinned locks,
and runs the guarded backend/UI together. No Vite migration or extra frontend framework.

Use `npm.cmd start -- --port 8781` for a conflict. The launcher does not kill a port owner.
Use `--state demo-review` for another isolated persistent fixture set or `--temporary` for
a disposable demonstration. Node >=22.18 and Python compatible with requirements-dev.lock
are required. LANNPYA_PYTHON can explicitly select an installed environment. No cloud setup,
real .env or API key is necessary. Shared worktree Python is currently reused here.

Open Admin and enter the local workspace; no private token entry. Rider uses a local rider
ID (blank selects the initial rider). Buyer opens a generated native link in the same local
app, verifies four synthetic digits, and submits a proposal. Fresh process persistence is
real SQLite; close with Ctrl+C. Public deployment is blocked by missing production login.

The build is static validation/copy to frontend/dist; the loopback shell serves first-party
source assets with no-store. It does not bundle secrets. Original backend health and API
are exercised internally through the BFF. localhost on another computer is another server;
there is deliberately no LAN origin, tunnel or cross-computer privileged access.
