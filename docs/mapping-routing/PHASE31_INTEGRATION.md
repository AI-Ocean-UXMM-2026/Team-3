# Mapping release integration into the team review branch

## Sources and preservation

- Source: `feature/mtt-maps-database-integration`, release commit
  `5ede5716245e55809d3c4a291bb31bc78a496322`.
- Original remote target: `integration/lannpya-final`,
  `b57f15f32f96581138b19461995e5cf9934c4b70`.
- Remote `mtt` at inspection: `71ef2b80745a5a07922bedbda17fb3c70874428d`.
- Remote `main` at inspection: `f175883727ad85b8eaa3f75c5d829abff32e72a0`.
- Isolated review worktree: `LannPya-AI-mapping-review`, local branch
  `integration/mapping-release-review`.

The original target is an ancestor of the source. There were no target-only commits
and no merge conflicts. A verified fast-forward in the isolated review worktree
preserves every original target commit and the complete source history. This avoids
an artificial copy of the frontend or selective commits that would omit required
MTT frontend moves and their backend integration.

The source contains 26 commits beyond the original target and changes 142 files
relative to that target, before this integration report. Of those changes, the final
mapping release commit contains 37 files. The existing MTT UI, local authenticated
proxy, parser, buyer review, rider/COD flows and API workspace remain together.
The AI implementations and preserved TypeScript parser have no changes relative to
the target. Earlier migrations are retained; migration `0005_routing_plans` adds
route-plan storage.

Newer `mtt` commits after the source's `0e95c6a` baseline include order/rider pop-ups,
mobile polish, saved buyer state, rider history and cash-handover presentation.
They are deliberately not imported into this mapping release: they require a
separate compatibility review against the now-tested MTT/live API integration.
No existing teammate branch or worktree is reset, replaced or deleted.

## Integrated functionality

- Customer Leaflet pin selection/dragging, permission-based GPS and error recovery.
- Authorized location submission and dispatcher review; no automatic geospatial
  verification or GREEN upgrade from an initial pin.
- Provider-independent routing, Google and ORS adapter boundaries, explicit
  single-request consent, durable request limits and default zero live budget.
- OR-Tools bounded multi-rider planning with hard capacities/time windows,
  service times, assignment consistency, return-to-hub and weighted priorities.
- Separate previews and commits, persistent versioned plans and stale-plan checks.
- Approved rider stop sequences, manual queue refresh, navigation links, COD and
  persisted event history.
- Reusable browser acceptance coverage across five viewport sizes and an isolated
  real HTTP/backend-restart verification script.

## Verification

Checks run in the new review worktree with its own pinned Python environment and
fresh npm dependencies; Python's imported `app.__file__` was verified to point here.
All mutating tests use synthetic data and isolated temporary SQLite databases.

| Check | Observed result |
|---|---|
| Full Python backend suite | 1003 passed, 0 failed; 223.00 seconds |
| Full real Chromium browser suite | 59 passed, 0 failed; 8.8 minutes |
| Frontend Node tests | 117 passed, 0 failed |
| Dashboard/client Node tests | 17 passed, 0 failed |
| Preserved TypeScript/Vitest tests | 141 passed, 0 failed |
| TypeScript type check | Passed |
| Native real HTTP integration | 1 passed, 0 failed |
| Mapping real HTTP/backend restart | Passed |
| Frontend production build | 27 validated static assets |
| JavaScript syntax | 42 tracked files passed |
| Ruff lint / formatting | Passed; 127 Python files already formatted |
| Python dependency check | Passed; no broken requirements |
| npm direct dependency trees | Valid; fresh npm installs reported zero vulnerabilities |

The HTTP/restart scenario submits a buyer pin, approves the request, previews and
commits a SIMULATED route, retrieves the rider sequence, completes COD delivery and
then restarts the backend. It verifies the DELIVERED order, COMMITTED plan, ordered
stop and 12 events persist, with COD 25000 and AMBER confidence. Unauthorized direct
private reads are rejected. External routing and AI call counts are both zero.

The Python suite includes isolated migration/schema-drift, rollback, routing,
optimization, GPS approval and security tests. Three upstream OR-Tools SWIG
deprecation warnings were observed; none are test failures. Chromium exercised
the mapping/delivery journey at 1440x900, 1366x768, 768x1024, 390x844 and 360x740,
including GPS grant/denial, mouse/touch pin dragging, review, optimizer preview,
commit, rider COD, navigation and stale-plan replanning. Existing parser, buyer
lockout/expiry, privacy, hub closeout, event-history and prototype regressions pass.
Google SDK/provider behavior is mocked; no real Google renderer or live matrix
is claimed. No application
logic changes were needed in the review worktree; only this report and the complete
file inventory are added beyond the source release.

## Security review

- Scanned 290 new historical file blobs between original target and source release:
  no Google-key, GitHub-token or private-key pattern matches.
- Scanned all 447 tracked files and 28 files produced under `frontend/dist`:
  no matches for those credential patterns.
- No private environments, virtual environments, node_modules, database files or
  logs are tracked. `backend/.env.google-demo.local` remains Git-ignored and absent
  from the integration worktree; its contents were not read or copied.
- No Google key is staged or bundled. Live requests remain opt-in with a default
  zero budget; browser tests force offline configuration and zero live calls.
- These bounded checks do not prove that every possible secret format is detectable.
  Existing development-only access is not production authentication.

## Provider and deployment boundaries

No new live Google, ORS or external AI requests are authorized or performed for this
integration. Tests disable external routing and use recorded/mocked responses.
The historical one-request Google success remains historical evidence only.
OR-Tools currently uses explicitly SIMULATED matrix data. Real road-matrix
optimization requires an authorized provider and entitlement. Google route geometry
is withheld from Leaflet; the Google renderer boundary is stub-tested, and a real
embedded Google map requires a separately restricted authorized browser credential.
Key-free external Google Maps navigation remains available.

The private Google environment is not copied into this review worktree. Production
authentication and production PostgreSQL remain unverified; this is a local demo
release, not permission for public deployment. No database-provider migration,
Supabase work, billing activation or deployment is included.

## Publication

Only a normal update of `origin/integration/lannpya-final` is authorized. Publication
requires passing checks, a credential/artifact review and a fresh remote check.
The final commit is identified by this report's containing Git commit and the
publication response; embedding that commit's own hash in its contents is avoided.
All listed checks passed before publication preparation. Generated changes to two
pre-existing routing screenshots are restored to the source release versions, so
this review adds only this report and `PHASE31_INTEGRATED_FILES.json` beyond the
source release. The original source worktree remains clean after its release commit.
