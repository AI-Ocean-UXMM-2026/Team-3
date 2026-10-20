"""Record actual API outputs with synthetic inputs; injected adapters are test doubles."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai.extraction import (
    AddressExtractionProvider,
    ExtractionRateLimitError,
    ExtractionTimeoutError,
)
from app.core.config import Settings
from app.main import create_app

INPUT = "09791234567, Hlaing, COD 25000, address: behind red gate"


class ScenarioTestAdapter(AddressExtractionProvider):
    is_external = False

    def __init__(self, scenario):
        self.scenario = scenario

    @property
    def name(self):
        return "verification_test_double"

    async def extract(self, payload, *, timeout_seconds):
        if self.scenario == "timeout":
            raise ExtractionTimeoutError()
        if self.scenario == "rate_limited":
            raise ExtractionRateLimitError(30)
        if self.scenario == "malformed_json":
            return "not json"
        return json.dumps(
            {
                "landmark": {
                    "value": "red gate",
                    "quote": "behind red gate",
                    "fragment_id": "fragment_0",
                }
            }
        )


def main() -> None:
    cases = []
    for scenario in (
        "default_mock",
        "disabled",
        "timeout",
        "rate_limited",
        "malformed_json",
        "grounded_merge_test_double_NOT_REAL_AI",
    ):
        injected = scenario not in {"default_mock", "disabled"}
        settings = Settings(
            _env_file=None,
            parser_mode="hybrid",
            ai_provider="disabled" if scenario == "disabled" else "mock",
        )
        adapter = ScenarioTestAdapter(scenario) if injected else None
        with TestClient(create_app(settings, extraction_provider=adapter)) as client:
            response = client.post("/api/orders/parse", json={"raw_text": INPUT})
            assert response.status_code == 200
            cases.append(
                {
                    "scenario": scenario,
                    "injected_test_double": injected,
                    "external_ai_called": False,
                    "request": {"raw_text": INPUT},
                    "http_status": response.status_code,
                    "response": response.json(),
                }
            )
    output = Path(__file__).resolve().parents[2] / "docs" / "PHASE3_SAMPLE_RESPONSES.json"
    output.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(cases)} Phase 3 scenarios; no real AI services called.")


if __name__ == "__main__":
    main()
