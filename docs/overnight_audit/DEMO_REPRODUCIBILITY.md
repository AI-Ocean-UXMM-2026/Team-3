# Repeatable real-HTTP demonstration

From backend in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\verify_delivery_demo.py
```

The wrapper reuses the established LocalDemo engine, creates a new UUID-specific ignored
SQLite database, migrates/seeds fictional merchant/dispatcher/rider, starts three loopback
role processes, verifies 68 HTTP cases, stops servers and reopens storage. It returns a
clear pass or nonzero failure and always invokes cleanup. No normal `.env`/database reset,
public bind, messaging provider, paid AI or production database is used.

Observed persisted result: 5 orders, 3 buyer requests, 3 assignments, 4 rider action receipts,
32 delivery events and 3 confirmation links. Success includes parse/create, buyer challenge,
initial pin proposal, dispatcher approval, availability, rider queue/start, COD guard and
completion; separate review/rejection/rescheduling/failure and access/CORS checks also run.

Safe aggregate output is [demo_results.json](demo_results.json); redacted actual responses
are [frontend_samples.json](frontend_samples.json). Tokens and complete phone fixture
representations are replaced before writing shareable samples. Existing Phase 7 response
files are preserved. Fixture (0,0) pin is explicitly synthetic, never a verified Myanmar
customer location or automatic GREEN proof.

Earlier `scripts/demo_mvp.py --serve` still supports local frontend development. This new
command is the stop-after-verification wrapper and does not replace its implementation.
