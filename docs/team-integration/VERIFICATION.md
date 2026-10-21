# Phase 17 verification and publication boundary

Executed locally on 2026-10-21, Windows, Python 3.14.7 and Node 24.20.0. Tests use isolated
SQLite and fictional data. Real AI remains disabled. No production database or remote
application was exercised, and no branch was pushed, merged or published as a PR.

| Check | Observed outcome |
| --- | --- |
| Complete Python suite | **870 passed**, 94.25s |
| Node frontend | **98 passed** |
| Dashboard / real HTTP controller workflow | **17 + 1 passed** |
| TypeScript parser | **141 passed**, nine files; type-check passed |
| Real Chromium | **33 passed**, 169.83s; zero failures/skips/retries |
| Frontend build | 24 validated static assets |
| Ruff lint / format | Passed; 105 files formatted |
| Dependency checks | pip check and npm ls passed |
| Runtime packaging | Isolated wheel build passed; metadata declares httpx2 as a runtime requirement |
| Latest mtt candidate, separate temporary extraction | **93 Node tests passed**, zero failures/skips; not included in integrated totals |

The complete merchant/chat -> buyer verification/pin -> dispatcher review -> rider
assignment/departure -> delivery/COD -> hub closeout journey passes through actual UI/API
controls. Existing rescheduling, failure/return, lockout/expiry, history, privacy, role/CSRF
and five-viewport cases pass. Browser street-tile requests are intercepted, not live
third-party calls. Node totals include their framework's reported parent/subtests.

## Database evidence

The full suite includes `test_migrated_schema_and_no_drift` (13 tables, foreign keys on,
head `0004_workflow_routes`, no SQLAlchemy metadata drift, idempotent upgrade), an isolated
empty-database downgrade/re-upgrade, offline PostgreSQL migration compilation, transaction
rollback and persistent native buyer capability/database reopen cases. No developer database
was downgraded or reset. PostgreSQL offline SQL is not production PostgreSQL verification.

## Small readiness fixes

The prepared HTTP adapter is imported by the runtime, but its client had been declared only
under development extras. `httpx2` is now a normal runtime dependency; the existing locked
version was not upgraded. An offline no-build-isolation attempt found the shared environment
lacked setuptools. Standard isolated wheel building then installed the declared build
prerequisite in a temporary environment and passed; shared environments were not modified.

CI path filters now include root lock/config/tests; CI installs pinned root dependencies
and Chromium before running browser tests. Existing backend, frontend and TypeScript
checks remain. **This workflow is prepared locally; no GitHub Actions run is claimed.**

## Safety review

- Reviewed tracked and publishable untracked paths and their diff. A targeted scan covered
  357 text files before final report staging; no recognizable provider/GitHub key or private
  key block was detected. No stored local secret values were available in the checked
  .env/access-file locations for exact-value comparison. This is not a universal secret audit.
- No tracked live .env, DB, private-access JSON, environment, node_modules or build output
  was found. Only the example environment file is retained. Existing branch history also
  showed no additions at the checked secret/database path patterns.
- New generated PNGs and browser/evaluation exports stay local and ignored, alongside raw
  test results, logs and build output. Curated Markdown, test fixtures, dependency locks and
  licensed vendored runtime assets are intentional review inputs.
- No public port/tunnel, provider activation, account change, force push or history rewrite
  occurred. Existing teammate branches and worktrees were preserved.

Git's CRLF-to-LF notices reflect existing attributes, not conflicts; whitespace checks pass.
No merge conflict is present. The new mtt Signboard presentation is an explicit deferred
integration/design decision, not a silently discarded feature.

## Reviewer decision

The candidate is suitable for a **review branch push after explicit approval**, not public
deployment or automatic main merge. Remaining blockers: production authentication/tenant
authorization, PostgreSQL deployment, trusted location verification and approved real-model
privacy/quality evaluation. Review the PR draft and team handoff before publication.

The verified feature changes are committed locally as `db8647e` (41 files), following the
existing integration baseline `e3bfd9a`. The subsequent team-preparation commit contains
only CI and the four handoff/review documents. Final remote re-fetch confirmed the four
reviewed SHAs in `BRANCH_SYNC.md`; no remote integration branch existed at that check.
