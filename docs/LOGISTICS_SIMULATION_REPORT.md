# Logistics simulation and evaluation

Executed locally on 2026-10-21. All logistics data and outcomes are synthetic. This is
engineering evidence, not measured Myanmar courier performance, customer research or ROI.

## Assessment and implementation

The overnight audit, API contract, existing fixtures and buyer/rider tests were reviewed
first. The existing 300-record corpus and regression tests were reused. The remaining gap
was configurable multi-order experimentation with event-derived analytics and exportable
assumption comparisons; see [gap analysis](logistics_lab/GAP_ANALYSIS.md).

The isolated `backend/tools/logistics_lab/` package adds configuration, seeded plans,
real application API orchestration, event analytics, exact COD totals, parser evaluation,
comparison sensitivity and JSON/CSV/Markdown reporting. No application modules, migrations,
public endpoints or frontend files were changed by this task. There are 29 existing OpenAPI
operations. No confirmed application defect required a production-code fix.

Each run creates a new temporary SQLite database, applies existing Alembic migrations,
creates fictional merchants and actor-bound riders, and exercises actual FastAPI routes
through TestClient. Protected calls use the existing loopback development controls; public
buyer calls use separate clients and normal verification/rate-limit policies. Random
credentials stay in memory. The database is reopened to assert persistent orders/events,
then disposed and removed. No configurable input database can target developer records.

Hub labels are experiment metadata, not persistent courier hubs. Shared riders are assigned
round-robin, not by geography or hub boundaries. Plans share a seed-stable prefix across
volumes. UUIDs, tokens, timestamps, next-day delivery windows and timings are not seeded.

## Execution and configuration

See [commands, configuration and exports](logistics_lab/README.md). From `backend`:

```powershell
.\.venv\Scripts\python.exe -m tools.logistics_lab --orders 100 500 1000 5000 --workflow-limit 24
.\.venv\Scripts\python.exe -m tools.logistics_lab --demo --workflow-limit 20
.\.venv\Scripts\python.exe -m pytest -q tests/test_logistics_lab.py
```

Defaults: seed 20261021, three merchants, two nominal hubs, six riders, batches of 100,
15 paginated/filter read samples, confirmation probability 0.65 and failure probability
0.20. These probabilities are assumed scenario inputs. Every requested order is ingested;
only the configured number of eligible orders exercises the expensive delivery workflow.
The remaining orders deliberately stay in the backlog. `--output` selects report storage.
Latest `run_status.json` is authoritative, including after a previous failed experiment.

## Executed outcomes

| Ingested | Initial AMBER | Initial RED | Workflows | Delivered | Failed | Events |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 72 | 28 | 24 | 18 | 6 | 308 |
| 500 | 351 | 149 | 24 | 18 | 6 | 708 |
| 1,000 | 706 | 294 | 24 | 18 | 6 | 1,208 |
| 5,000 | 3,382 | 1,618 | 24 | 18 | 6 | 5,208 |
| Demo: 20 | 14 | 6 | 14 | 12 | 1 | 139 |

Totals: 6,620 orders ingested, 110 selected workflows, 84 delivered, 25 failed, one still
assigned and 6,510 DRAFT backlog orders. There were 7,571 persisted events, 438 queue
consistency assertions and 15,435 API calls, with zero unexpected HTTP errors. Three
intentional demo rejections checked revoked links, duplicate assignment and missing COD
confirmation. The same selected prefix explains identical scale-run delivery outcomes;
this does not model congestion or prove outcomes improve with volume.

The polished 20-order demo uses fictional Burmese clothing merchants and three riders.
It includes missing/invalid addresses, prepaid/COD, two explicitly duplicated inputs,
pin confirmation, two approved reschedules, one failed delivery and one active assignment.
It created 13 links, verified 12 buyers and persisted 12 completions. Two initial pins
required dispatcher approval. Test coordinates `(0, 0)` are labeled artificial inputs,
not customer homes or evidence of township accuracy. All operational cases remain AMBER
or RED. A separate synthetic catalog checks the GREEN logic branch without claiming
independently verified geography. Thus there is no misleading live GREEN demo order.

