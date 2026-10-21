import math
import statistics
from collections import Counter
from decimal import Decimal


def latency_summary(samples: dict[str, list[float]]) -> dict:
    return {
        name: {
            "samples": len(values),
            "median_ms": round(statistics.median(values), 3),
            "p95_ms": round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 3),
        }
        for name, values in samples.items()
        if values
    }


def aggregate(orders, events, assignments, buyer_requests, initial_confidence, queue_checks):
    statuses, confidence = Counter(), Counter(initial_confidence)
    event_counts = Counter(e.event_type for e in events)
    money_expected, money_asserted = Decimal(0), Decimal(0)
    by_id = {row.id: row for row in orders}
    for order in orders:
        statuses[str(order.status)] += 1
        if order.status == "DELIVERED" and order.cod_amount is not None:
            money_expected += order.cod_amount
    for assignment in assignments:
        if assignment.status == "COMPLETED" and assignment.cod_collected is True:
            row = by_id[assignment.order_id]
            money_asserted += row.cod_amount or Decimal(0)
    verified = {
        e.order_id
        for e in events
        if e.event_type == "BUYER_SECURITY" and e.event_metadata.get("action") == "VERIFIED"
    }
    confirmed = {
        r.order_id for r in buyer_requests if r.decision == "APPLIED" or r.resolution == "APPROVE"
    }
    manual = {
        e.order_id for e in events if e.event_type in {"ORDER_CORRECTED", "BUYER_REQUEST_REVIEWED"}
    }
    return {
        "total_orders": len(orders),
        "initial_confidence": dict(confidence),
        "phone_township_valid_for_review": confidence["AMBER"] + confidence["GREEN"],
        "ambiguous_or_unverified_addresses": confidence["AMBER"],
        "invalid_addresses": confidence["RED"],
        "delivery_status": dict(statuses),
        "confirmation_links_created": event_counts["BUYER_LINK_CREATED"],
        "phone_challenges_verified_orders": len(verified),
        "buyer_action_requests": len(buyer_requests),
        "successful_buyer_action_orders": len(confirmed),
        "rescheduling_requested_orders": len(
            {r.order_id for r in buyer_requests if r.submitted_values.get("action") == "RESCHEDULE"}
        ),
        "approved_rescheduling_orders": len(
            {
                r.order_id
                for r in buyer_requests
                if r.submitted_values.get("action") == "RESCHEDULE" and r.resolution == "APPROVE"
            }
        ),
        "orders_with_delivery_window": sum(bool(o.delivery_time_window) for o in orders),
        "dispatcher_review_events": event_counts["BUYER_REQUEST_REVIEWED"],
        "manual_intervention_executed_orders": len(manual),
        "manual_review_flagged_orders": sum(o.manual_review_required for o in orders),
        "rider_assignments": len(assignments),
        "completed_assignments": sum(a.status == "COMPLETED" for a in assignments),
        "delivered": statuses["DELIVERED"],
        "failed": statuses["FAILED"],
        "cod": {
            "delivered_expected_mmk": format(money_expected, ".0f"),
            "collection_asserted_mmk": format(money_asserted, ".0f"),
            "unasserted_delivered_mmk": format(money_expected - money_asserted, ".0f"),
            "state": "ASSERTIONS_ONLY_NOT_FINANCIAL_RECONCILIATION",
        },
        "queue_consistency_checks": queue_checks,
        "events": dict(event_counts),
        "total_events": len(events),
    }
