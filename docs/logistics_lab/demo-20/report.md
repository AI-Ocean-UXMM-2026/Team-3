# Synthetic logistics run

Fictional experiment, not courier outcome/ROI evidence.

## Configuration

```json
{
  "orders": 20,
  "seed": 20261021,
  "merchants": 1,
  "hubs": 1,
  "riders": 3,
  "batch_size": 100,
  "read_samples": 15,
  "workflow_limit": 20,
  "confirmation_rate": 0.65,
  "delivery_failure_rate": 0.2,
  "demo": true
}
```

## Observed API/DB results

```json
{
  "total_orders": 20,
  "initial_confidence": {
    "AMBER": 14,
    "RED": 6
  },
  "phone_township_valid_for_review": 14,
  "ambiguous_or_unverified_addresses": 14,
  "invalid_addresses": 6,
  "delivery_status": {
    "DELIVERED": 12,
    "FAILED": 1,
    "ASSIGNED": 1,
    "DRAFT": 6
  },
  "confirmation_links_created": 13,
  "phone_challenges_verified_orders": 12,
  "buyer_action_requests": 18,
  "successful_buyer_action_orders": 12,
  "rescheduling_requested_orders": 2,
  "approved_rescheduling_orders": 2,
  "orders_with_delivery_window": 2,
  "dispatcher_review_events": 6,
  "manual_intervention_executed_orders": 4,
  "manual_review_flagged_orders": 20,
  "rider_assignments": 14,
  "completed_assignments": 12,
  "delivered": 12,
  "failed": 1,
  "cod": {
    "delivered_expected_mmk": "299000",
    "collection_asserted_mmk": "299000",
    "unasserted_delivered_mmk": "0",
    "state": "ASSERTIONS_ONLY_NOT_FINANCIAL_RECONCILIATION"
  },
  "queue_consistency_checks": 54,
  "events": {
    "ORDER_CREATED": 20,
    "STATUS_CHANGED": 30,
    "BUYER_LINK_CREATED": 13,
    "BUYER_SECURITY": 12,
    "BUYER_LOCATION": 2,
    "BUYER_REQUEST_REVIEWED": 6,
    "BUYER_RESPONSE": 16,
    "RIDER_ASSIGNED": 14,
    "DELIVERY_STARTED": 13,
    "DELIVERY_COMPLETED": 12,
    "DELIVERY_FAILED": 1
  },
  "total_events": 139,
  "workflow_orders_exercised": 14,
  "http_calls": 327,
  "unexpected_http_errors": 0,
  "expected_rejection_calls": 3,
  "duplicate_input_orders": 2,
  "confirmed_window_queue_observations": 2,
  "average_ingestion_api_ms": 18.87925999926665
}
```

## In-process API timing

| Operation | Samples | Median ms | p95 ms |
| --- | --- | --- | --- |
| rider_create | 3 | 10.615 | 92.067 |
| parse | 20 | 4.167 | 6.524 |
| order_create | 20 | 11.658 | 12.512 |
| order_detail | 50 | 5.508 | 8.038 |
| status_update | 30 | 12.263 | 13.682 |
| link_create | 12 | 12.791 | 16.437 |
| link_replace | 1 | 13.633 | 13.633 |
| revoked_link_rejection | 1 | 16.116 | 16.116 |
| buyer_card | 12 | 12.251 | 12.976 |
| buyer_verify | 12 | 23.621 | 27.403 |
| buyer_details | 12 | 17.703 | 24.395 |
| buyer_pin_proposal | 2 | 21.583 | 24.137 |
| buyer_request_history | 4 | 7.169 | 9.145 |
| dispatcher_review | 6 | 13.013 | 15.297 |
| buyer_available | 12 | 20.316 | 23.483 |
| rider_assign | 14 | 15.668 | 20.776 |
| duplicate_assignment_rejection | 1 | 6.781 | 6.781 |
| rider_queue | 27 | 6.876 | 85.461 |
| rider_queue_poll | 27 | 6.85 | 8.365 |
| delivery_start | 13 | 15.534 | 18.704 |
| missing_cod_confirmation_rejection | 1 | 9.778 | 9.778 |
| delivery_finish | 13 | 16.344 | 19.467 |
| buyer_reschedule | 4 | 20.27 | 21.041 |
| paginated_list | 15 | 8.386 | 10.693 |
| filtered_list | 15 | 5.832 | 7.226 |

## Assumption-only comparison

```json
{
  "model_only": true,
  "orders": 20,
  "assumptions": {
    "baseline_failure_rate": 0.15,
    "unconfirmed_failure_rate": 0.15,
    "confirmed_failure_rate": 0.08,
    "confirmation_rate": 0.65,
    "baseline_seconds_per_order": 120,
    "lannpya_seconds_per_order": 45,
    "confirmation_handling_seconds": 60,
    "labour_mmk_per_hour": 3000,
    "failed_attempt_cost_mmk": 3500
  },
  "baseline": {
    "expected_failures": 3.0,
    "processing_seconds": 2400,
    "modeled_cost_mmk": 12500.0
  },
  "lannpya": {
    "expected_failures": 2.0900000000000003,
    "processing_seconds": 1680.0,
    "modeled_cost_mmk": 8715.0
  },
  "modeled_cost_difference_mmk": 3785.0,
  "warning": "Assumption model, not observed courier ROI or causal evidence."
}
```

Hubs are lab metadata, not backend entities. No route optimizer, real AI, financial
remittance, trusted geospatial verification or browser integration is represented.
Workflow sampling and trace omissions are explicit in report.json. IDs, credentials,
raw messages and full phones are omitted. Backend IDs/times/latencies are not seeded.
