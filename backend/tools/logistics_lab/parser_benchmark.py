import asyncio
import json
from collections import Counter

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.db.session import BACKEND_ROOT
from app.main import create_app
from app.parsing.places import LocationCatalog, TrustedLocation
from app.schemas.orders import ParseRequest
from app.services.deterministic import DeterministicOrderParsingService


def score_pairs(pairs):
    counts = Counter(tp=0, fp=0, fn=0, tn=0, mismatches=0, cases=0)
    for expected, actual in pairs:
        counts["cases"] += 1
        if expected == actual:
            counts["tn" if expected is None else "tp"] += 1
        else:
            counts["mismatches"] += 1
            counts["fp"] += actual is not None
            counts["fn"] += expected is not None
    return {
        **counts,
        "precision": counts["tp"] / (counts["tp"] + counts["fp"])
        if counts["tp"] + counts["fp"]
        else None,
        "recall": counts["tp"] / (counts["tp"] + counts["fn"])
        if counts["tp"] + counts["fn"]
        else None,
        "error_rate": counts["mismatches"] / counts["cases"] if counts["cases"] else None,
    }


async def evaluate():
    corpus = json.loads((BACKEND_ROOT / "tests/fixtures/delivery_corpus.json").read_text("utf-8"))
    pairs = {key: [] for key in ("phone_number", "township", "cod_amount")}
    counts, failures = Counter(), []
    parser = DeterministicOrderParsingService(LocationCatalog())
    for record in corpus["records"]:
        try:
            request = ParseRequest(raw_text=record["raw_text"])
        except ValidationError:
            counts["rejected"] += 1
            counts["correct_rejections"] += not record["request_valid"]
            continue
        result = await parser.parse(request)
        for field in pairs:
            expected, actual = record["expected"][field], getattr(result.address, field)
            pairs[field].append((expected, actual))
            if expected != actual:
                failures.append(
                    {
                        "fixture": record["id"],
                        "category": record["category"],
                        "field": field,
                        "reason": "value_mismatch",
                    }
                )
        if record.get("classification_uncertainty"):
            counts["triage_unknown_excluded"] += 1
        else:
            counts["triage_labeled"] += 1
            counts["triage_matches"] += result.confidence == record["confidence"]
        counts["valid"] += 1
        counts["original_preserved"] += result.original_text == record["raw_text"]
        counts["provenance_matches"] += all(
            result.normalized_text[e.start : e.end] == e.matched_text
            for source in result.field_sources.values()
            for e in source.evidence
        )
        if any(ch in record["raw_text"] for ch in "၀၁၂၃၄၅၆၇၈၉"):
            counts["digit_cases"] += 1
            counts["digit_matches"] += result.normalization.digits_normalized
    synthetic_catalog = LocationCatalog(
        (
            TrustedLocation(
                township="Hlaing",
                field="street",
                name="Lab Fixture Road",
                dataset="synthetic-logic-test-only",
                source_url="https://fixture.example.invalid/not-real-geodata",
            ),
        )
    )
    green = await DeterministicOrderParsingService(synthetic_catalog).parse(
        ParseRequest(raw_text="09790000000, Hlaing Township, street: Lab Fixture Road, COD 0")
    )
    return {
        "synthetic_only": True,
        "corpus_records": len(corpus["records"]),
        "reuses": "overnight 300-record corpus; no duplicate dataset created",
        "field_scores": {field: score_pairs(values) for field, values in pairs.items()},
        "checks": dict(counts),
        "categorized_failures": failures,
        "ai_accuracy": None,
        "synthetic_green_branch": {
            "test_only": True,
            "confidence": str(green.confidence),
            "catalog": "synthetic-logic-test-only",
            "coordinates": None,
            "not_real_geospatial_evidence": True,
            "scope": "Injected catalog logic check; default order simulator has no trusted catalog",
        },
        "geospatial_accuracy": None,
        "limitations": "Known synthetic template labels only; no population inference.",
    }


def benchmark_parser():
    result = asyncio.run(evaluate())
    with TestClient(create_app(Settings(_env_file=None, order_management_enabled=False))) as client:
        response = client.post(
            "/api/orders/parse",
            content=b'{"raw_text":"\\ud800"}',
            headers={"Content-Type": "application/json"},
        )
        result["checks"]["malformed_unicode_json_rejected"] = response.status_code == 422
    return result
