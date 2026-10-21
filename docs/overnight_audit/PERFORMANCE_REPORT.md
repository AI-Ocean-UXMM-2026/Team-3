# Local performance measurements

Measured with Windows 11, Python 3.14.7, temporary SQLite and in-process FastAPI TestClient. Each metric uses 15 serial requests at fixture sizes 100, 1,000 and 5,000. Data setup is bulk-seeded from a valid API-created template and is excluded from timing. Create requests add 15 orders to each fixture. The final table sizes are 115, 1,015 and 5,015.

Parsing uses rules mode and a Burmese-digit corpus message. Fixture loading is outside timing. Correction/event recording measures the complete correction transaction. Queue measurement has one active stop, not 5,000 rider stops. Buyer verification rotates one fixture credential with a test-only request limit.

| Fixture orders | Endpoint / operation | Median ms | p95 ms | Serial requests/sec | Errors |
| --- | --- | --- | --- | --- | --- |
| 100 | health | 2.225 | 3.332 | 430.16 | 0 |
| 100 | parse_rules | 3.445 | 24.211 | 205.93 | 0 |
| 100 | create_order | 11.47 | 12.393 | 87.58 | 0 |
| 100 | list_page | 7.679 | 11.054 | 125.36 | 0 |
| 100 | filter_search | 8.268 | 12.379 | 116.74 | 0 |
| 100 | correction_with_event | 10.777 | 12.325 | 90.99 | 0 |
| 100 | buyer_verify | 21.336 | 62.663 | 38.05 | 0 |
| 100 | rider_queue_one_active_stop | 6.535 | 9.824 | 144.46 | 0 |
| 1000 | health | 2.191 | 2.892 | 438.16 | 0 |
| 1000 | parse_rules | 3.485 | 4.664 | 272.05 | 0 |
| 1000 | create_order | 10.954 | 12.829 | 88.96 | 0 |
| 1000 | list_page | 12.768 | 15.126 | 78.22 | 0 |
| 1000 | filter_search | 18.999 | 22.02 | 50.9 | 0 |
| 1000 | correction_with_event | 10.694 | 12.756 | 91.78 | 0 |
| 1000 | buyer_verify | 21.539 | 40.14 | 44.38 | 0 |
| 1000 | rider_queue_one_active_stop | 6.693 | 9.235 | 146.39 | 0 |
| 5000 | health | 2.211 | 3.622 | 416.66 | 0 |
| 5000 | parse_rules | 3.352 | 3.936 | 290.68 | 0 |
| 5000 | create_order | 11.437 | 12.243 | 87.09 | 0 |
| 5000 | list_page | 29.878 | 32.026 | 33.6 | 0 |
| 5000 | filter_search | 61.354 | 68.453 | 16.14 | 0 |
| 5000 | correction_with_event | 10.733 | 13.459 | 91.32 | 0 |
| 5000 | buyer_verify | 20.996 | 40.942 | 44.64 | 0 |
| 5000 | rider_queue_one_active_stop | 6.556 | 8.884 | 147.01 | 0 |

**360 measured requests, zero errors.** p95 is the observed nearest-rank estimate from 15 samples and can be influenced by cold initialization. Serial request rate is not production concurrency capacity. No network latency, browser, public server, real PostgreSQL, hardware saturation or sustained load test is represented.

Search/list latency rises with table size. Inspection confirms SQL pagination is already applied; it does not load all orders before slicing. Leading-wildcard substring filters and unscoped global sort/count can scan data. No new index was justified without a product latency target and actual PostgreSQL plans. Existing merchant/status indexes were retained.

Raw aggregate evidence: [performance.json](performance.json). Repeat from backend with `python scripts/benchmark_backend.py`; it creates/disposes only its own temporary databases.
