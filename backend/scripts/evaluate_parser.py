"""Score explicit deterministic fixture expectations, never mock AI quality."""

import asyncio
import json
from collections import Counter

from pydantic import ValidationError

from app.db.session import BACKEND_ROOT
from app.parsing.places import LocationCatalog
from app.schemas.orders import ParseRequest
from app.services.deterministic import DeterministicOrderParsingService


async def evaluate():
    corpus = json.loads((BACKEND_ROOT / "tests/fixtures/delivery_corpus.json").read_text("utf-8"))
    counters, failures = Counter(), []
    categories = Counter()
    service = DeterministicOrderParsingService(LocationCatalog())
    for row in corpus["records"]:
        categories[row["category"]] += 1
        try:
            request = ParseRequest(raw_text=row["raw_text"])
        except ValidationError:
            counters["invalid_inputs"] += 1
            counters["correct_rejections"] += not row["request_valid"]
            if row["request_valid"]:
                failures.append(row["id"])
            continue
        result = await service.parse(request)
        counters["valid_inputs"] += 1
        for field, expected in row["expected"].items():
            counters[f"{field}_cases"] += 1
            counters[f"{field}_matches"] += getattr(result.address, field) == expected
            if expected is not None:
                counters[f"{field}_positive_cases"] += 1
                counters[f"{field}_positive_matches"] += getattr(result.address, field) == expected
            if getattr(result.address, field) != expected:
                failures.append(row["id"])
        if row.get("classification_uncertainty"):
            counters["classification_uncertain_excluded"] += 1
        else:
            counters["classification_cases"] += 1
            counters["classification_matches"] += result.confidence == row["confidence"]
            if result.confidence != row["confidence"]:
                failures.append(row["id"])
        counters["original_preserved"] += result.original_text == row["raw_text"]
        counters["provenance_cases"] += 1
        counters["provenance_matches"] += all(
            result.normalized_text[e.start : e.end] == e.matched_text
            for source in result.field_sources.values()
            for e in source.evidence
        )
        if any(digit in row["raw_text"] for digit in "၀၁၂၃၄၅၆၇၈၉"):
            counters["digit_normalization_cases"] += 1
            counters["digit_normalization_matches"] += (
                result.normalization.digits_normalized
                and not any(digit in result.normalized_text for digit in "၀၁၂၃၄၅၆၇၈၉")
            )
    output = {
        "synthetic_only": True,
        "records": len(corpus["records"]),
        "categories": dict(categories),
        "metrics": dict(counters),
        "failure_ids": sorted(set(failures)),
        "limitations": "Template corpus regression score, not population or AI accuracy. "
        "No geospatial truth. Optional free-text extraction not scored.",
    }
    folder = BACKEND_ROOT.parent / "docs/overnight_audit"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "parser_results.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(evaluate())
