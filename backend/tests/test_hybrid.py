import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.adapters.mock import DisabledExtractionProvider, MockExtractionProvider
from app.ai.extraction import (
    AddressExtractionProvider,
    AIExtractionResponse,
    ExtractionRateLimitError,
    ExtractionTimeoutError,
    ExtractionUnavailableError,
)
from app.ai.factory import create_extraction_provider
from app.ai.sanitization import prepare_ai_request
from app.api.routes import get_extraction_provider
from app.core.config import Settings
from app.main import create_app
from app.schemas.orders import ParseResponse

BASE = "09791234567, Hlaing, COD 25000, address: behind red gate"


class TestAdapter(AddressExtractionProvider):
    __test__ = False
    is_external = False

    def __init__(self, output="{}", error=None, delay=0):
        self.output, self.error, self.delay = output, error, delay
        self.requests, self.timeouts = [], []
        self.cancelled = False

    @property
    def name(self):
        return "test_adapter"

    async def extract(self, payload, *, timeout_seconds):
        self.requests.append(payload)
        self.timeouts.append(timeout_seconds)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
            return self.output(payload) if callable(self.output) else self.output
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def suggestion(value="red gate", quote="behind red gate", fragment_id="fragment_0"):
    return {"value": value, "quote": quote, "fragment_id": fragment_id}


def run_parse(provider=None, text=BASE, **settings):
    app = create_app(
        Settings(_env_file=None, parser_mode="hybrid", **settings), extraction_provider=provider
    )
    with TestClient(app) as client:
        response = client.post("/api/orders/parse", json={"raw_text": text})
    assert response.status_code == 200, response.text
    return ParseResponse.model_validate(response.json())


def test_default_hybrid_mock_preserves_real_results():
    parsed = run_parse()
    assert parsed.provider == "rules" and not parsed.is_mock
    assert parsed.address.phone_number == "09791234567"
    assert parsed.address.cod_amount == 25000 and parsed.address.township == "Hlaing"
    assert parsed.original_text == BASE
    assert parsed.ai.status == "mock" and parsed.ai.is_mock and parsed.ai.attempted
    assert parsed.ai.applied_fields == [] and parsed.address.landmark is None
    assert parsed.confidence == "AMBER" and parsed.manual_review_required


def test_mock_provider_contract():
    payload = TestAdapter()
    parsed = run_parse(payload)
    prepared = prepare_ai_request(parsed, 2000)
    raw = asyncio.run(MockExtractionProvider().extract(prepared.payload, timeout_seconds=1))
    assert AIExtractionResponse.model_validate_json(raw).model_dump() == {
        "landmark": None,
        "building_floor_unit": None,
        "delivery_instructions": None,
    }
    with pytest.raises(TypeError):
        AddressExtractionProvider()


def test_grounded_landmark_merge_and_provenance():
    parsed = run_parse(TestAdapter(json.dumps({"landmark": suggestion()})))
    assert parsed.address.landmark == "red gate"
    assert parsed.ai.status == "available" and parsed.ai.applied_fields == ["landmark"]
    source = parsed.field_sources["landmark"]
    assert source.method == "ai" and source.provider == "test_adapter"
    assert source.requires_review and not source.verified
    item = source.evidence[0]
    assert parsed.normalized_text[item.start : item.end] == "behind red gate"
    assert parsed.address.phone_number == "09791234567" and parsed.address.cod_amount == 25000
    assert parsed.confidence == "AMBER" and parsed.manual_review_required
    assert "AI_FIELD_REVIEW" in {r.code for r in parsed.validation_reasons}


