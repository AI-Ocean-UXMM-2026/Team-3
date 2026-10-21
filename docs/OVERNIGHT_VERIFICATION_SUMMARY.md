# Overnight verification summary

Completed locally on 2026-10-21. No commit, push, deployment, frontend modification, paid AI
call or production database mutation occurred. Existing uncommitted Phase 8 work and the
user-supplied implementation guide were preserved.
Final Git fetch showed zero ahead/behind on main. All audit changes remain local and
uncommitted. The final scan checked 154 Git-visible working files against ten private
runtime values and common key signatures: no matches or broken report links were found.

## Actual results

| Item | Result |
| --- | --- |
| New Python tests | **323** (300 corpus cases plus property/validation/race coverage) |
| Full Python suite | **749 passed**, 0 failed/errors/skipped; console elapsed 53.69 seconds |
| Existing cases preserved | 426 |
| JavaScript helper tests | **4 passed** |
| Real HTTP demo | **68 cases passed**, storage reopened after shutdown |
| Independent OS HTTP clients | Same-version race -> **200/409**, version 2, one correction + creation event |
| OpenAPI | **29 operations**, existing snapshots remain equal |
| Lint/format/dependencies | Ruff passed, 79 Python files formatted, pip check passed |
| Benchmark | **360 measured serial requests**, 100/1,000/5,000 fixture orders, zero errors |

## Improvements made

- Rejected NUL in raw/persistent/buyer-audit/search text with the existing 422 format. This
  avoids PostgreSQL-incompatible data and inconsistent SQLite text behavior.
- Added local encoding-detector failure recovery: original input and deterministic fields
  remain, uncertainty is explicit, review/RED is required, private exception text is not logged.
- Added 300 explicit fictional corpus cases and four bounded deterministic Hypothesis
  invariants (up to 50 examples each). The corpus is a template regression suite, not a real
  customer or model quality evaluation.
- Added races for assignment, credential rotation, dispatch readiness, completion and rider
  availability; verified optimistic updates with two separate OS HTTP clients too.
- Added repeatable evaluation, temporary benchmark and isolated HTTP demo tools, redacted
  frontend sample responses and a local GitHub Actions workflow.

## Parser findings

On 270 valid corpus records, phone, township and COD fields each matched all 270 explicit
expectations, including appropriate null/ambiguity. Positive extractions: phone 240/240,
township 250/250, COD 190/190. Definite triage labels matched 260/260; ten short mixed-encoding
cases are explicitly uncertain and excluded. All 30 invalid inputs were rejected, valid
originals/provenance were preserved and all ten digit-normalization cases passed. No overall
AI or geospatial accuracy is claimed. Real model integration remains mock/disabled.

## Performance and database

At 5,000 fixture orders the final run measured median/p95 milliseconds: health 2.211/3.622,
Myanmar-digit rules parse 3.352/3.936, create 11.437/12.243, page list 29.878/32.026,
combined filter/search 61.354/68.453, correction/event 10.733/13.459, buyer verification
20.996/40.942 and one-stop rider queue 6.556/8.884. These are serial in-process SQLite
microbenchmarks, not production throughput or network capacity.

Fresh migrations, constraints, rollback, version conflicts, assignment uniqueness and reopen
persistence passed. Head remains 0003_rider_copilot. No table/migration/index change was made.
Real PostgreSQL execution and multi-worker server races remain unverified.

## Security and integration boundaries

No new access-control or duplicate-completion failure was reproduced. The known public-use
blocker remains production identity/tenant/role authorization and a reviewed HTTPS deployment.
Development tokens are loopback-only and must never enter public Vite/browser builds. Buyer
last-four plus link is a light check, not phone ownership proof. Order create lacks an
idempotency key, so reconcile uncertain creates before retrying.

Same-machine frontend integration with synthetic data is ready. The frontend source is
absent, so no browser/cross-application test was possible. A public demo with private order
data is **not currently safe**. Trusted geospatial data, paid model activation, messages,
masked calls, photos, routing and remittance remain absent/simulated as previously documented.

## Files changed in this session

Runtime: app/schemas/orders.py, management.py, buyer.py; app/parsing/normalization.py;
app/api/order_management.py. Tooling: scripts/build_audit_corpus.py, evaluate_parser.py,
benchmark_backend.py, verify_delivery_demo.py, verify_process_race.py. Tests:
tests/test_overnight_parser.py, test_overnight_concurrency.py and fixtures/delivery_corpus.json.
Also pyproject.toml, requirements-dev.lock, .github/workflows/backend-ci.yml, .gitignore,
backend/README.md, root README.md, docs/API_CONTRACT.md and docs/overnight_audit artifacts.

## Evidence and next phase

[Executive summary](overnight_audit/EXECUTIVE_SUMMARY.md),
[defects](overnight_audit/DEFECT_INVENTORY.md),
[test counts](overnight_audit/FINAL_TEST_RESULTS.md),
[parser evaluation](overnight_audit/PARSER_EVALUATION.md),
[performance](overnight_audit/PERFORMANCE_REPORT.md),
[security](overnight_audit/SECURITY_REVIEW.md),
[database integrity](overnight_audit/DATABASE_INTEGRITY.md),
[lifecycle scenarios](overnight_audit/LIFECYCLE_SIMULATIONS.md),
[concurrency](overnight_audit/CONCURRENCY_REPORT.md),
[engineering log](overnight_audit/ENGINEERING_LOG.md),
and [next steps](overnight_audit/NEXT_STEPS.md).

Next: import the existing frontend and test its real browser workflows locally; design
proper authentication and validate disposable PostgreSQL before a shared public demo.
