import csv
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.db.session import BACKEND_ROOT
from tools.logistics_lab.analytics import aggregate, latency_summary
from tools.logistics_lab.comparison import compare, sensitivity
from tools.logistics_lab.config import ComparisonConfig, SimulationConfig
from tools.logistics_lab.dataset import generate_plan
from tools.logistics_lab.parser_benchmark import benchmark_parser, score_pairs
from tools.logistics_lab.reporting import (
    METRIC_COLUMNS,
    ORDER_COLUMNS,
    export_failure,
    export_report,
)
from tools.logistics_lab.runner import SimulationError, simulate


@pytest.mark.parametrize(
    "change",
    [
        {"orders": -1},
        {"orders": 5001},
        {"orders": True},
        {"seed": -1},
        {"riders": 0},
        {"merchants": 0},
        {"hubs": 0},
        {"batch_size": 0},
        {"read_samples": 0},
        {"read_samples": 51},
        {"workflow_limit": -1},
        {"confirmation_rate": 1.1},
        {"delivery_failure_rate": float("nan")},
        {"unknown": 1},
    ],
)
def test_lab_invalid_configuration_fails_before_simulation(change):
    with pytest.raises(ValidationError):
        SimulationConfig(**change)


def test_seeded_plans_are_reproducible_and_different_seeds_differ():
    config = SimulationConfig(orders=100)
    assert generate_plan(config) == generate_plan(config)
    assert generate_plan(config) != generate_plan(config.model_copy(update={"seed": 7}))
    assert len({row.reference for row in generate_plan(config)}) == 100
    assert generate_plan(SimulationConfig(orders=500))[:100] == generate_plan(config)


def test_duplicate_inputs_remain_explicit_and_public_plan_has_no_phone():
    plan = generate_plan(SimulationConfig(orders=20, demo=True))
    duplicate = plan[6]
    assert duplicate.duplicate_of == plan[0].reference
    assert duplicate.raw_text == plan[0].raw_text
    assert "raw_text" not in duplicate.public()
    assert "phone_last_four" not in duplicate.public()
    assert len(asdict(duplicate)) > len(duplicate.public())


def test_baseline_model_can_show_lannpya_worse_and_has_no_forced_improvement():
    result = compare(
        100,
        ComparisonConfig(
            baseline_failure_rate=0.01,
            unconfirmed_failure_rate=0.2,
            confirmed_failure_rate=0.3,
            lannpya_seconds_per_order=500,
        ),
    )
    assert result["modeled_cost_difference_mmk"] < 0
    assert result["lannpya"]["expected_failures"] > result["baseline"]["expected_failures"]
    rows = sensitivity(100)
    assert len(rows) == 32
    assert any(row["modeled_cost_difference_mmk"] < 0 for row in rows)
    assert any(row["modeled_cost_difference_mmk"] > 0 for row in rows)


def test_comparison_formula_zero_and_known_values():
    config = ComparisonConfig(
        baseline_failure_rate=0.1,
        unconfirmed_failure_rate=0.1,
        confirmed_failure_rate=0,
        confirmation_rate=0.5,
        baseline_seconds_per_order=60,
        lannpya_seconds_per_order=30,
        confirmation_handling_seconds=60,
        labour_mmk_per_hour=3600,
        failed_attempt_cost_mmk=1000,
    )
    result = compare(10, config)
    assert result["baseline"]["expected_failures"] == 1
    assert result["lannpya"]["expected_failures"] == 0.5
    assert (
        result["baseline"]["processing_seconds"] == result["lannpya"]["processing_seconds"] == 600
    )
    assert result["modeled_cost_difference_mmk"] == 500
    assert compare(0, config)["modeled_cost_difference_mmk"] == 0
    with pytest.raises(ValueError):
        compare(-1, config)


def test_precision_recall_treat_wrong_nonnull_prediction_as_fp_and_fn():
    result = score_pairs([("a", "a"), ("a", "b"), (None, "b"), ("a", None), (None, None)])
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 2, 2, 1)
    assert result["precision"] == result["recall"] == pytest.approx(1 / 3)
    assert result["error_rate"] == 0.6
    assert score_pairs([])["precision"] is None


def test_actual_parser_benchmark_uses_known_labels_and_excludes_ai_accuracy():
    result = benchmark_parser()
    assert result["corpus_records"] == 300
    assert result["checks"]["correct_rejections"] == 30
    assert result["checks"]["triage_unknown_excluded"] == 10
    assert result["checks"]["malformed_unicode_json_rejected"] is True
    assert result["categorized_failures"] == []
    assert result["ai_accuracy"] is None
    assert result["synthetic_green_branch"]["confidence"] == "GREEN"
    assert result["synthetic_green_branch"]["not_real_geospatial_evidence"] is True
    assert all(score["error_rate"] == 0 for score in result["field_scores"].values())


