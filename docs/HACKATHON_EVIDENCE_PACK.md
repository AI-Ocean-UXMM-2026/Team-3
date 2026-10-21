# Hackathon evidence pack

This pack separates software evidence from fictional logistics outcomes. Executed
2026-10-21; details and commands are in the [simulation report](LOGISTICS_SIMULATION_REPORT.md).

## Defensible statements

| Evidence type | Supported statement | Limits |
| --- | --- | --- |
| Implemented APIs | Rules-first parsing, persistent orders, protected buyer verification, dispatcher approval, rider queues and COD delivery assertions work through existing routes | AI is mocked; development access is not production authentication |
| Automated tests | Current regression: 775 Python tests and 4 JavaScript tests passed; 26 Python cases added for the lab | Passing tests are not proof of production security or real-user usability |
| Synthetic scale | 100, 500, 1,000 and 5,000-order isolated databases were populated and reopened successfully | Only 24 selected delivery workflows per scale; remaining orders were backlog |
| Synthetic demo | 20 fictional orders produced 12 deliveries, one failure, one active assignment and six DRAFT orders | These are configured test outcomes, not courier success rates |
| Event integrity | Across all runs, 7,571 events persisted, 438 queue checks passed and 15,435 API calls had zero unexpected HTTP errors | Sequential local TestClient runs, not a public load or browser test |
| Parser regression | Known phone/township/COD labels matched on 270 valid synthetic records; 30 invalid records were correctly rejected | Template corpus, not a held-out Myanmar address study; real AI accuracy not measured |
| Timing | At 5,000 rows, parse median/p95 4.127/5.125 ms; create 11.939/14.141 ms; list 63.936/73.410 ms | Local Windows SQLite in-process timing, not production network latency |
| Financial assertion | Demo deliveries recorded 299,000 MMK expected COD and equal rider collection assertions | No actual money, settlement, remittance or payment processing |

## Safe pitch sequence

Run `python -m tools.logistics_lab --demo --workflow-limit 20` from the backend environment.
Use [demo report](logistics_lab/demo-20/report.md), `orders.csv` and sanitized `trace.jsonl`:

1. Explain the input is fictional Burmese chat text and parsing is deterministic plus mock AI.
2. Show an AMBER result and explicit missing/unverified reasons; RED examples remain visible.
3. Show a buyer link, last-four verification and a temporary buyer credential conceptually;
   keep actual credentials off slides/logs.
4. Show the initial artificial test pin entering dispatcher review, then explicit approval.
5. Show approved availability/time-window changes reflected in rider queue polling.
6. Show assignment, delivery start, rejected missing-COD completion and successful completion.
7. Show persisted event history after database reopen and the deliberately failed delivery.

The batch lab has no UI/server session. Use the pre-existing local interactive demo tool
if presenting a browser, and label it according to its actual mode. Do not imply this task
tested the teammate's absent frontend. Do not display a fabricated 99% confidence or call
an initial buyer pin independently verified. Default operational GREEN count is zero;
the separate injected synthetic catalog is a logic test only.

## Claims requiring real-world validation

The manual-versus-LannPya comparison is a configurable analytical assumption model.
Its default modeled cost difference of 189.25 MMK/order is not observed ROI. The 32-case
sensitivity table includes unfavorable cases. Collect consented time-and-motion,
delivery-attempt, confirmation-uptake and cost data before making improvement claims.

Do not claim live Messenger/Viber delivery, masked calling, gate-photo verification,
geographic route optimization, automatic push updates, geocoding, settlement or model
accuracy. These were not implemented/evaluated here. Hub metadata is not operational hub
management, and future windows do not establish on-time delivery performance.

## Readiness and next phase

The backend is ready for controlled local integration and a clearly labeled synthetic
demonstration. An unrestricted public privileged demo is not safe under the existing
development-token mechanism. Keep tokens out of browser-delivered code. Before public
use: implement proper authenticated roles or a secure server-side integration boundary,
verify PostgreSQL/migrations, review deployment security and validate location data policy.
Real frontend/browser integration, trusted geospatial evidence and any real AI activation
remain separate work. No push or deployment was performed.
