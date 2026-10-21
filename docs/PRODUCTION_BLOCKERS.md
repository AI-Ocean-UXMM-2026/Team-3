# Prioritized readiness assessment

A private on-screen localhost demonstration using fictional data works now. An API/browser
application exposed to remote users is different: production currently fails closed.
Do not remove that gate or publish a development token to make a public demo work.

| Priority | Area | Current evidence and remaining work |
| --- | --- | --- |
| CRITICAL BEFORE PUBLIC DEMO | Authentication and role/tenant authorization | One actor/local token per instance; no real login/session lifecycle or tenant membership. Implement authenticated merchant ownership, tenant-scoped dispatchers, rider assignment authorization and revocation. No admin/shared dispatcher token in deployed JS. |
| CRITICAL BEFORE PUBLIC DEMO | Secure public deployment | No deployment performed. Require reviewed HTTPS hosting, secrets, trusted origin/client-IP/proxy rules, private DB network, edge/body limits and redacted logs. Keep production APIs disabled until this boundary exists. |
| CRITICAL BEFORE PUBLIC DEMO | PostgreSQL connection/migrations | SQLite persistence/migrations and offline PG DDL pass; live driver/server execution, locking, pooling, backups/restore and rollout are unverified. Test against disposable PostgreSQL before relying on public shared state. No paid account is needed for future local PG checks. |
| CRITICAL BEFORE PUBLIC DEMO | Privacy/sensitive data | Hashed tokens, expiry, lockout, short sessions and protected audits exist. Four digits plus a link is not phone-ownership proof. Review delivery/previews/referrers, frontend/proxy logs, retention/encryption/backups, audit access and privacy messaging before exposing real customer data. |
| IMPORTANT FOR MVP | Frontend integration | Handoff/helper/OpenAPI and backend HTTP flow work; no frontend UI supplied/modified. Build screens, validation/review/conflict states, abortable polling and real browser/mobile tests locally. |
| IMPORTANT FOR MVP | Error handling | Sanitized JSON/field locations/rollback exist. Phase 7 fixes browser-readable 500 and Retry-After headers. Frontend must distinguish network/preflight/HTML errors, authorization, review-200, conflict-409, locked-423 and rate-429. Production observability/readiness unverified; /health is liveness only. |
| IMPORTANT FOR MVP | Performance/operations | Bounded queues and SQLite concurrency tests exist; no fleet-scale load/latency SLA established. Measure parser sizes, polling, history/search, pool/write contention and recovery. Sync SQLAlchemy work within async creation and SQLite write serialization need evaluation before scale. |
| IMPORTANT FOR MVP | Courier/demo policy | Rescheduling/security delivery default to review. COD is an actor assertion, not payment/proof of delivery. Confirm courier cutoff/fees, AMBER dispatch policy, branding inputs and operator training; global local settings are not per-courier contracts. |
| POST-HACKATHON | Real AI activation | Model/provider undecided; local mock/disabled only. Choose and evaluate after privacy review, authorization, cost controls and transport safeguards. Rules-first demo works without an LLM; label mock/unavailable honestly. |
| POST-HACKATHON | Trusted geospatial verification | No reviewed boundary/street dataset or geocoding exists. Manual approval does not prove accuracy. Select/licence/validate trusted data and ambiguous/border cases before enabling GREEN/automatic relocation. Not needed for the honest AMBER/manual-review demo. |

Real AI and automatic trusted location verification become blockers if the demo promises
them. No WebSocket, optimization, tracking, spatial memory, billing or paid messaging
module is required for local frontend integration.

Recommended Phase 8: build frontend screens/browser tests locally while designing proper
tenant-aware authentication. Next verify disposable PostgreSQL and secure hosting before
an authenticated public pilot. Keep AI/provider and trusted-map choices explicit later decisions.
