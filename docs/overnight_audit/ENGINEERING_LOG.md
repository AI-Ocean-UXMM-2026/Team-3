# Engineering log

- Inspected Git and preserved prior uncommitted Phase 8 docs, guide and configuration edits.
  Read routes, schemas, parser, access controls, models, lifecycle and existing failure tests.
- Reproduced accepted NUL text and traced the persistence/query incompatibility. Added 422
  safeguards and schema/API regressions, preserving ordinary whitespace/Unicode.
- Added deterministic synthetic corpus and bounded Hypothesis dependency/settings. Initial
  mixed-script triage mismatches were explicitly relabelled uncertain rather than weakening
  encoding safety. All core extraction expectations now pass.
- Added detector-failure recovery with private logging and an injected-failure regression.
- Added bounded assignment/session/readiness/completion/availability races. No new locking
  defect reproduced; existing version/transaction architecture retained.
- Ran two independent OS HTTP clients against the same version on one isolated API worker;
  200/409 and exactly one persistent correction confirmed optimistic conflict handling.
- Ran temporary SQLite benchmarks; corrected fixture-loading overhead outside timed calls
  and explicitly selected rules mode/one Myanmar-digit fixture for final measurements.
  The reported file contains the final measured run, not an claimed speed improvement.
- Reused LocalDemo in a stop-after-verification command. Its initial direct-script import
  was corrected; final 68-case run and reopen passed. Core demo was not rewritten.
- Prepared local CI; fixed lint/format findings in new tooling, installed only property-test
  dependencies, ran full 749-case regression and four Node checks, and wrote actual results.
