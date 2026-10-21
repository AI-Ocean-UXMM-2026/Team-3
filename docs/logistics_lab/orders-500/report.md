# Synthetic logistics run

Fictional experiment, not courier outcome/ROI evidence.

## Configuration

```json
{
  "orders": 500,
  "seed": 20261021,
  "merchants": 3,
  "hubs": 2,
  "riders": 6,
  "batch_size": 100,
  "read_samples": 15,
  "workflow_limit": 24,
  "confirmation_rate": 0.65,
  "delivery_failure_rate": 0.2,
  "demo": false
}
```

## Observed API/DB results

```json
{
  "total_orders": 500,
  "initial_confidence": {
    "AMBER": 351,
    "RED": 149
  },
  "phone_township_valid_for_review": 351,
  "ambiguous_or_unverified_addresses": 351,
  "invalid_addresses": 149,
  "delivery_status": {
    "DELIVERED": 18,
    "DRAFT": 476,
    "FAILED": 6
  },
  "confirmation_links_created": 18,
  "phone_challenges_verified_orders": 18,
  "buyer_action_requests": 32,
  "successful_buyer_action_orders": 18,
  "rescheduling_requested_orders": 5,
  "approved_rescheduling_orders": 5,
  "orders_with_delivery_window": 5,
  "dispatcher_review_events": 14,
  "manual_intervention_executed_orders": 9,
  "manual_review_flagged_orders": 500,
  "rider_assignments": 24,
  "completed_assignments": 18,
  "delivered": 18,
  "failed": 6,
  "cod": {
    "delivered_expected_mmk": "358000",
    "collection_asserted_mmk": "358000",
    "unasserted_delivered_mmk": "0",
    "state": "ASSERTIONS_ONLY_NOT_FINANCIAL_RECONCILIATION"
  },
  "queue_consistency_checks": 96,
  "events": {
    "ORDER_CREATED": 500,
    "STATUS_CHANGED": 54,
    "RIDER_ASSIGNED": 24,
    "DELIVERY_STARTED": 24,
    "DELIVERY_COMPLETED": 18,
    "BUYER_LINK_CREATED": 18,
    "BUYER_SECURITY": 18,
    "BUYER_RESPONSE": 28,
    "DELIVERY_FAILED": 6,
    "BUYER_LOCATION": 4,
    "BUYER_REQUEST_REVIEWED": 14
  },
  "total_events": 708,
  "workflow_orders_exercised": 24,
  "http_calls": 1477,
  "unexpected_http_errors": 0,
  "expected_rejection_calls": 0,
  "duplicate_input_orders": 17,
  "confirmed_window_queue_observations": 5,
  "average_ingestion_api_ms": 15.74658299987641
}
```

## In-process API timing

| Operation | Samples | Median ms | p95 ms |
| --- | --- | --- | --- |
| rider_create | 6 | 10.237 | 85.656 |
| parse | 500 | 3.883 | 4.733 |
| order_create | 500 | 11.29 | 13.039 |
| order_detail | 92 | 5.148 | 6.497 |
| status_update | 54 | 12.151 | 13.603 |
| rider_assign | 24 | 15.196 | 17.227 |
| rider_queue | 48 | 6.302 | 80.837 |
| rider_queue_poll | 48 | 6.277 | 8.536 |
| delivery_start | 24 | 14.76 | 16.452 |
| delivery_finish | 24 | 16.113 | 17.309 |
| link_create | 18 | 12.052 | 13.385 |
| buyer_card | 18 | 12.25 | 14.185 |
| buyer_verify | 18 | 23.214 | 27.15 |
| buyer_details | 18 | 16.868 | 18.96 |
| buyer_available | 18 | 20.396 | 24.753 |
| buyer_pin_proposal | 4 | 18.896 | 20.008 |
| buyer_request_history | 9 | 6.248 | 8.994 |
| dispatcher_review | 14 | 12.814 | 15.293 |
| buyer_reschedule | 10 | 20.308 | 24.449 |
| paginated_list | 15 | 12.948 | 17.104 |
| filtered_list | 15 | 11.152 | 14.089 |

## Assumption-only comparison

```json
{
  "model_only": true,
  "orders": 500,
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
    "expected_failures": 75.0,
    "processing_seconds": 60000,
    "modeled_cost_mmk": 312500.0
  },
  "lannpya": {
    "expected_failures": 52.25000000000001,
    "processing_seconds": 42000.0,
    "modeled_cost_mmk": 217875.0
  },
  "modeled_cost_difference_mmk": 94625.0,
  "warning": "Assumption model, not observed courier ROI or causal evidence."
}
```

Hubs are lab metadata, not backend entities. No route optimizer, real AI, financial
remittance, trusted geospatial verification or browser integration is represented.
Workflow sampling and trace omissions are explicit in report.json. IDs, credentials,
raw messages and full phones are omitted. Backend IDs/times/latencies are not seeded.
