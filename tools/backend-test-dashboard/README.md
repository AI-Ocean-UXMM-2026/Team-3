# Local backend test dashboard

This directory is a launcher, not the product frontend. From the repository root:

```powershell
.\tools\backend-test-dashboard\start.ps1
```

Open <http://127.0.0.1:8765>. Code and first-party assets are in
`backend/tools/backend_test_dashboard/`. See
[the testing guide](../../docs/LOCAL_BACKEND_TESTING_GUIDE.md) for isolation, security,
workflow details and limitations. No normal project database or browser-delivered private
token is used. Stop with Ctrl+C or the dashboard's Stop tool button.

Run the UI handler and real HTTP checks from the repository root:

```powershell
node --test tools/backend-test-dashboard/dashboard.test.cjs tools/backend-test-dashboard/dashboard-http.test.cjs
```

The HTTP suite starts and stops a separate temporary dashboard on an ephemeral loopback
port. It leaves the open dashboard at 8765 alone. Its DOM harness is not a visual browser.
See [the current end-to-end report](../../docs/CODEX_END_TO_END_TEST_REPORT.md).
