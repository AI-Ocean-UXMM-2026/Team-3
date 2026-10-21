# CI preparation and dependencies

Prepared `.github/workflows/backend-ci.yml` locally. It runs on backend/docs pull requests
or manual dispatch, uses read-only repository permission and a 15-minute timeout, installs
pinned `requirements-dev.lock` plus the project, then executes pip check, Ruff lint/format,
the full Pytest suite (including isolated migrations/property/contract cases), and four
Node helper tests. A failed job uploads JUnit output for seven days. No production secret,
paid service, PostgreSQL account or cloud resource is required.

The equivalent Python, Node, lint, formatting and dependency commands passed locally on
Windows/Python 3.14.7. The workflow targets Ubuntu/Python 3.14/Node 22 and has not been pushed
or run by GitHub; hosted runner/action availability and Linux execution remain unverified.
No separate redundant test job was added.

Added only Hypothesis 6.170.5 and sortedcontainers 2.4.0 for bounded property tests, with
matching dev declaration/pins. Existing runtime dependencies were not upgraded. `pip check`
found no broken requirements. No dependency advisory database scan was performed, so
vulnerability status is not established by compatibility checks. `.hypothesis/` and JUnit
temporary output are ignored.