def test_unit_and_instruction_can_be_enriched_with_input_evidence():
    output = {
        "building_floor_unit": suggestion("upper level", "upper level", "fragment_0"),
        "delivery_instructions": suggestion("knock gently", "knock gently", "fragment_1"),
    }
    parsed = run_parse(
        TestAdapter(json.dumps(output)),
        "09791234567, Hlaing, address: upper level, address: knock gently",
    )
    assert parsed.address.building_floor_unit == "upper level"
    assert parsed.address.delivery_instructions == "knock gently"
    assert set(parsed.ai.applied_fields) == {"building_floor_unit", "delivery_instructions"}


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "```json\n{}\n```",
        "[]",
        "null",
        "true",
        "42",
        '{"landmark":"red gate"}',
        '{"landmark":{"value":123}}',
        '{"landmark":null,"landmark":null}',
        '{"landmark":NaN}',
        '{"landmark":{"value":" ","fragment_id":"fragment_0","quote":"behind red gate"}}',
        "x" * 16385,
        b"{}",
        {},
        "[" * 1200 + "]" * 1200,
    ],
)
def test_malformed_ai_output_degrades_without_data_loss(raw):
    parsed = run_parse(TestAdapter(raw))
    assert parsed.ai.status == "invalid_response"
    assert parsed.address.landmark is None
    assert parsed.address.phone_number == "09791234567" and parsed.address.cod_amount == 25000
    assert parsed.confidence == "AMBER"


@pytest.mark.parametrize(
    "key,value",
    [
        ("phone_number", "09951234567"),
        ("cod_amount", 0),
        ("customer_name", "Invented"),
        ("township", "Bahan"),
        ("street", "Invented Road"),
        ("confidence", "GREEN"),
        ("latitude", 16.8),
        ("longitude", 96.1),
        ("coordinates", [16.8, 96.1]),
        ("score", 0.99),
        ("is_mock", False),
    ],
)
def test_ai_cannot_supply_authoritative_or_fabricated_fields(key, value):
    parsed = run_parse(TestAdapter(json.dumps({key: value, "landmark": suggestion()})))
    assert parsed.ai.status == "invalid_response"
    assert parsed.address.phone_number == "09791234567"
    assert parsed.address.cod_amount == 25000 and parsed.address.township == "Hlaing"
    assert parsed.address.landmark is None  # Validate the whole output before any merge.


@pytest.mark.parametrize(
    "bad",
    [
        suggestion("Invented Temple", "behind red gate"),
        suggestion(quote="not in the request"),
        suggestion(fragment_id="fragment_999"),
    ],
)
def test_ungrounded_values_are_rejected(bad):
    parsed = run_parse(TestAdapter(json.dumps({"landmark": bad})))
    assert parsed.ai.status == "invalid_response" and parsed.address.landmark is None


def test_repeated_evidence_quote_is_ambiguous():
    parsed = run_parse(
        TestAdapter(json.dumps({"landmark": suggestion()})), text=BASE + " behind red gate"
    )
    assert parsed.ai.status == "invalid_response"


def test_ai_cannot_overwrite_existing_deterministic_optional_fields():
    text = "09791234567, Hlaing, note: knock gently, address: behind red gate"
    parsed = run_parse(
        TestAdapter(
            json.dumps(
                {
                    "delivery_instructions": suggestion(
                        "knock gently", "knock gently", "fragment_0"
                    ),
                }
            )
        ),
        text,
    )
    assert parsed.ai.status == "invalid_response"
    assert parsed.address.delivery_instructions == "knock gently"
    assert parsed.field_sources["delivery_instructions"].method == "rule"


def test_ai_cannot_resolve_deterministic_ambiguity_without_review():
    text = "09791234567, Hlaing, near school, near shop"
    parsed = run_parse(TestAdapter(json.dumps({"landmark": suggestion("school", "school")})), text)
    assert parsed.ai.status == "available"
    assert parsed.address.landmark is None
    assert parsed.field_sources["landmark"].status == "ambiguous"
    assert parsed.field_sources["landmark"].ai_suggestion == "school"
    assert parsed.ai.suggested_fields == ["landmark"]
    assert parsed.confidence == "AMBER"


def test_mock_suggestions_are_never_merged():
    adapter = TestAdapter(json.dumps({"landmark": suggestion()}))
    adapter.is_mock = True
    parsed = run_parse(adapter)
    assert parsed.ai.status == "mock" and parsed.address.landmark is None


