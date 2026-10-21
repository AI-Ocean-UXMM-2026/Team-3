# Final test results

| Check | Actual outcome |
| --- | --- |
| Full Python regression | **749 passed in 53.69 seconds**, 0 failures/errors/skips |
| New tests | **323**: 317 parser/property/validation cases plus 6 concurrency/search cases |
| Existing cases retained | 426, including Phase 8B contract tests |
| Final corpus alias/abbreviation refinement | Affected parser suite rerun: **317 passed in 2.66s** |
| Synthetic corpus | 300 records, 270 valid + 30 rejected; 10 encoding-uncertain confidence labels excluded |
| JavaScript helper | 4 passed, 0 failed/skipped |
| Real HTTP demo | 68 cases passed; storage reopened after server shutdown |
| Lint/format | Ruff passed; 79 Python files formatted |
| Dependencies | pip check: no broken requirements |
| OpenAPI | 29 operations; existing schema snapshots unchanged/equal |
| Benchmark | 360 measured serial requests over 3 fixture sizes; 0 request errors |
| Two OS clients | Same-version HTTP race returned 200/409; version/event consistency persisted |

Machine-readable module counts/timing: [test_results.json](test_results.json). Pytest JUnit
suite timing excludes some runner overhead, so it differs slightly from console elapsed
time. Hypothesis examples are not counted as additional Pytest tests.

No actual frontend/browser, remote laptop, hosted CI, real PostgreSQL, paid AI, courier
integration, messaging or trusted geospatial verification was executed.
