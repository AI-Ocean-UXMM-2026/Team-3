# Defect inventory

| Priority / finding | Evidence and impact | Resolution / regression |
| --- | --- | --- |
| P1 reliability: NUL accepted in text | A parse request containing escaped U+0000 returned 200 before the change. Structured/buyer text validators also allowed it. PostgreSQL text cannot represent NUL, so accepting it creates cross-database write/search failures. SQLite can also report truncated string length at NUL. | Reject NUL in raw input, editable order text, buyer instructions/reference/review reason and order search. Existing 422 envelope; new tests cover fields, API privacy and search. PostgreSQL runtime remains unverified. |
| P1 resilience: detector failure escaped parsing | Detector construction/probability call had no recovery path. An unavailable local detector could turn otherwise usable phone/COD extraction into an API failure. | Catch detector exceptions, log exception type only, retain input and normalize digits, mark encoding uncertain/RED. Injected failure test proves deterministic phone retention and no private exception logging. |
| P0 before public use: no production authentication | Known development-only access design; private endpoints are intentionally loopback/actor-bound and production-disabled. | Preserved fail-closed behavior. Needs a separately approved identity/tenant/role design before public access. No security bypass added. |
| P1 integration: frontend assumptions differ | Guide calls buyer token JWT, treats pin as verified and uses numerical confidence. Actual contract differs. | Existing Phase 8 compatibility matrix and current audit document the mappings; frontend source is absent. |
| P2 performance: search grows with table size | 5,000-order fixture combined search has a higher measured latency than 100-order fixture; substring filters and global sorting scan data. | Document measurements. No index/migration added without a product latency target or PostgreSQL query-plan evidence. |
| P2 duplicate order create semantics | POST /api/orders has no client idempotency key; repeated creates are distinct UUID records. | Preserved documented behavior. A timeout must be reconciled before retry; buyer/rider actions already have request UUID replay protection. |

No new broken-access-control, lost-update or duplicate-completion defect was reproduced in
the bounded tests. This does not establish absence of all vulnerabilities or PostgreSQL races.

The NUL restriction is specified by the official
[PostgreSQL character-type documentation](https://www.postgresql.org/docs/current/datatype-character.html).
This source check does not replace real PostgreSQL execution testing.
