# LannPya AI — Unified Frontend, Backend and AI Architecture

Proposed base: `main`. Proposed head: `integration/lannpya-final`.
**Prepared locally only; no push or pull request has been made.**

## Description

Connect dispatchers, verified buyers and riders to one persisted order-to-delivery workflow.
The unified local site replaces disconnected live/demo states with real FastAPI operations,
retains deterministic Burmese parsing and makes simulated features explicit.

Includes protected local order management, buyer links/verification and dispatcher review,
Leaflet pin selection, rider assignments/queues, route departure, COD recording/physical
hub closeout and chronological persisted event history. Real AI stays disabled; prepared
HTTP adapters share strict sanitization, evidence validation and deterministic fallback.

## Contributions selected

| Source | Reused |
| --- | --- |
| main plus preserved local hardening | Authoritative Python backend, security, persistence, migrations, parser and tests |
| ZLHantigravity / checkpoint lineage | Connected three-role frontend, physical custody, route/COD extensions and design |
| mtt research lineage | Preserved TypeScript parser/provider research; not live AI |
| Integration Phases 15/16 | Chromium suite, reliability fixes, customer map, timeline and Python adapter readiness |

Latest remote review includes mtt `7ffbd41` and its 93 passing candidate Node tests.
Its new Signboard redesign remains on mtt: adopting it would replace the selected design
and require a separate live-state/CSP/service-worker integration review. Team branches and
their commits are preserved; this PR does not blindly merge their ancestry.

## Validation

- Python: **870 passed**, including migration, rollback, security and persistence coverage.
- Node: **116 passed** (98 frontend, 17 dashboard, one real HTTP controller workflow).
- TypeScript: **141 passed** and type-check passed.
- Real Chromium: **33 passed**, including the complete delivery/COD journey and all five viewports.
- Frontend build: 24 static assets validated; Ruff lint/format and dependency checks passed.
- Fresh migration to `0004_workflow_routes`, metadata drift, isolated round-trip and offline
  PostgreSQL SQL compilation pass in the Python suite. No production connection was made.
- Isolated wheel build confirms `httpx2` is a runtime requirement, fixing the previously
  development-only declaration for the imported AI transport.

CI now installs pinned root dependencies and runs Chromium as well as existing checks.
The GitHub Actions workflow has not executed remotely because this branch is unpublished.
Raw browser exports, screenshots, builds, databases, logs and environments are excluded from
Git; generate evidence locally using the handoff. Curated verification documents are included.

## Known limits

Local developer identities/BFF are not production authentication. Public deployment requires
proper identity/tenant authorization, PostgreSQL verification and secure hosting. No trusted
geospatial dataset is installed; buyer confirmation is not automatic GREEN. AI providers and
quality remain unverified externally. Optional map tiles require buyer consent; automated
tile tests use fixtures. Cash records do not transfer money. The demo prototype is separate.

## Reviewer checklist

- [ ] Run the unified site on loopback with fictional data; distinguish live versus demo mode.
- [ ] Review parser provenance, provider opt-in guards and privacy limits.
- [ ] Verify buyer lockout, pin review, rider permissions and protected history.
- [ ] Process one COD delivery and physical cash closeout; refresh and inspect persisted events.
- [ ] Run tests/build and review migration/security checks.
- [ ] Review `TEAM_INTEGRATION_HANDOFF.md` and the deferred Signboard design decision.
- [ ] Confirm no secrets/runtime databases/generated artifacts enter the proposed commit range.
- [ ] Review local CI changes; public deployment and main merge remain separate approvals.
