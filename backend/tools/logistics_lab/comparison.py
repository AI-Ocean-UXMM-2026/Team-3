from itertools import product

from tools.logistics_lab.config import ComparisonConfig


def compare(orders: int, config: ComparisonConfig) -> dict:
    if type(orders) is not int or orders < 0:
        raise ValueError("orders must be a nonnegative integer")
    baseline_failures = orders * config.baseline_failure_rate
    lab_rate = (
        1 - config.confirmation_rate
    ) * config.unconfirmed_failure_rate + config.confirmation_rate * config.confirmed_failure_rate
    lab_failures = orders * lab_rate
    baseline_seconds = orders * config.baseline_seconds_per_order
    lab_seconds = orders * (
        config.lannpya_seconds_per_order
        + config.confirmation_rate * config.confirmation_handling_seconds
    )
    baseline_cost = (
        baseline_seconds / 3600 * config.labour_mmk_per_hour
        + baseline_failures * config.failed_attempt_cost_mmk
    )
    lab_cost = (
        lab_seconds / 3600 * config.labour_mmk_per_hour
        + lab_failures * config.failed_attempt_cost_mmk
    )
    return {
        "model_only": True,
        "orders": orders,
        "assumptions": config.model_dump(),
        "baseline": {
            "expected_failures": baseline_failures,
            "processing_seconds": baseline_seconds,
            "modeled_cost_mmk": round(baseline_cost, 2),
        },
        "lannpya": {
            "expected_failures": lab_failures,
            "processing_seconds": lab_seconds,
            "modeled_cost_mmk": round(lab_cost, 2),
        },
        "modeled_cost_difference_mmk": round(baseline_cost - lab_cost, 2),
        "warning": "Assumption model, not observed courier ROI or causal evidence.",
    }


def sensitivity(orders: int):
    rows = []
    # Includes scenarios where confirmation has no benefit or is worse than manual work.
    for baseline, confirmed, uptake, cost, handling in product(
        (0.05, 0.15), (0.03, 0.20), (0.20, 0.80), (1000, 3500), (30, 150)
    ):
        config = ComparisonConfig(
            baseline_failure_rate=baseline,
            unconfirmed_failure_rate=baseline,
            confirmed_failure_rate=confirmed,
            confirmation_rate=uptake,
            failed_attempt_cost_mmk=cost,
            lannpya_seconds_per_order=handling,
        )
        rows.append(compare(orders, config))
    return rows