def test_event_counts_and_exact_money_do_not_call_collection_remittance():
    orders = [
        SimpleNamespace(
            id=i,
            status=status,
            cod_amount=Decimal(amount),
            manual_review_required=True,
            delivery_time_window=None,
        )
        for i, status, amount in (
            (1, "DELIVERED", "1000000000"),
            (2, "DELIVERED", "25000"),
            (3, "FAILED", "48000"),
        )
    ]
    events = [
        SimpleNamespace(event_type="ORDER_CREATED", order_id=i, event_metadata={})
        for i in range(1, 4)
    ]
    assignments = [
        SimpleNamespace(order_id=1, status="COMPLETED", cod_collected=True),
        SimpleNamespace(order_id=2, status="COMPLETED", cod_collected=False),
    ]
    result = aggregate(orders, events, assignments, [], ["AMBER"] * 3, 2)
    assert result["total_events"] == 3 and result["delivered"] == 2 and result["failed"] == 1
    assert result["cod"]["delivered_expected_mmk"] == "1000025000"
    assert result["cod"]["collection_asserted_mmk"] == "1000000000"
    assert result["cod"]["unasserted_delivered_mmk"] == "25000"
    assert "NOT_FINANCIAL" in result["cod"]["state"]


def test_latency_summary_empty_and_percentile_definition():
    assert latency_summary({"unused": []}) == {}
    stats = latency_summary({"sample": [1.0, 2.0, 3.0, 4.0, 100.0]})["sample"]
    assert stats == {"samples": 5, "median_ms": 3.0, "p95_ms": 100.0}


def test_empty_run_and_exports_are_valid(tmp_path):
    result = simulate(SimulationConfig(orders=0, riders=1, merchants=1, hubs=1))
    assert result["metrics"]["total_orders"] == 0
    assert result["metrics"]["total_events"] == 0
    assert result["metrics"]["average_ingestion_api_ms"] == 0
    export_report(result, tmp_path)
    export_failure(tmp_path, SimulationConfig(orders=0), RuntimeError("synthetic secret"))
    assert json.loads((tmp_path / "run_status.json").read_text())["passed"] is False
    export_report(result, tmp_path)
    assert json.loads((tmp_path / "run_status.json").read_text())["passed"] is True
    assert json.loads((tmp_path / "report.json").read_text())["synthetic_only"]
    with (tmp_path / "orders.csv").open(newline="") as stream:
        assert next(csv.reader(stream)) == list(ORDER_COLUMNS)
    with (tmp_path / "metrics.csv").open(newline="") as stream:
        assert next(csv.reader(stream)) == list(METRIC_COLUMNS)


def test_demo_workflow_events_rescheduling_queue_and_export_privacy(tmp_path):
    result = simulate(SimulationConfig(orders=10, demo=True, riders=3, workflow_limit=10))
    metrics = result["metrics"]
    assert metrics["total_orders"] == 10
    assert metrics["delivered"] > 0 and metrics["failed"] == 1
    assert metrics["delivery_status"]["ASSIGNED"] == 1
    assert metrics["initial_confidence"].get("GREEN", 0) == 0
    assert metrics["approved_rescheduling_orders"] == 1
    assert metrics["confirmed_window_queue_observations"] > 0
    assert metrics["queue_consistency_checks"] > 0
    assert metrics["unexpected_http_errors"] == 0
    assert result["isolation"]["database_reopened"]
    assert result["isolation"]["persisted_events"] == metrics["total_events"]
    export_report(result, tmp_path)
    exported = "".join(path.read_text("utf-8") for path in tmp_path.iterdir())
    for forbidden in (
        "access_token",
        "last_four",
        "X-Dev-Access-Token",
        "raw_text",
        "phone_last_four",
    ):
        assert forbidden not in exported
    traces = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert any(row["operation"] == "buyer_pin_proposal" for row in traces)
    assert any(row["operation"] == "revoked_link_rejection" for row in traces)


def test_identical_seed_has_identical_business_outcomes_not_latency():
    config = SimulationConfig(orders=5, demo=True, riders=1, workflow_limit=2)
    first, second = simulate(config), simulate(config)
    metrics_a, metrics_b = dict(first["metrics"]), dict(second["metrics"])
    metrics_a.pop("average_ingestion_api_ms")
    metrics_b.pop("average_ingestion_api_ms")
    assert metrics_a == metrics_b
    assert first["rows"] == second["rows"]


def test_database_fault_is_isolated_and_failure_export_redacts_message(monkeypatch, tmp_path):
    targets = [BACKEND_ROOT / ".env", BACKEND_ROOT / "data/lannpya_dev.sqlite3"]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets if p.exists()}

    def fail(*args, **kwargs):
        raise OperationalError("synthetic statement", {}, Exception("sensitive-fixture-value"))

    monkeypatch.setattr("app.services.order_management.OrderManagementService.create", fail)
    config = SimulationConfig(orders=1, riders=1)
    with pytest.raises(SimulationError) as error:
        simulate(config)
    export_failure(tmp_path, config, error.value)
    assert "sensitive-fixture-value" not in (tmp_path / "failure.json").read_text()
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    monkeypatch.undo()
    assert simulate(config)["metrics"]["total_orders"] == 1