## Metric definitions

- Initial classification counts use actual saved parser results. AMBER means sufficient
  phone/township for review, not a geospatially valid address. GREEN is zero by default.
- Confirmation requests count persisted link events; successful challenges count distinct
  verified orders. Buyer action requests, reviews and approved reschedules use persisted
  actions/events, not random plan flags.
- Assignments and completions use database assignment records and delivery events; final
  success/failure counts use canonical order status. Queue checks compare returned active
  deliveries and unchanged-cursor responses against persistent assignments.
- Manual-intervention executed orders and review events measure actual lab actions.
  `manual_review_flagged_orders` remains all orders under the current conservative policy;
  it is not evidence that manual work has been eliminated.
- COD sums use Decimal and explicit delivery collection assertions. Each scale run has
  358,000 MMK asserted against delivered expected COD; demo has 299,000 MMK, with zero
  unasserted delivered COD. This is not settlement, banking or financial reconciliation.
- Average ingestion API time is summed parse/create durations divided by orders. Per-stage
  latency uses observed durations, median and nearest-rank p95. It excludes setup and
  does not represent merchant labor or wall-clock parcel transit.

CSV `confirm`/`fail` values are plan flags, not observed completion states. Duplicate
messages intentionally remain separate orders: no new idempotency contract was invented.

## Parser benchmark

The existing labeled synthetic corpus contains 300 records: 270 valid requests and 30
correct input rejections. Known-label results:

| Field | True positive | True negative | False positive | False negative | Precision / recall |
| --- | ---: | ---: | ---: | ---: | --- |
| Phone | 240 | 30 | 0 | 0 | 1.0 / 1.0 |
| Township | 250 | 20 | 0 | 0 | 1.0 / 1.0 |
| COD | 190 | 80 | 0 | 0 | 1.0 / 1.0 |

All 260 known triage labels matched; ten unknown triage labels were excluded. Original
input and provenance checks passed on 270 cases; Burmese digit checks passed 10/10.
Malformed surrogate JSON was rejected. There were no categorized mismatches in this
template corpus. Precision is TP/(TP+FP), recall TP/(TP+FN), error rate mismatched
field cases/labeled cases; undefined denominators return null. A wrong non-null prediction
counts both FP and FN. AI and geospatial accuracy are explicitly null. These are regression
scores on synthetic templates, not representative accuracy estimates or a held-out trial.
See [machine-readable benchmark](logistics_lab/parser_benchmark.json).

## Baseline comparison and sensitivity

The baseline is an analytical manual-workflow model, not an implemented manual courier
service. Defaults assume failure rates 0.15 baseline/unconfirmed, 0.08 confirmed, uptake
0.65, processing 120 seconds baseline/45 seconds LannPya, 60 seconds per confirmation,
labor 3,000 MMK/hour and failed-attempt cost 3,500 MMK. None were empirically measured.

For N orders and uptake q: model failure rate is `(1-q)*unconfirmed + q*confirmed`;
baseline seconds are `N*manual_seconds`, model seconds `N*(processing+q*confirmation_seconds)`.
Cost is `seconds/3600*labor + expected_failures*failure_cost`; reported difference is
baseline minus model cost. Defaults yield an assumed 189.25 MMK difference per order.
This is an assumption calculation, not observed savings or a causal effect.

Each export includes 32 sensitivity cases varying baseline/confirmed failure rates,
confirmation uptake, processing cost and failure cost. Both favorable and unfavorable
results occur. The confirmation model is distinct from the simulator's selected realized
success/failure events; do not combine their denominators or call either real-world ROI.

## Performance