def test_timeout_cancels_request_and_preserves_deterministic_results():
    adapter = TestAdapter(delay=10)
    parsed = run_parse(adapter, ai_timeout_seconds=0.01)
    assert parsed.ai.status == "timeout" and adapter.cancelled
    assert adapter.timeouts == [0.01]
    assert parsed.address.phone_number == "09791234567" and parsed.address.cod_amount == 25000


@pytest.mark.parametrize(
    "error,status",
    [
        (ExtractionTimeoutError("private timeout payload"), "timeout"),
        (ExtractionRateLimitError(30), "rate_limited"),
        (ExtractionUnavailableError("sk-private upstream"), "unavailable"),
        (RuntimeError("sk-private customer phone 09791234567"), "unavailable"),
    ],
)
def test_failure_modes_are_explicit_and_logs_are_private(error, status, caplog):
    parsed = run_parse(TestAdapter(error=error))
    assert parsed.ai.status == status
    assert parsed.address.cod_amount == 25000 and parsed.address.phone_number == "09791234567"
    assert "sk-private" not in parsed.ai.model_dump_json()
    assert "09791234567" not in caplog.text and "sk-private" not in caplog.text
    assert parsed.confidence == "AMBER"
    if status == "rate_limited":
        assert parsed.ai.retry_after_seconds == 30


@pytest.mark.parametrize(
    "raw,expected", [(-4, 1), (1000000, 86400), (None, None), ("secret", None)]
)
def test_rate_limit_header_is_bounded(raw, expected):
    assert ExtractionRateLimitError(raw).retry_after_seconds == expected


def test_external_adapters_cannot_make_a_paid_or_network_call():
    adapter = TestAdapter()
    adapter.is_external = True
    parsed = run_parse(adapter)
    assert adapter.requests == [] and not parsed.ai.attempted
    assert parsed.ai.status == "unavailable"


def test_disabled_provider_never_invoked():
    adapter = TestAdapter(error=AssertionError("must not be called"))
    parsed = run_parse(adapter, ai_provider="disabled")
    assert adapter.requests == [] and parsed.ai.status == "disabled"
    assert parsed.ai.attempted is False


def test_no_allowed_context_no_ai_request():
    adapter = TestAdapter()
    parsed = run_parse(adapter, "Name: Alice Win, 09791234567, COD 25000, Hlaing, product: dress")
    assert adapter.requests == [] and parsed.ai.status == "not_requested"


def test_privacy_redaction_names_phones_amounts_email_accounts_and_unlabelled_names():
    adapter = TestAdapter()
    run_parse(
        adapter,
        "Alice Unlabelled, name: Alice Win, phone: ၀၉၇၉၁၂၃၄၅၆၇, Hlaing, COD ၂၅၀၀၀, "
        "address: behind Alice Win stall, address: call +95 9 421 234 567 behind school, "
        "note: knock first, bank account: 1234567890, password: private, "
        "address: beside alice@example.com https://secret.example/private school",
    )
    assert len(adapter.requests) == 1
    payload = adapter.requests[0].model_dump_json()
    for private in [
        "Alice",
        "09791234567",
        "421",
        "25000",
        "1234567890",
        "private",
        "alice@example.com",
        "https://secret.example",
    ]:
        assert private not in payload
    assert "behind" in payload and "school" in payload
    assert set(adapter.requests[0].model_dump()) == {"township", "fragments", "requested_fields"}


def test_evidence_cannot_cross_a_redacted_name_span():
    def output(payload):
        fragment = payload.fragments[0]
        return json.dumps({"landmark": suggestion("stall", fragment.text, fragment.id)})

    parsed = run_parse(
        TestAdapter(output), "name: Alice Win, 09791234567, Hlaing, address: behind Alice Win stall"
    )
    assert parsed.ai.status == "invalid_response" and parsed.address.landmark is None


