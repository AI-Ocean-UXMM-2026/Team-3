import csv
import json
from pathlib import Path

ORDER_COLUMNS = (
    "reference",
    "merchant",
    "hub",
    "kind",
    "confirm",
    "fail",
    "duplicate_of",
    "initial_confidence",
    "status",
    "cod_amount",
)
METRIC_COLUMNS = ("metric", "value")


def export_report(result: dict, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    public = {key: value for key, value in result.items() if key not in {"trace", "rows"}}
    (directory / "report.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    with (directory / "orders.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ORDER_COLUMNS)
        writer.writeheader()
        writer.writerows(result["rows"])
    with (directory / "metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=METRIC_COLUMNS)
        writer.writeheader()
        for key, value in result["metrics"].items():
            writer.writerow({"metric": key, "value": json.dumps(value, sort_keys=True)})
    with (directory / "trace.jsonl").open("w", encoding="utf-8") as stream:
        for record in result["trace"]:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    with (directory / "sensitivity.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = (
            "baseline_failure_rate",
            "confirmed_failure_rate",
            "confirmation_rate",
            "lannpya_seconds_per_order",
            "failed_attempt_cost_mmk",
            "modeled_cost_difference_mmk",
        )
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in result["sensitivity"]:
            writer.writerow({key: row.get(key, row["assumptions"].get(key)) for key in fields})
    lines = [
        "# Synthetic logistics run",
        "",
        "Fictional experiment, not courier outcome/ROI evidence.",
        "",
        "## Configuration",
        "",
        "```json",
        json.dumps(result["configuration"], indent=2),
        "```",
        "",
        "## Observed API/DB results",
        "",
        "```json",
        json.dumps(result["metrics"], indent=2),
        "```",
        "",
        "## In-process API timing",
        "",
        "| Operation | Samples | Median ms | p95 ms |",
        "| --- | --- | --- | --- |",
    ]
    for key, value in result["latency"].items():
        lines.append(f"| {key} | {value['samples']} | {value['median_ms']} | {value['p95_ms']} |")
    lines += [
        "",
        "## Assumption-only comparison",
        "",
        "```json",
        json.dumps(result["comparison"], indent=2),
        "```",
        "",
        "Hubs are lab metadata, not backend entities. No route optimizer, real AI, financial",
        "remittance, trusted geospatial verification or browser integration is represented.",
        "Workflow sampling and trace omissions are explicit in report.json. IDs, credentials,",
        "raw messages and full phones are omitted. Backend IDs/times/latencies are not seeded.",
    ]
    (directory / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "run_status.json").write_text(
        json.dumps({"passed": True, "configuration": result["configuration"]}, indent=2) + "\n",
        encoding="utf-8",
    )


def export_failure(directory: Path, config, error):
    directory.mkdir(parents=True, exist_ok=True)
    # Exception messages can contain SQL input or credentials: type only.
    payload = {
        "synthetic_only": True,
        "passed": False,
        "configuration": config.model_dump(),
        "error_type": type(error).__name__,
    }
    (directory / "failure.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "run_status.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
