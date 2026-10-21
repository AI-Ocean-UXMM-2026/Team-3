# Confirmed defects and minimal fixes

| Defect | Impact / root cause | Fix and regression |
| --- | --- | --- |
| Stale parsed fields/payment | Parser UI updated only non-null fields; a later RED message retained an earlier phone/township and prepaid choice | Clear missing extracted values on each explicit parse; recalculate payment choice. Browser second-message case and Node regression pass. |
| Phone immediately before COD hides amount | Reverse amount-before-COD pattern treated the preceding phone as another invalid payment candidate, nulling a valid forward amount | Ignore phone-overlapping candidates only for the reverse rule. Keep forward phone-as-COD invalid and unmatched labels unresolved. Three parameterized Python cases (0/12500/25000) failed before and pass after; browser missing-township/COD case passes. |
| Save notice disappears | Initial loading render consumed the queued notice before final data render | Preserve notice during loading. Focused Node regression failed before and passed after; all responsive rider-save and live workflows pass. |
| Prototype CSP console error | Browser-only prototype imported Google Fonts despite existing self-only style CSP | Remove blocked external links, retain local font fallback. Prototype browser regression and final complete suite pass. |

Application edits: `backend/app/parsing/rules.py`, `frontend/api-workspace.mjs`,
`frontend/prototype.html`. No endpoint, response schema, migration, authentication rule,
selected framework or layout was replaced. The original repository and other branches
were not edited. Source fixes remain local and uncommitted on the integration branch.

Testing infrastructure: exact Playwright dev dependency and root lockfile, config,
`tests/browser/fixtures.cjs`, `tests/browser/website.spec.cjs`, safe observation exporter,
package test command and ignored raw browser artifacts. Existing Python/Node test files
contain the additional focused regressions. Reports/screenshots are under this directory.

Early harness failures were also corrected: open the optional parser disclosure, await
actual response JSON/newly rendered forms, allow the legitimate `not_requested` AI status,
and compare numeric navigation destinations rather than Decimal string formatting.
Those were test assumptions/timing mistakes, not additional product defects. No failing
test was deleted or disabled. The final full run has no failures, skips or retries.