Windows 11 build 26200; Python 3.14.7; Intel Core i5-10300H, four cores/eight logical
processors; 15.8 GiB RAM; local temporary SQLite; synchronous TestClient transport.
No public service was loaded. This is sequential in-process performance, not network
throughput, PostgreSQL scalability, disk-only throughput or a sustained concurrency test.
Read stages have 15 samples per volume; verification has 18; queue reads have 48.

| Orders | Parse median/p95 ms | Create median/p95 ms | List median/p95 ms | Filter median/p95 ms |
| ---: | --- | --- | --- | --- |
| 100 | 3.966 / 5.425 | 11.132 / 13.427 | 8.576 / 10.913 | 8.242 / 9.751 |
| 500 | 3.883 / 4.733 | 11.290 / 13.039 | 12.948 / 17.104 | 11.152 / 14.089 |
| 1,000 | 3.978 / 4.745 | 11.641 / 13.283 | 19.623 / 21.138 | 16.650 / 17.647 |
| 5,000 | 4.127 / 5.125 | 11.939 / 14.141 | 63.936 / 73.410 | 48.574 / 54.060 |

At 5,000 orders, queue median/p95 was 6.835/87.402 ms; verification 23.827/25.850 ms;
status updates 12.574/14.721 ms. The queue tail deserves measurement under a real server
and PostgreSQL before optimization. Creation/status timing includes transaction and
application work; it is only a database-write proxy. Full timing tables are in each run.
Read growth is visible; there was no measured need to change application indexes here.

## Tests, adversity and integrity

The complete current regression run passed **775 Python tests**, including **26 new lab
cases**, in 59.37 seconds. Four JavaScript adapter tests passed. Ruff lint and formatting
passed (90 Python files); `pip check` reported no broken requirements. New cases cover
determinism, bounds, empty datasets, exact arithmetic, export schemas, privacy, failure
isolation, model outcomes, parser labels and API-driven demo events. An injected database
OperationalError produced a safe failure; normal local configuration/database hashes
remained unchanged, and a subsequent isolated run succeeded.

Existing regression tests were reused for concurrent buyer verification/assignment,
expiry/lockout, unauthorized mutation, transaction rollback, invalid coordinates,
unavailable AI, protected deterministic fields and rider queue ordering. They were rerun,
not reimplemented. Scale ingestion is batched sequentially; it is not a 5,000-concurrent
request test. No new claim of production multi-process or PostgreSQL race safety is made.
Migrations ran on every isolated simulation and persistence was verified after reopening.

The demo checks rescheduling with explicit reviews, link replacement, duplicate assignment,
missing COD acknowledgment, approved pin propagation and unchanged-cursor polling. Other
adversarial behavior remains covered by the existing full regression suite. This task did
not rerun the historical standalone 68-case network HTTP suite or a browser application;
all new scale/demo API calls were in-process. No actual frontend source was available.

## Artifacts, boundaries and next work

Run directories [100](logistics_lab/orders-100/report.md),
[500](logistics_lab/orders-500/report.md), [1,000](logistics_lab/orders-1000/report.md),
[5,000](logistics_lab/orders-5000/report.md), and [demo](logistics_lab/demo-20/report.md)
contain JSON/CSV/Markdown plus sanitized execution traces and authoritative manifests.
See [test results](logistics_lab/test_results.json) and
[hackathon evidence pack](HACKATHON_EVIDENCE_PACK.md).

No secrets, raw customer messages, phone challenges or capability URLs are exported.
Existing uncommitted Phase 8/overnight changes were preserved. No frontend modifications,
new dependencies, external paid calls, pushes, deployments or production data changes.

Production authentication/authorization, PostgreSQL verification, trusted geospatial
evidence and real frontend integration remain blockers. Real AI remains mocked.
The simulation has no travel clock, congestion, geographic route optimizer, hub-specific
policies, customer behavior calibration, payment settlement or live messaging. Delivery
windows test persistence/priority, not arrival compliance. Recommended next work is a
secure frontend integration against the documented contract, followed by PostgreSQL
verification and a consented, labeled field pilot to calibrate assumptions. Production
authentication must precede public privileged access.
