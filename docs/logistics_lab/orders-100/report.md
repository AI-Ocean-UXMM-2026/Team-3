# Synthetic logistics run

Fictional experiment, not courier outcome/ROI evidence.

## Configuration

```json
{
  "orders": 100,
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
  "total_orders": 100,
  "initial_confidence": {
    "AMBER": 72,
    "RED": 28
  },
  "phone_township_valid_for_review": 72,
  "ambiguous_or_unverified_addresses": 72,
  "invalid_addresses": 28,
  "delivery_status": {
    "DELIVERED": 18,
    "DRAFT": 76,
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
  "manual_review_flagged_orders": 100,
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
    "ORDER_CREATED": 100,
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
  "total_events": 308,
  "workflow_orders_exercised": 24,
  "http_calls": 677,
  "unexpected_http_errors": 0,
  "expected_rejection_calls": 0,
  "duplicate_input_orders": 3,
  "confirmed_window_queue_observations": 5,
  "average_ingestion_api_ms": 16.891887000456336
}
```

## In-process API timing

| Operation | Samples | Median ms | p95 ms |
| --- | --- | --- | --- |
| rider_create | 6 | 10.622 | 98.56 |
| parse | 100 | 3.966 | 5.425 |
| order_create | 100 | 11.132 | 13.427 |
| order_detail | 92 | 5.117 | 5.91 |
| status_update | 54 | 11.727 | 13.269 |
| rider_assign | 24 | 15.494 | 23.585 |
| rider_queue | 48 | 6.63 | 80.35 |
| rider_queue_poll | 48 | 6.261 | 7.709 |
| delivery_start | 24 | 14.911 | 16.678 |
| delivery_finish | 24 | 15.867 | 17.398 |
| link_create | 18 | 11.972 | 13.188 |
| buyer_card | 18 | 11.65 | 13.372 |
| buyer_verify | 18 | 23.167 | 25.956 |
| buyer_details | 18 | 16.913 | 18.386 |
| buyer_available | 18 | 20.343 | 22.497 |
| buyer_pin_proposal | 4 | 20.147 | 22.753 |
| buyer_request_history | 9 | 6.66 | 8.301 |
| dispatcher_review | 14 | 12.498 | 15.865 |
| buyer_reschedule | 10 | 19.413 | 20.161 |
| paginated_list | 15 | 8.576 | 10.913 |
| filtered_list | 15 | 8.242 | 9.751 |

## Assumption-only comparison

```json
{
  "model_only": true,
  "orders": 100,
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
    "expected_failures": 15.0,
    "processing_seconds": 12000,
    "modeled_cost_mmk": 62500.0
  },
  "lannpya": {
    "expected_failures": 10.450000000000001,
    "processing_seconds": 8400.0,
    "modeled_cost_mmk": 43575.0
  },
  "modeled_cost_difference_mmk": 18925.0,
  "warning": "Assumption model, not observed courier ROI or causal evidence."
}
```

Hubs are lab metadata, not backend entities. No route optimizer, real AI, financial
remittance, trusted geospatial verification or browser integration is represented.
Workflow sampling and trace omissions are explicit in report.json. IDs, credentials,
raw messages and full phones are omitted. Backend IDs/times/latencies are not seeded.
