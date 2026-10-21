# Prioritized next steps

1. Import the teammate's existing frontend on its feature branch and run a full browser
   workflow against isolated local role instances. Use the Phase 8 integration playbook and
   current redacted samples. Keep fallback explicitly simulated.
2. Before any shared/public demo, design authenticated tenant/user/rider roles, secure HTTPS
   hosting/BFF boundaries, secret rotation, rate/abuse controls, privacy retention and logs.
   Keep current development token private and production APIs closed.
3. Validate migrations, concurrency, rollback, pooling and query plans against disposable
   PostgreSQL. SQLite tests and offline DDL are not production evidence.
4. Set a measured pagination/search latency target. The current 5,000-order serial search
   measurement is acceptable only as a local baseline, not a capacity promise. Consider
   targeted indexes/search only with plans and workload evidence.
5. Agree order-create idempotency/reconciliation behavior before unreliable-network pilots.
6. Expand the parser corpus with independently annotated, consented/de-identified real
   language samples. Do not mistake perfect template regression scores for field accuracy.
7. Choose/evaluate a real AI provider and trusted geospatial data in separate authorized
   phases; define privacy, quality and cost thresholds before activation.

No speculative authentication, routing, WebSockets, billing, tracking or provider feature
was implemented during this audit.
