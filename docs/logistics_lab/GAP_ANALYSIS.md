# Gap analysis before implementation

The overnight audit already supplied a 300-record parser corpus, 749 tests, transaction/
security/concurrency regressions, an isolated HTTP demo and serial SQLite microbenchmarks.
Repeating or replacing those components would add little evidence.

The useful remaining gaps were:

1. No seeded multi-merchant/rider order plan with explicit duplicate and incomplete inputs.
2. No event-derived operations analytics distinguishing ingested backlog from deliveries.
3. No assumption-only manual-vs-LannPya comparison with counterexamples and sensitivity.
4. No precision/recall computation over the existing known parser labels.
5. No repeatable 20-order evidence dataset and redacted per-operation trace/export contract.
6. No tests for the new simulator's reproducibility, money, export privacy and failure isolation.

The logistics lab fills these gaps without changing application modules or endpoints.
Prior evidence is reused: existing queue, security, expiry, rollback, geofence and concurrency
tests run in the complete regression suite. Their implementation is not duplicated.

Unresolved prerequisites are unchanged: actual frontend source, production identity/tenant
authorization, secure public hosting, live PostgreSQL and trusted geospatial data. No lab
result resolves those product/deployment limitations.
