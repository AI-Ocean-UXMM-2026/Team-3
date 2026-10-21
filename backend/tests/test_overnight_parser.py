import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.core.config import Settings
from app.db.session import BACKEND_ROOT
from app.main import create_app
from app.parsing.normalization import normalize_text
from app.parsing.places import LocationCatalog
from app.schemas.buyer import BuyerResponse, ReviewBuyerRequest, SetLocationReference
from app.schemas.management import StructuredOrder
from app.schemas.orders import ParseRequest
from app.services.deterministic import DeterministicOrderParsingService

CORPUS = json.loads((BACKEND_ROOT / "tests/fixtures/delivery_corpus.json").read_text("utf-8"))
BOUNDED = settings(max_examples=50, derandomize=True, database=None, deadline=None)


@pytest.mark.parametrize("row", CORPUS["records"], ids=lambda row: row["id"])
def test_synthetic_corpus(row):
    if not row["request_valid"]:
        with pytest.raises(ValidationError):
            ParseRequest(raw_text=row["raw_text"])
        return
    parsed = asyncio.run(
        DeterministicOrderParsingService(LocationCatalog()).parse(
            ParseRequest(raw_text=row["raw_text"])
        )
    )
    assert parsed.original_text == row["raw_text"]
    for key, value in row["expected"].items():
        assert getattr(parsed.address, key) == value
    if row.get("classification_uncertainty"):
        assert parsed.confidence in {"AMBER", "RED"}
        if parsed.confidence == "RED":
            assert "ENCODING_UNCERTAIN" in {reason.code for reason in parsed.validation_reasons}
    else:
        assert parsed.confidence == row["confidence"]
    assert not parsed.location_verification.status == "verified"
    assert set(parsed.field_sources) == set(type(parsed.address).model_fields)
    for source in parsed.field_sources.values():
        for item in source.evidence:
            assert parsed.normalized_text[item.start : item.end] == item.matched_text


@BOUNDED
@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=300))
def test_arbitrary_unicode_normalization_is_total(text):
    normalized, _ = normalize_text(text)
    assert isinstance(normalized, str)
    assert not any(ch in normalized for ch in "၀၁၂၃၄၅၆၇၈၉")


@BOUNDED
@given(st.integers(min_value=-1000000000, max_value=-1))
def test_negative_structured_cod_is_never_accepted(amount):
    with pytest.raises(ValidationError):
        StructuredOrder(cod_amount=amount)


@BOUNDED
@given(st.floats(min_value=90.000001, max_value=100000, allow_nan=False))
def test_invalid_latitude_never_accepted(latitude):
    with pytest.raises(ValidationError):
        StructuredOrder(latitude=latitude, longitude=0)


@BOUNDED
@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz \t", min_size=1, max_size=100))
def test_missing_phone_and_unknown_township_cannot_be_green(text):
    parsed = asyncio.run(
        DeterministicOrderParsingService(LocationCatalog()).parse(
            ParseRequest(raw_text="unknown-place " + text)
        )
    )
    assert parsed.confidence == "RED"
    assert parsed.original_text == "unknown-place " + text


@pytest.mark.parametrize(
    "field",
    [
        "customer_name",
        "street",
        "landmark",
        "building",
        "floor",
        "unit",
        "delivery_instructions",
        "delivery_time_window",
    ],
)
def test_nul_cannot_reach_persistent_structured_text(field):
    with pytest.raises(ValidationError):
        StructuredOrder(**{field: "synthetic\x00text"})


def test_nul_is_safe_api_validation_error_and_normal_whitespace_is_preserved():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        bad = client.post("/api/orders/parse", json={"raw_text": "private\x00text"})
        assert bad.status_code == 422
        assert "private" not in bad.text
        raw = "Hlaing Township\nCOD 25000\t"
        assert (
            client.post("/api/orders/parse", json={"raw_text": raw}).json()["original_text"] == raw
        )


@pytest.mark.parametrize(
    "schema,body",
    [
        (
            BuyerResponse,
            {
                "request_id": "00000000-0000-4000-8000-000000000001",
                "action": "INSTRUCTIONS",
                "instructions": "note\x00bad",
            },
        ),
        (
            ReviewBuyerRequest,
            {"expected_version": 1, "decision": "REJECT", "reason": "bad\x00note"},
        ),
        (
            SetLocationReference,
            {
                "request_id": "00000000-0000-4000-8000-000000000001",
                "latitude": 0,
                "longitude": 0,
                "township": "Hlaing",
                "source_reference": "bad\x00reference",
                "independently_checked": True,
            },
        ),
    ],
)
def test_nul_is_rejected_from_buyer_audit_text(schema, body):
    with pytest.raises(ValidationError):
        schema.model_validate(body)


def test_unavailable_encoding_detector_retains_input_and_requires_review(monkeypatch, caplog):
    def broken():
        raise OSError("private-detector-error")

    monkeypatch.setattr("app.parsing.normalization.detector", broken)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        raw = "09790000000, လှိုင်မြို့နယ်, COD 25000"
        response = client.post("/api/orders/parse", json={"raw_text": raw})
        assert response.status_code == 200
        data = response.json()
        assert data["original_text"] == raw
        assert data["address"]["phone_number"] == "09790000000"
        assert data["confidence"] == "RED"
        assert "ENCODING_UNCERTAIN" in {x["code"] for x in data["validation_reasons"]}
        assert "private-detector-error" not in caplog.text