def test_payload_limits_and_oversized_private_input():
    adapter = TestAdapter()
    run_parse(
        adapter,
        "09791234567, Hlaing, " + ", ".join("address: behind gate " + str(i) for i in range(20)),
        ai_max_input_chars=128,
    )
    payload = adapter.requests[0]
    assert len(payload.fragments) <= 8
    assert sum(len(f.text) for f in payload.fragments) <= 128
    oversized = TestAdapter()
    parsed = run_parse(oversized, "09791234567, Hlaing, address: " + "s" * 600)
    assert parsed.ai.status == "not_requested" and oversized.requests == []


def test_encoding_uncertainty_blocks_enrichment(monkeypatch):
    class Uncertain:
        def get_zawgyi_probability(self, text):
            return 0.5

    monkeypatch.setattr("app.parsing.normalization.detector", lambda: Uncertain())
    adapter = TestAdapter()
    parsed = run_parse(adapter, "09791234567, လှိုင်မြို့နယ်, address: behind school")
    assert parsed.ai.status == "privacy_blocked" and adapter.requests == []
    assert parsed.confidence == "RED"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hlaing, address: behind red gate", "RED"),
        ("09791234567, Unknown Township, address: behind red gate", "RED"),
        ("09791234567, Hlaing, address: behind red gate", "AMBER"),
    ],
)
def test_enrichment_does_not_override_rule_triage(text, expected):
    parsed = run_parse(TestAdapter(json.dumps({"landmark": suggestion()})), text)
    assert parsed.confidence == expected


def test_ai_unavailable_does_not_create_false_green():
    parsed = run_parse(TestAdapter(error=RuntimeError("provider failed")))
    assert parsed.confidence == "AMBER"
    assert parsed.location_verification.status == "unverified"


def test_existing_trusted_green_and_ai_review_are_deterministic():
    from test_rules_parser import trusted_fixture

    settings = Settings(_env_file=None, parser_mode="hybrid")
    app = create_app(
        settings,
        location_catalog=trusted_fixture(),
        extraction_provider=TestAdapter(json.dumps({"landmark": suggestion()})),
    )
    with TestClient(app) as client:
        green = client.post(
            "/api/orders/parse", json={"raw_text": "09791234567, Hlaing, Fixture Road"}
        ).json()
        assert green["confidence"] == "GREEN" and not green["manual_review_required"]
        assisted = client.post(
            "/api/orders/parse",
            json={"raw_text": "09791234567, Hlaing, Fixture Road, address: behind red gate"},
        ).json()
        assert assisted["confidence"] == "AMBER" and assisted["manual_review_required"]
        assert assisted["field_sources"]["landmark"]["verified"] is False


def test_switching_configuration_and_dependency_injection(monkeypatch):
    monkeypatch.setenv("LANNPYA_AI_PROVIDER", "disabled")
    settings = Settings(_env_file=None)
    assert isinstance(create_extraction_provider(settings), DisabledExtractionProvider)
    monkeypatch.setenv("LANNPYA_AI_PROVIDER", "mock")
    assert isinstance(create_extraction_provider(Settings(_env_file=None)), MockExtractionProvider)
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_extraction_provider] = lambda: TestAdapter(
        json.dumps({"landmark": suggestion()})
    )
    with TestClient(app) as client:
        response = client.post("/api/orders/parse", json={"raw_text": BASE})
    assert response.json()["address"]["landmark"] == "red gate"


@pytest.mark.parametrize("value", [0, -1, 31, float("nan"), float("inf")])
def test_timeout_configuration_validation(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_timeout_seconds=value)


def test_backward_compatible_response_and_request_contract():
    parsed = run_parse()
    assert set(parsed.address.model_dump()) == {
        "customer_name",
        "phone_number",
        "township",
        "street",
        "landmark",
        "building_floor_unit",
        "cod_amount",
        "delivery_instructions",
        "time_window",
    }
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert (
            client.post(
                "/api/orders/parse", json={"raw_text": BASE, "ai_provider": "anything"}
            ).status_code
            == 422
        )
        assert client.get("/health").json() == {"status": "ok", "service": "LannPya AI"}
        assert client.post("/api/orders/parse", json={"raw_text": " "}).status_code == 422
        assert client.post("/api/orders/parse", json={"raw_text": "x" * 10001}).status_code == 422


