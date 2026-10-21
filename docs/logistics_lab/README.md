# Local logistics lab

All results here are fictional local experiments, not Myanmar courier statistics or ROI.
See [the main report](../LOGISTICS_SIMULATION_REPORT.md) and
[hackathon evidence pack](../HACKATHON_EVIDENCE_PACK.md).

From `backend` in PowerShell, using the existing installed development environment:

```powershell
.\.venv\Scripts\python.exe -m tools.logistics_lab --demo --workflow-limit 20
.\.venv\Scripts\python.exe -m tools.logistics_lab --orders 100 500 1000 5000 --workflow-limit 24
.\.venv\Scripts\python.exe -m pytest -q tests/test_logistics_lab.py
```

The command always creates new temporary SQLite databases, applies Alembic migrations,
seeds fictional actors and exercises real FastAPI routes through TestClient. It checks
reopened persistence before automatic cleanup. There is no input database URL and no server
bind, tunnel, paid provider or public deployment. `--output` chooses reports, never a DB.

Each `orders-N/` or `demo-20/` directory contains:

- `run_status.json`: authoritative success/failure for the latest export.
- `report.json`, `report.md`: configuration, actual analytics, timing, comparison and limitations.
- `orders.csv`: every ingested order's stable lab reference, scenario, initial confidence,
  final status, COD amount and duplicate relationship; no customer/raw/credential fields.
- `metrics.csv`: metric/value rows; nested values are JSON encoded in CSV cells.
- `sensitivity.csv`: 32 fully labeled assumption-model cases, including unfavorable outcomes.
- `trace.jsonl`: first five ingestion pairs and selected workflow actions, with safe result
  fields only. Repeated reads and other ingestion calls are counted but omitted from trace.

`parser_benchmark.json` reuses the overnight corpus and adds precision, recall, error and
missing-information counts. A separately labeled synthetic catalog checks GREEN rule logic;
it is not a real location dataset, and no ordinary simulated order is automatically GREEN.

Report exports overwrite these generated filenames on repeat runs. A previous `failure.json`
may remain as diagnostic history; always use `run_status.json` before reading current results.
Use a distinct `--output` directory when preserving an earlier experiment. Do not run two
writers against the same report directory concurrently.

Plans and business outcomes are seed-reproducible. Actual backend UUIDs, cryptographic tokens,
timestamps, next-day windows, rate-limit buckets and performance timings are not seeded.
No phone challenge, raw message, bearer/development token or database path is exported.

The CSV `confirm` and `fail` columns describe planned scenarios; use `status` and report
metrics for observed results. Hub affiliations are sidecar labels: the shared rider pool
is assigned round-robin, without hub-constrained dispatch or geographic routing.
Delivery windows test persistence and queue priority, not simulated travel or on-time arrival.

For additional configuration, call the same tool from Python inside `backend`:

```python
from pathlib import Path
from tools.logistics_lab.config import SimulationConfig
from tools.logistics_lab.runner import simulate
from tools.logistics_lab.reporting import export_report

config = SimulationConfig(orders=100, merchants=2, hubs=1, riders=3,
                          batch_size=50, workflow_limit=30,
                          confirmation_rate=0.8, delivery_failure_rate=0.1)
export_report(simulate(config), Path('../docs/logistics_lab/custom'))
```

Configuration is bounded and rejects unknown fields. `orders` supports 0–5,000,
`workflow_limit` 0–5,000, merchants 1–20, hubs 1–10, riders 1–40, batch size 1–250,
and read samples 5–50. Larger workflow selections cost more local execution time.
Rates must be finite numbers between zero and one. The default seed is 20261021.

For interactive frontend development, the pre-existing `scripts/demo_mvp.py --serve` remains
available. This lab is a batch verification/evaluation tool and does not create a frontend.
