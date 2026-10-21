# Source review

Four source branches were fetched and inspected: main, checkpoint/admin-rider-workflow,
mtt and ZLHantigravity. See [inventory](../branch-integration/BRANCH_INVENTORY.md),
[comparison](../branch-integration/BRANCH_COMPARISON.md) and
[ZLH review](../branch-integration/ZLHANTIGRAVITY_REVIEW.md) for SHAs, unique changes and actual tests.

The local hardened overlay was independently verified: 812 Python tests passed in 73.69s.
The detached ZLH backend passed 447 tests. Checkpoint/ZLH frontend harnesses revealed a
Windows CRLF import-removal issue; repaired retained UI cases pass in the integrated tree.
The mtt TypeScript parser passed 141 tests and typecheck; real API calls were not made.
Source main is backend-only; the three other snapshots share a combined native workspace.
ZLH includes mtt's AI package and small CORS/client/portability fixes, not a superior
replacement for the newer local backend. A separate integration branch was selected.

Actual PRD v2 was found in these branches and extracted/read. IA and use-case diagrams
were not found in the tracked source inventories. The older supplied Vite/Leaflet guide
does not describe this actual branch frontend: selected source is static vanilla ES modules
with an explicitly schematic map. We preserve its UI instead of inventing a Vite migration.
