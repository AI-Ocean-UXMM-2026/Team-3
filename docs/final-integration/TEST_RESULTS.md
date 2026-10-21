# Final verification results

Executed 2026-10-21 on Windows 11, Python 3.14.7 and Node 24.20.0. No real customer data,
external AI request, production DB, public deployment or remote push was used.

| Check | Actual result |
| --- | --- |
| Original main-worktree hardened overlay, rerun independently | 812 passed in 73.69s |
| Detached ZLH backend at initial 172af96 | 447 passed in 61.37s |
| Latest ZLH frontend at 3018adf | 93 passed |
| Integrated complete Python suite | **839 passed**, zero failed/errors/skipped, 86.21s |
| Integrated Node suite | **112 passed**, zero failed/errors/skipped (6.87s reported) |
| TypeScript parser | **141 passed** in nine files; typecheck passed |
| Actual selected frontend HTTP workflow | Passed: raw save/provenance, buyer verification/pin review, assignment/departure, COD delivery, hub closeout, corrected RED/failed delivery |
| Process restart/persistence | Native buyer capability still valid; order/events persisted, seeded actors stable, verification required again |
| Build | 21 validated first-party static assets produced in frontend/dist |
| Lint / formatting | Ruff passed; 102 Python files already formatted |
| Dependencies | pip check: no broken requirements; npm lock install completed |
| Running site | http://127.0.0.1:8780 serves chosen UI; proxied health 200; private assets 404 |
| Browser visual tests | Not performed: CUA browser inventory was empty; no screenshots claimed |

The Node count includes parent/subtests reported by Node, not 112 distinct user journeys.
It combines retained UI/domain/model tests, local adapter tests, original dashboard tests
and the actual selected-controller/HTTP integration case. The TypeScript count is a separate
Vitest suite. Do not sum source-candidate reruns into the integrated totals.

The first integrated full Python run exposed one missing documentation entry for additive
/api/session in the old handoff; all 838 other cases passed. The handoff was updated with
all six new operations and the contract-completeness test passed. The final full run then
passed 839. Final lint found two overlong notice strings; adjacent-string wrapping fixed
those without changing response text/behavior, lint/format passed and persistence/capability
regression passed again. No failing test was deleted or skipped to conceal an issue.

New integration-specific Python coverage: seven cases for persistence/native capability
across restart, four unsafe storage labels, production factory refusal and unauthenticated
proxy rejection. Twenty native workflow cases were retained from ZLH alongside all 812
hardened baseline cases. Existing schema tests now assert the additive table/head and generated
35-operation contract. Existing old-operation behavior remains covered.

The selected frontend test uses its real api-workspace controller and LocalWorkspaceApi,
a lightweight DOM adapter and a separately launched HTTP process with temporary SQLite.
It performs actual validation and database writes, including explicit approvals and physical
receipt/departure assertions. Only the UI's two-second cancellation timer is advanced in
the DOM harness; the backend clock/policy is not bypassed. Core provider failure, malformed
AI, timeout, lockout, invalid status/coordinate, rollback, COD and permission tests all reran.
No browser rendering/mobile usability or actual external provider response was tested.

CI is updated locally for the expanded frontend/build/integration/parser checks. No GitHub
Actions run occurred because the branch was not pushed. Production PostgreSQL and public
security remain blockers regardless of these passing local tests.
