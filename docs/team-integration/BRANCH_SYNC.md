# Phase 17 branch synchronization review

Repository: `https://github.com/ZawLwinHtoo/lannpya-ai.git`.
Preparation started on `integration/lannpya-final` at
`e3bfd9afc7f4b25420b92d520cfb81377caef8f7`. Phase 15/16 changes were uncommitted and preserved.
The original main and detached review worktrees were not modified.

## Fetched sources, 2026-10-21

The wildcard fetch refspec covers all remote heads. `ls-remote --heads` confirmed four
branches; `origin/HEAD` is an alias, not a fifth branch.

| Branch | Current reviewed SHA | Change since Phase 14 |
| --- | --- | --- |
| main | `a030097382cffaacae7f057de884966081422b69` | None |
| ZLHantigravity | `3018adffa6eb027785cf0dd983184f92a2be8d1f` | None |
| checkpoint/admin-rider-workflow | `c57f79bc7b188f67e8316ca5e791a288babb8998` | None |
| mtt | `7ffbd41e9f0b12917243c4c9b038220cf7459635` | Six commits after `aa4ae23cda6a1f30824cc37d90af11294425ff93` |

The initial fetch found no movement. A recheck during verification detected mtt's newly
published advancement, which was then fetched and reviewed. No remote branch was modified
by this work. No integration branch existed remotely at inspection time.

Integration uses selected/adapted components, not ancestry merges. At the initial local
commit, `rev-list --left-right --count remote...HEAD` was main 0/1, ZLH 8/1,
checkpoint 1/1; after mtt advanced, mtt was 9/1. Those branch-only commits are not all new
missing functionality. See the original `branch-integration/` component analysis.

## New mtt delta

| Commit | Purpose |
| --- | --- |
| `9f0c465` | Signboard device-local UI overhaul |
| `1652fe0` | Finish-review fixes and UI handoff |
| `ade5715` | Secondary dispatcher pages, rider dialogs/night mode |
| `6b800c4` | Text density and navigation refinement |
| `453e373` | Inline navigation and mobile wordmark |
| `7ffbd41` | Merge that design lineage into mtt |

18 paths changed: new `signboard.css`, brand SVGs, DESIGN/PRODUCT/HANDOFF/Burmese-review
documents and design metadata; modified static entry, view controller, cache list,
package metadata and two test assertions. The backend, migration history, workflow-domain
logic and TypeScript AI implementation did not change in this delta.

The candidate was extracted at its exact SHA into an isolated temporary directory.
Its six-file root Node test command passed **93 tests, zero failures/skips**. This was a
candidate DOM/domain test run, not a real browser or live backend integration of Signboard.
No candidate dependencies, local storage or database were shared with the integration app.

## Reconciliation decision

| Component | Decision / evidence |
| --- | --- |
| Mature backend and existing local hardening | Keep authoritative integration version; 870 tests pass |
| ZLH-derived live Admin/Customer/Rider UI and routes/COD | Keep selected design and real API connection |
| Phase 16 Leaflet selection and persisted timeline | Keep; Chromium coverage passes |
| mtt TypeScript research | Already preserved, 141 tests pass; not activated |
| New Signboard design/copy/assets | Keep on mtt pending a separate design/integration decision |
| New CRLF-aware test helper | Equivalent protection already exists locally |
| New service-worker cache list | Do not copy: live app explicitly excludes API/live navigation caching |
| External fonts / brand SVG loading | Requires deliberate local CSP/static-asset adaptation before adoption |
| Business wording about fixed departure/offline behavior | Documentation/prototype assumptions, not authorization to change backend policy |

mtt's handoff records design/Burmese approval in another context. It is not treated as an
instruction to override this task's requirement to preserve the current frontend design.
Its device-local state and fixed demo geofence must not replace persisted orders or trusted
server-side location policy. A future UI port should adapt presentation onto the existing
API controller and retain the 33 Chromium cases. No broad merge/cherry-pick was justified.

## Git warnings

Git reports CRLF-to-LF normalization for edited Windows text files. `.gitattributes` already
requires LF for source, CRLF for batch files and binary treatment for images/databases.
`git diff --check` passes; no global renormalization, destructive reset, clean, history
rewrite, main merge or teammate branch update was performed.
