# Lifecycle simulation evidence

All referenced tests ran successfully in the full suite. They exercise TestClient API
responses, isolated DB state/events and access conditions; the separate real-HTTP demo
covers the complete merchant/buyer/dispatcher/rider success/failure workflow.

| Required scenario | Executed test evidence |
| --- | --- |
| 1. Successful COD delivery | `test_delivery_cod_idempotence_events_and_view_only_link`; HTTP demo |
| 2. Ambiguous address and buyer review | `test_initial_pin_requires_ack_and_dispatcher_approval` |
| 3. Invalid phone -> RED | `test_invalid_phone_is_red`; 10 invalid-phone corpus rows |
| 4. Reschedule before dispatch | `test_supported_reschedule_and_leave_with_security`; unsupported request review in HTTP demo |
| 5. Buyer location after dispatch | `test_closed_order_never_accepts_buyer_changes`; no canonical mutation |
| 6. Cross-township request | `test_cross_township_review_and_repeated_decision`; synthetic test boundaries only |
| 7. Rider failure | `test_failure_requires_reason_and_records_private_note`; HTTP demo |
| 8. Duplicate completion | Existing same-UUID parallel test; new distinct-UUID race gives 200/404 and one event |
| 9. Link expired | `test_invalid_expired_revoked_and_replaced_links` |
| 10. Three failures lock link | `test_three_failed_attempts_lock_all_sessions`, concurrent limit test |
| 11. Assigned rider unavailable | New OFFLINE/start-denied test: stop remains assigned, start returns 409 |
| 12. Multiple riders act/assign | Existing rider-scope denial and new different-rider assignment race |
| 13. Dispatcher rejects pin | `test_review_rejection_scope_and_stale_version`; HTTP demo rejection |
| 14. AI fails parsing | `test_order_creation_survives_ai_failure`; hybrid timeout/malformed/rate/error tests |
| 15. Malformed customer input | Existing schema/API malformed tests plus 30 corpus rejections and NUL API regression |

No rule was bypassed to manufacture successful delivery. Confidence stays AMBER/RED without
trusted geospatial data. COD assertion records collection intent, not payment/remittance.
