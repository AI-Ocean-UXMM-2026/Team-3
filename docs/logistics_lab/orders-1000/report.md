# Synthetic logistics run

Fictional experiment, not courier outcome/ROI evidence.

## Configuration

```json
{
  "orders": 1000,
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
  "total_orders": 1000,
  "initial_confidence": {
    "AMBER": 706,
    "RED": 294
  },
  "phone_township_valid_for_review": 706,
  "ambiguous_or_unverified_addresses": 706,
  "invalid_addresses": 294,
  "delivery_status": {
    "DELIVERED": 18,
    "DRAFT": 976,
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
  "manual_review_flagged_orders": 1000,
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
    "ORDER_CREATED": 1000,
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
  "total_events": 1208,
  "workflow_orders_exercised": 24,
  "http_calls": 2477,
  "unexpected_http_errors": 0,
  "expected_rejection_calls": 0,
  "duplicate_input_orders": 34,
  "confirmed_window_queue_observations": 5,
  "average_ingestion_api_ms": 15.95188319998124
}
```

## In-process API timing

| Operation | Samples | Median ms | p95 ms |
| --- | --- | --- | --- |
| rider_create | 6 | 10.629 | 84.204 |
| parse | 1000 | 3.978 | 4.745 |
| order_create | 1000 | 11.641 | 13.283 |
| order_detail | 92 | 5.725 | 7.137 |
| status_update | 54 | 13.073 | 15.123 |
| rider_assign | 24 | 17.412 | 19.87 |
| rider_queue | 48 | 7.014 | 82.777 |
| rider_queue_poll | 48 | 6.762 | 8.541 |
| delivery_start | 24 | 15.763 | 18.828 |
| delivery_finish | 24 | 17.318 | 18.233 |
| link_create | 18 | 13.308 | 15.728 |
| buyer_card | 18 | 13.111 | 30.421 |
| buyer_verify | 18 | 24.83 | 26.781 |
| buyer_details | 18 | 18.273 | 20.537 |
| buyer_available | 18 | 21.962 | 25.877 |
| buyer_pin_proposal | 4 | 20.454 | 22.066 |
| buyer_request_history | 9 | 7.32 | 8.777 |
| dispatcher_review | 14 | 13.419 | 16.903 |
| buyer_reschedule | 10 | 22.368 | 25.639 |
| paginated_list | 15 | 19.623 | 21.138 |
| filtered_list | 15 | 16.65 | 17.647 |

## Assumption-only comparison

```json
{
  "model_only": true,
  "orders": 1000,
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
    "expected_failures": 150.0,
    "processing_seconds": 120000,
    "modeled_cost_mmk": 625000.0
  },
  "lannpya": {
    "expected_failures": 104.50000000000001,
    "processing_seconds": 84000.0,
    "modeled_cost_mmk": 435750.0
  },
  "modeled_cost_difference_mmk": 189250.0,
  "warning": "Assumption model, not observed courier ROI or causal evidence."
}
```

Hubs are lab metadata, not backend entities. No route optimizer, real AI, financial
remittance, trusted geospatial verification or browser integration is represented.
Workflow sampling and trace omissions are explicit in report.json. IDs, credentials,
raw messages and full phones are omitted. Backend IDs/times/latencies are not seeded.
