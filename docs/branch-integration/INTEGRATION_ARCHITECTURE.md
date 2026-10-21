# Baseline decision

Create a new integration branch from main and overlay the preserved hardened local backend,
then apply selected ZLH workflow additions using shared-ancestor three-way file reconciliation.
The only content conflict was the management schema; it was reconciled explicitly to retain
NUL/input safeguards and additive parcel metadata. Original legacy requests still require a
merchant unless explicit parcel context is supplied. All original backend tests are retained.

There is one backend at backend/, one chosen live frontend at frontend/index.html, and an
explicit separate DEMO_SIMULATION at frontend/prototype.html. order-parser/ is a preserved,
tested optional experiment, not another authoritative order database or live API. A guarded
local BFF reuses the testing dashboard boundary and actual backend app factory/role clients.
Persistent workspace storage is isolated under backend/data/integrated-workspaces/local/;
normal project data is untouched. No destructive reset is exposed for the persistent app.

Reasons: preserve the most complete backend and security; keep the best available existing UI;
reuse tested route/cash workflows instead of fake compatibility endpoints; keep all role
credentials server-side; use one canonical DB and migrations. Live failures never trigger a
simulated success. AI defaults mock; provider/model choice is not fixed by the PRD's suggestion.
Source refs and file hashes preserve provenance without merging nested directories or changing
teammates' branches. Real authentication/public deployment remains a separate prerequisite.
