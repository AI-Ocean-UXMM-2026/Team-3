# Functional implementation coverage

Current update — 21 October 2026, v0.6: only Admin, Customer and Rider operate the app. Manual admin creation, an empty one-time-reset workspace, dedicated customer landing/links, customer first-pin submission with admin approval, live-clock defaults and Any time manual orders are implemented. README.md and FUNCTIONAL_REVIEW.md supersede the earlier merchant, legacy migration and fixed demo-clock references below. Active checks now cover the fresh three-role flow as well as the retained delivery/closeout rules.

Updated 20 October 2026 after implementation of the missing local workflows. The previous gap audit has been superseded by the active application in `workflow-domain.js` and `functional-app.js`.

This records functional prototype coverage, not production readiness. The supplied PRD and images still define product intent; [PRODUCT_FUNCTIONAL_OUTLINE.md](PRODUCT_FUNCTIONAL_OUTLINE.md) contains the detailed rule and screen baseline.

## Completed local increments

| Increment | Implemented behavior |
| --- | --- |
| F1 Shared lifecycle | Separate triage, location/confirmation, custody/lifecycle, assignment, link, collection, cash handover and pending-action states; version/operation identity; actor guards; legacy preservation |
| F2 Admin intake/review | Paste/preview, progressive extraction, source evidence, duplicates, partial failure/cancellation/retry, retained drafts, inline corrections, receipt, assignment and board filters |
| F3 Customer contracts | Per-order links/gates, lock/reissue/revoke/expiry, radius/township rules, deadline freeze, future windows, explicit response, COD/security rule and stale-form recovery |
| F4 Rider/closeout | Departed assignments, active stop, real navigation/optional speech, two-second undo, COD mismatch reason, attempts/retry limits, return receipt, cash handover/dispute and closure gates |
| F5 Recovery/review | Scenario clock, slow/failed saves, partial parser failure, map/GPS/voice fallbacks, offline preparation/replay/conflicts, named role denial, backup, form drafts and controller tests |

## Screen requirements

| Outline IDs | Current local functionality | Remaining external/verification boundary |
| --- | --- | --- |
| A01–A02 | Multi-order capture/preview, per-record progress and retry, explicit duplicate decisions, manual encoding review | Robust automatic Zawgyi conversion, broader free-text parsing and optional AI provider; sample/fixture output is labelled |
| A03–A04 | Search/filter counts, correction/re-triage, original text/highlights, field sources and before/after audit | Device usability, accessibility and performance review |
| A05 | Per-order opaque demo link, copy/manual-share distinction, expiry/revoke/reissue/lockout and local cooldown | Server token/session security and actual external notifications |
| A06–A07 | Physical receipt, draft route/rider assignment, unassignment, route readiness/departure and active stop | Actual accounts/permissions and cross-device coordination; operational reassignment during an offline handoff needs backend conflict integration |
| A08–A09 | Exceptions, incidents, return receipt, discrepancy review, cash declaration/receipt/dispute and closure | Real custody/cash operating procedures and server-authoritative audit |
| A10 | Versioned local coverage/cutoff/retry/link policy and demo clock | Real supported geography, capacity, retention and pilot operating defaults |
| C01–C02 | Public-safe projection, own-order phone gate, malformed/wrong/locked recovery | Backend must enforce these projections and limits; local code/storage is inspectable |
| C03–C05 | Fixed-anchor diagram/nudges/reset, approximate township bounds, future window/response/note and explicit confirmation | Verified coordinates/boundaries, interactive map provider and real GPS permission handling |
| C06–C08 | Cutoff/departure freeze, terminal/retry state, invalid/revoked/expired/locked recovery, retained/refreshable draft | Server clock/expiry, actual reconnect acknowledgement and production session policy |
| R01–R03 | Assigned queue, current stop stability, latest buyer preference, actual Maps URL and optional browser speech | Real update delivery/voice availability and device review |
| R04–R05 | Exact undo timer before submission, incomplete cancellation, actual COD/prepaid validation, discrepancy reason, recoverable unsubmitted amount draft | Real server acknowledgement/idempotency; browser restart/interaction verification |
| R06–R07 | Retained attempts, future retry/limit, return pending/received, later cycles, history/cash handover and closure | Real physical hub verification and operational user testing |
| R08 | Prepared local queue, persistent pending payload, acknowledgement/conflict simulation, original observer/reviewer and static-shell worker | Actual HTTP offline restart and cross-device/server replay/concurrency tests |
| Shared roles | Named preview actors and scope/command denial | Authenticated users and tenant isolation in backend phase |

## Acceptance coverage

The 40 outline scenarios remain the acceptance baseline. Automated domain/controller tests cover the local business rules and handlers; they are not forty certified production or browser tests.

- Intake, triage, manual correction, duplicates and partial import: domain and controller tests.
- Public projection, lockout, reissue/expiry, geographic bounds, deadline, security/COD and stale writes: domain and controller tests.
- Receipt/assignment/departure, stable stop, undo, cash result, retries, cancellation, return receipt, handover and closure: domain and controller tests.
- Offline preparation, persistence, repeated replay, generic stale-version conflict and dispatcher review: domain and controller tests.
- Real model/encoding/map providers, multi-device races/reassignment, actual browser voice/navigation, HTTP worker lifecycle, mobile layout/accessibility and performance: integration/device verification remains, explicitly not claimed as passed.

## Next gates

1. Walk the implemented happy/failure/offline paths in [FUNCTIONAL_REVIEW.md](FUNCTIONAL_REVIEW.md). Resolve functional defects found during that review.
2. Refine UI/UX and verify real browser/device states, Burmese copy and accessibility.
3. Implement authenticated backend, persistence, real token/security rules, providers and acknowledged cross-device/offline synchronization. Confirm actual courier policies and retention before live data.

CSV import, masked calls, SMS/Viber sending, native apps, pickups, fleet optimization and payment integrations remain outside the core MVP as specified in the outline. No external deployment, messaging or backend was added in this increment.
