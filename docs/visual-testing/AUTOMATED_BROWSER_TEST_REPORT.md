# Automated Chromium verification

Executed 2026-10-21 in `integration/lannpya-final`, integration worktree only.

**Real headless Chromium 156.0.8078.4 launched and interacted with the website.**
Playwright Test 1.64.1 ran 28 cases: **28 passed, 0 failed, 0 skipped, 0 retries**,
132.47 seconds in the final complete run. These are rendered-browser interactions,
not the project's earlier lightweight DOM harness. No paid AI calls or deployment occurred.

| Final check | Observed result |
| --- | --- |
| Chromium | 28 passed |
| Python regression | 842 passed, 95.99s; baseline before changes: 839 passed |
| Node frontend / dashboard / HTTP integration | 96 + 17 + 1 = 114 passed; baseline: 112 |
| TypeScript parser | 141 passed, nine files |
| TypeScript type-check | Passed |
| Python Ruff lint / formatting | Passed; 102 files formatted |
| Frontend production build | Passed; 21 validated static assets |
| Dependency consistency | `pip check` clean; root `npm ls --depth=0` clean |
| Git whitespace check | Passed |
| Screenshots | 64 PNGs in `screenshots/` |

New coverage: 28 browser cases, three parameterized Python cases, two Node regressions.
Totals are separate framework counts; Node includes reported parent/subtests and is not
a count of distinct user journeys. Earlier failing runs were used to construct the browser
harness and reproduce the four defects; they are not counted as final passing runs.

## Reproduce

From the integration repository in PowerShell:

```powershell
npm.cmd run test:browser
node scripts/summarize_browser_tests.cjs
```

Dependencies and Chromium are already installed locally. On a clean checkout run
`npm.cmd ci` and `npx.cmd playwright install chromium` first, using the existing Python
environment/`LANNPYA_PYTHON` described in `../final-integration/LOCAL_STARTUP_GUIDE.md`.
No manually running backend or fixed browser-test port is required.

`playwright.config.cjs` uses one Chromium worker and fresh browser contexts. Every case
launches a separate loopback FastAPI process on an ephemeral port with `--temporary`.
Each owns a migrated temporary SQLite database, fictional actors and mock AI. The fixture
uses authenticated graceful shutdown and releases the temporary database afterwards.
It never points tests at the regular database or the saved port-8780 workspace.

`BROWSER_OBSERVATIONS.json` contains the final test outcomes, sanitized request/status
observations and screenshot dimensions. Raw Playwright results stay ignored under
`test-results/`; traces/video are disabled. Buyer link fields are masked in screenshots.
No request bodies, cookies, authorization values or CSRF values are exported.

## Runtime and scope

The existing site at http://127.0.0.1:8780 was initially checked without writes. After
verification it was gracefully restarted to load the parser fix, using its existing
isolated persistent workspace. SHA-256 of the SQLite logical dump matched before/after;
existing saved records were preserved. A parse request confirmed the corrected COD on
the restarted process. Browser tests themselves used disposable instances of this same app.
Existing open browser sessions may need to reconnect/reverify after this restart.

Local frontend/backend integration and the full delivery journey pass. Public deployment
remains blocked by missing production authentication/authorization and the other limits
in `REMAINING_ISSUES.md`. This is local hackathon evidence, not production certification.
