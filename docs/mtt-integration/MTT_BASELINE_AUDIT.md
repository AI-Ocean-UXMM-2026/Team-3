# MTT baseline audit

Audited 2026-10-21. Authoritative parent: `origin/mtt` at
`0e95c6a9970198a345622a145330749aaabca83f` (merge PR #5).
New local branch: `feature/mtt-maps-database-integration`.
Worktree: `C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI-mtt-integration`.

The remote was fetched before creating this worktree. Its starting tree was clean.
The original main, previous integration worktree and teammates' branches were preserved.
No old branch was merged, pushed or reset. The older unpublished navigation fix was
reviewed and adapted to MTT's relocated developer tool only after reproducing its race.

## Observed baseline

| Area | Implementation at the MTT parent | Integration gap |
| --- | --- | --- |
| Product UI | Signboard HTML/CSS, vanilla JavaScript, bilingual dispatcher/buyer/rider views | `functional-app.js` used the synchronous localStorage domain exclusively |
| Demo parser | Bundled TypeScript rules/dictionary/Zawgyi converter | Separate from authoritative Python REST parser |
| Backend | FastAPI, Pydantic, SQLAlchemy 2, Alembic | Mature backend retained; product UI did not use it |
| AI | Provider-independent Python interface; mock default; prepared gated adapters; optional TS Gemini research | No real AI activated or measured |
| Maps | Shared Google/Leaflet helper, vendored Leaflet 1.9.4 | Root Signboard did not load the helper; schematic/fixture geometry in demo |
| Database | SQLite locally; PostgreSQL-compatible models; four migrations | Browser prototype successes did not mean SQL persistence |
| Buyer security | Hashed links/sessions, expiry, three-attempt lockout, SQL rate limits, review workflow | Native API connected only through developer workspace |
| Rider operations | Server-bound identities, assignments, queues, COD, route/cash custody | Signboard used browser domain state |
| Local BFF | Loopback-only proxy, exact host/origin, CSRF, HttpOnly session, server-held private credentials | Existing `/api.html` developer UI worked independently |
| CI | Pinned Python/Node installs, pytest, Ruff, Node/TS/Chromium checks | Navigation race remained in relocated developer UI |

The README's reference to the previous ZLH UI as the primary screen was stale.
Current `PRODUCT.md` and `DESIGN.md` describe MTT's Signboard;
its design and standalone demo remain in place.

## Baseline checks actually executed

- Python: **870 passed**, 91.10 seconds.
- Frontend Node suite: **99 passed**.
- Static build: **21 assets validated**.
- Root dependency install: lockfile install succeeded, no audit findings reported by npm.

The historical 33-browser figure was not treated as a fresh baseline result.
The subsequent full browser run exposed the developer-page navigation race and
a stale test assuming the root was still a demo. See the final verification report.

## Boundaries retained

35 business API operations are generated from the application in [OPENAPI.json](OPENAPI.json).
The new runtime configuration route belongs to the local BFF, not the business API.
No business endpoints, ORM models or migrations were renamed or replaced.
No real customer data, regular development database or external database was used.

Public deployment remains blocked by missing production authentication/authorization.
No trustworthy township polygon dataset or geocoder exists. Buyer/dispatcher approval
does not establish independent geospatial accuracy. Shop-preparation policies, retry
planning and offline replay remain demo-only until their server contracts are defined.
