"""Offline label/contract validation; this does not call or score a real AI model."""

import json
from pathlib import Path

from app.ai.extraction import AIExtractionResponse


def evaluate():
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/phase16_ai_benchmark.json"
    rows = json.loads(fixture.read_text(encoding="utf-8"))
    for row in rows:
        output = AIExtractionResponse.model_validate(row["expected_ai"], strict=True)
        for suggestion in output.model_dump().values():
            if suggestion is not None:
                assert suggestion["value"] in suggestion["quote"] in row["text"]
    return {
        "mode": "offline_contract_and_label_validation",
        "synthetic_cases": len(rows),
        "valid_expected_schemas": len(rows),
        "real_model_calls": 0,
        "model_accuracy": None,
        "limitations": [
            "Labels express synthetic expectations, not independently measured accuracy.",
            "Ambiguous values may remain null; unsupported AI fields are forbidden.",
            "Time expressions remain deterministic/reviewed instructions; no automatic scheduling.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
