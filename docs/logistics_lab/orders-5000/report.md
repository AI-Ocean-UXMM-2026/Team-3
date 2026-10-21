# Synthetic logistics run

Fictional experiment, not courier outcome/ROI evidence.

## Configuration

```json
{
  "orders": 5000,
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
  "total_orders": 5000,
  "initial_confidence": {
    "AMBER": 3382,
    "RED": 1618
  },
  "phone_township_valid_for_review": 3382,
  "ambiguous_or_unverified_addresses": 3382,
  "invalid_addresses": 1618,
  "delivery_status": {
    "DELIVERED": 18,
    "DRAFT": 4976,
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
  "manual_review_flagged_orders": 5000,
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
    "ORDER_CREATED": 5000,
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
  "total_events": 5208,
  "workflow_orders_exercised": 24,
  "http_calls": 10477,
  "unexpected_http_errors": 0,
  "expected_rejection_calls": 0,
  "duplicate_input_orders": 172,
  "confirmed_window_queue_observations": 5,
  "average_ingestion_api_ms": 16.433424680015015
}
```

## In-process API timing

| Operation | Samples | Median ms | p95 ms |
| --- | --- | --- | --- |
| rider_create | 6 | 12.139 | 107.142 |
| parse | 5000 | 4.127 | 5.125 |
| order_create | 5000 | 11.939 | 14.141 |
| order_detail | 92 | 5.456 | 6.695 |
| status_update | 54 | 12.574 | 14.721 |
| rider_assign | 24 | 15.694 | 19.476 |
| rider_queue | 48 | 6.835 | 87.402 |
| rider_queue_poll | 48 | 6.701 | 7.768 |
| delivery_start | 24 | 15.372 | 16.623 |
| delivery_finish | 24 | 16.321 | 18.233 |
| link_create | 18 | 12.642 | 14.154 |
| buyer_card | 18 | 12.532 | 15.24 |
| buyer_verify | 18 | 23.827 | 25.85 |
| buyer_details | 18 | 17.631 | 19.681 |
| buyer_available | 18 | 21.099 | 26.274 |
| buyer_pin_proposal | 4 | 21.128 | 22.637 |
| buyer_request_history | 9 | 6.793 | 7.962 |
| dispatcher_review | 14 | 13.072 | 15.832 |
| buyer_reschedule | 10 | 20.241 | 22.771 |
| paginated_list | 15 | 63.936 | 73.41 |
| filtered_list | 15 | 48.574 | 54.06 |

## Assumption-only comparison

```json
{
  "model_only": true,
  "orders": 5000,
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
    "expected_failures": 750.0,
    "processing_seconds": 600000,
    "modeled_cost_mmk": 3125000.0
  },
  "lannpya": {
    "expected_failures": 522.5,
    "processing_seconds": 420000.0,
    "modeled_cost_mmk": 2178750.0
  },
  "modeled_cost_difference_mmk": 946250.0,
  "warning": "Assumption model, not observed courier ROI or causal evidence."
}
```

Hubs are lab metadata, not backend entities. No route optimizer, real AI, financial
remittance, trusted geospatial verification or browser integration is represented.
Workflow sampling and trace omissions are explicit in report.json. IDs, credentials,
raw messages and full phones are omitted. Backend IDs/times/latencies are not seeded.