def test_broken_adapter_metadata_is_a_private_degradation(caplog):
    class Broken(TestAdapter):
        @property
        def name(self):
            raise RuntimeError("sk-private 09791234567")

    parsed = run_parse(Broken())
    assert parsed.ai.status == "unavailable" and parsed.address.phone_number == "09791234567"
    assert "sk-private" not in caplog.text and "09791234567" not in caplog.text


def test_previously_extracted_notes_are_not_unnecessarily_sent():
    adapter = TestAdapter()
    run_parse(adapter, BASE + ", note: keep out of sunlight")
    payload = adapter.requests[0].model_dump_json()
    assert "sunlight" not in payload and "delivery_instructions" not in payload


def test_unicode_redaction_and_source_offsets_after_emoji():
    text = "အမည်: မလှ၊ ၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ COD ၂၅၀၀၀၊ 😀 address: behind မလှ red gate"

    def output(payload):
        assert "မလှ" not in payload.model_dump_json()
        return json.dumps({"landmark": suggestion(quote="red gate")})

    parsed = run_parse(TestAdapter(output), text)
    assert parsed.ai.status == "available" and parsed.address.landmark == "red gate"
    evidence = parsed.field_sources["landmark"].evidence[0]
    assert parsed.normalized_text[evidence.start : evidence.end] == "red gate"


def test_ai_landmark_is_not_automatically_verified_even_if_catalog_name_matches():
    from app.parsing.places import LocationCatalog, TrustedLocation

    catalog = LocationCatalog(
        (
            TrustedLocation(
                township="Hlaing",
                field="landmark",
                name="red gate",
                dataset="synthetic-only",
                source_url="https://example.test/red-gate",
            ),
        )
    )
    app = create_app(
        Settings(_env_file=None),
        location_catalog=catalog,
        extraction_provider=TestAdapter(json.dumps({"landmark": suggestion()})),
    )
    with TestClient(app) as client:
        data = client.post("/api/orders/parse", json={"raw_text": BASE}).json()
    assert data["confidence"] == "AMBER" and data["manual_review_required"]
    assert data["field_sources"]["landmark"]["verified"] is False


def test_request_cancellation_is_not_hidden_as_provider_unavailability():
    from app.ai.extraction import SanitizedAddressInput, SanitizedFragment
    from app.ai.gateway import ExtractionGateway

    async def cancelled_run():
        payload = SanitizedAddressInput(
            fragments=(SanitizedFragment(id="fragment_0", text="gate"),),
            requested_fields=("landmark",),
        )
        task = asyncio.create_task(ExtractionGateway(TestAdapter(delay=10), 1).extract(payload))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancelled_run())


def test_ai_failure_on_a_trusted_street_still_requires_manual_review():
    from test_rules_parser import trusted_fixture

    app = create_app(
        Settings(_env_file=None),
        location_catalog=trusted_fixture(),
        extraction_provider=TestAdapter(error=RuntimeError("private failure")),
    )
    with TestClient(app) as client:
        data = client.post(
            "/api/orders/parse",
            json={"raw_text": "09791234567, Hlaing, Fixture Road, address: behind red gate"},
        ).json()
    assert data["confidence"] == "GREEN"  # Independent, trusted deterministic street evidence.
    assert data["ai"]["status"] == "unavailable" and data["manual_review_required"]


def test_all_grounding_is_validated_before_any_field_is_merged():
    output = {"landmark": suggestion(), "building_floor_unit": suggestion("invented floor")}
    data = run_parse(TestAdapter(json.dumps(output)))
    assert data.ai.status == "invalid_response"
    assert data.address.landmark is None and data.address.building_floor_unit is None
    assert data.ai.applied_fields == []
