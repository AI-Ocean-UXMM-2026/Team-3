import argparse
import json
import sys
from pathlib import Path

from app.db.session import BACKEND_ROOT
from tools.logistics_lab.config import SimulationConfig
from tools.logistics_lab.parser_benchmark import benchmark_parser
from tools.logistics_lab.reporting import export_failure, export_report
from tools.logistics_lab.runner import simulate


def main():
    parser = argparse.ArgumentParser(
        description="Isolated synthetic delivery experiments, not real ROI."
    )
    parser.add_argument("--orders", nargs="+", type=int, default=[100])
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--workflow-limit", type=int, default=24)
    parser.add_argument("--read-samples", type=int, default=15)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--output", type=Path, default=BACKEND_ROOT.parent / "docs/logistics_lab")
    args = parser.parse_args()
    # Validate all configs before doing any work or creating output files.
    configs = [
        SimulationConfig(
            orders=n,
            seed=args.seed,
            workflow_limit=args.workflow_limit,
            read_samples=args.read_samples,
            merchants=1 if args.demo else 3,
            hubs=1 if args.demo else 2,
            riders=3 if args.demo else 6,
            demo=args.demo,
        )
        for n in ([20] if args.demo else args.orders)
    ]
    failed = False
    for config in configs:
        destination = args.output / ("demo-20" if config.demo else f"orders-{config.orders}")
        try:
            result = simulate(config)
            export_report(result, destination)
            print(
                json.dumps(
                    {
                        "orders": config.orders,
                        "passed": True,
                        "workflows": result["metrics"]["workflow_orders_exercised"],
                        "events": result["metrics"]["total_events"],
                    }
                ),
                flush=True,
            )
        except Exception as error:
            export_failure(destination, config, error)
            print(
                json.dumps(
                    {"orders": config.orders, "passed": False, "error_type": type(error).__name__}
                ),
                flush=True,
            )
            failed = True
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "parser_benchmark.json").write_text(
        json.dumps(benchmark_parser(), indent=2) + "\n", encoding="utf-8"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
