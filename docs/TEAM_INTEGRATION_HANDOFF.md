# Team integration handoff

The review candidate is `integration/lannpya-final`, prepared in the integration worktree.
Publication is pending owner approval. No push, PR creation, main merge, collaborator invite
or deployment has occurred. The current site is local-only at http://127.0.0.1:8780.

Read [branch synchronization](team-integration/BRANCH_SYNC.md), the [PR draft](team-integration/PR_DRAFT.md),
[verification](team-integration/VERIFICATION.md) and [Phase 16](PHASE16_MVP_COMPLETION.md).

## Source of truth

`backend/` is the sole authoritative API/database implementation. `frontend/` contains the
selected connected vanilla-JavaScript UI plus a separately labeled browser prototype.
`order-parser/` is preserved research, not the runtime authority. Do not copy an older
`backend_repo/` or nested `lannpya-ai/` over this tree. Git ancestry alone does not identify
which features were adapted into the integration branch.

Latest mtt includes a Signboard redesign through `7ffbd41`, tested separately with 93 Node
cases. It has not replaced the selected UI. Decide its presentation port separately and
retain the current API controller, Leaflet, history, credential boundary and browser tests.
Other remote source heads remain unchanged at the SHAs in the branch review.

## Working together

After the integration branch is approved and published, each teammate starts a small feature
branch from that reviewed baseline, for example:

```text
git fetch origin
git switch -c feat/frontend-order-board origin/integration/lannpya-final
```

Until publication, do not assume that remote reference exists. Preserve existing team
branches and commit or otherwise safely preserve personal work before changing branches.
Use a separate worktree for parallel tasks on one machine. Do not force-push, reset another
developer's work or merge every source branch into the integration branch.

| Area | Coordination boundary |
| --- | --- |
| Frontend | Work under frontend; coordinate shared controller/API adapter edits. Keep secrets out of bundles and keep live errors distinct from demo simulation. |
| Backend | Work under backend/app with regression tests; communicate schema/error changes before UI adoption. |
| AI | Extend backend/app/ai adapters and synthetic tests. Preserve deterministic phone/COD and grounding. Model/provider/budget activation requires approval. |
| Database | Append coordinated Alembic revisions after the single current head, never rewrite applied migrations or test against a teammate's real DB. |
| QA / integration | Own cross-role browser contracts, safe fixtures, CI and small reviewed integration commits. |
| Docs / product | Keep API contract, handoff and known limitations aligned; approve major visual/business-policy decisions separately. |

Agree actual reviewers in the team; no ownership or repository permissions were invented.
For each PR, list trigger/behavior, affected endpoints, source branch/SHA, tests and limits.
Document additive changes in `API_CONTRACT.md`; coordinate breaking changes before coding
both sides. Do not rename stable endpoints merely to match a view's terminology.

Avoid simultaneous edits to `api-workspace.mjs`, shared styles, schemas and migration heads.
Make small commits; refresh remote metadata before review. Resolve conflicts by checking
both behavior and tests, not by accepting an entire older backend or demo controller.

## Local setup and verification

From a published checkout, Node >=22.18 and the supported Python environment are required:

```powershell
npm.cmd ci --ignore-scripts
npm.cmd --prefix order-parser ci --ignore-scripts
npx.cmd playwright install chromium
npm.cmd start
```

The launcher locates an existing Python environment or prepares `backend/.venv` from the
pinned development lock. `LANNPYA_PYTHON` can identify a known installed interpreter.
Use `npm.cmd start -- --port 8781 --temporary` for a disposable local demonstration.
Port conflicts are reported; never kill an unrelated port owner. Follow the complete
[Windows startup guide](final-integration/LOCAL_STARTUP_GUIDE.md) for environment details.

Verification commands: Python `-m pytest -q` and Ruff check/format in backend; root
`npm.cmd run test:frontend`, `test:dashboard`, `test:integration`, `test:browser`, `build`;
and `npm.cmd --prefix order-parser test` plus its `run typecheck`.
Browser tests start their own loopback instances with isolated temporary databases.

Screenshots and machine exports remain local, untracked outputs. Run browser tests and
`node scripts/summarize_browser_tests.cjs docs/phase16/BROWSER_OBSERVATIONS.json` to reproduce
browser evidence. `python -m tools.evaluate_ai_readiness` in backend emits offline JSON;
it makes zero model calls. Curated reports describe the observed runs, not remote CI results.

## Security and cross-computer integration

The loopback BFF holds private developer tokens and buyer authorization server-side.
Local role selection is a developer identity arrangement, not production login. Keep .env,
access JSON, DB files, logs, virtual environments and generated output out of Git. Example
environment files contain placeholders only. API keys must never enter Vite/browser settings.

`127.0.0.1` on another laptop points to that laptop, not this machine. Each developer can
run their own synthetic local environment. A shared online/LAN demo needs an explicitly
reviewed authenticated arrangement; do not open a public tunnel or expose the developer
token/BFF to make it convenient. CORS is not authorization. Production remains fail-closed.

Buyer pins require existing server review/trust rules; no fabricated GPS or automatic GREEN.
Real AI is disabled and the local workspace stays mock-only. Production authentication,
PostgreSQL, hosting/TLS and real-model privacy/quality evaluation remain open blockers.

## Copyable teammate message

“The integration candidate connects Dispatcher, Buyer and Rider to one persistent backend,
with secure buyer review, Leaflet pin selection and delivery history. Please branch from
the published integration candidate after approval, keep your current branch, and open a
small PR for your component. The new mtt Signboard design is preserved separately for a
presentation decision. Run locally with synthetic data; never put private tokens or AI keys
in the frontend. Share API/schema changes before altering both sides.”
