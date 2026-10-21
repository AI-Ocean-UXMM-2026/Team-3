import asyncio
import json
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.ai.adapters.http import HTTPExtractionProvider
from app.ai.extraction import AIExtractionResponse, SanitizedAddressInput, SanitizedFragment
from app.ai.factory import create_extraction_provider
from app.ai.gateway import ExtractionGateway
from app.ai.sanitization import prepare_ai_request
from app.api.routes import get_extraction_provider
from app.core.config import Settings
from app.main import create_app
from app.parsing.normalization import normalize_text
from app.schemas.orders import ParseResponse


def payload():
    return SanitizedAddressInput(
        township="Hlaing",
        fragments=(SanitizedFragment(id="fragment_0", text="address: behind fictional red gate"),),
        requested_fields=("landmark",),
    )


def configuration(**extra):
    return Settings(
        _env_file=None,
        ai_provider="gemini",
        ai_model="operator-selected-model",
        ai_api_key="fictional-test-key",
        **extra,
    )


def run(provider, *, enabled=True):
    return asyncio.run(ExtractionGateway(provider, 0.2, allow_external=enabled).extract(payload()))


def test_default_provider_and_direct_adapter_never_make_an_external_call():
    calls = []
    adapter = HTTPExtractionProvider(
        configuration(), transport=httpx.MockTransport(lambda r: calls.append(r))
    )
    assert run(adapter, enabled=False).availability.status == "unavailable"
    assert run(adapter).availability.status == "unavailable"  # Adapter guard also fails closed.
    assert calls == []


@pytest.mark.parametrize("provider", ["gemini", "json_http"])
def test_provider_factory_selection_and_model_are_configuration_only(provider):
    selected = create_extraction_provider(
        Settings(_env_file=None, ai_provider=provider, ai_model="chosen")
    )
    assert selected.name == provider
    assert selected.settings.ai_model == "chosen"
    assert not selected.settings.ai_external_requests_enabled


def test_gemini_wire_contract_and_grounded_schema_are_validated_without_network():
    calls = []
    suggestion = {
        "landmark": {
            "value": "fictional red gate",
            "quote": "behind fictional red gate",
            "fragment_id": "fragment_0",
        }
    }

    def handle(request):
        calls.append(json.loads(request.content))
        assert request.headers["x-goog-api-key"] == "fictional-test-key"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(suggestion)}]},
                    }
                ]
            },
        )

    adapter = HTTPExtractionProvider(
        configuration(ai_external_requests_enabled=True), transport=httpx.MockTransport(handle)
    )
    result = run(adapter)
    assert result.availability.status == "available" and not result.availability.is_mock
    assert result.output.landmark.value == "fictional red gate"
    assert (
        calls[0]["generationConfig"]["responseFormat"]["text"]["schema"]["additionalProperties"]
        is False
    )
    assert "09790000000" not in json.dumps(calls)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"latitude":16.8}',
        '{"phone_number":"09790000000"}',
        '{"cod_amount":1}',
        '{"landmark":{"value":"invented"}}',
        '{"landmark":null,"landmark":null}',
    ],
)
def test_malformed_extra_and_protected_model_fields_are_rejected(raw):
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": raw}]}}]},
        )
    )
    result = run(
        HTTPExtractionProvider(
            configuration(ai_external_requests_enabled=True), transport=transport
        )
    )
    assert result.availability.status == "invalid_response"
    assert result.output is None


@pytest.mark.parametrize(
    "code,status",
    [(429, "rate_limited"), (401, "unavailable"), (500, "unavailable"), (302, "unavailable")],
)
def test_upstream_failures_do_not_disclose_payload_or_secret(code, status, caplog):
    transport = httpx.MockTransport(
        lambda r: httpx.Response(code, headers={"Retry-After": "9"}, text="fictional-test-key")
    )
    result = run(
        HTTPExtractionProvider(
            configuration(ai_external_requests_enabled=True), transport=transport
        )
    )
    assert result.availability.status == status
    assert "fictional-test-key" not in result.availability.model_dump_json() + caplog.text


def test_timeout_degrades_safely():
    def timeout(request):
        raise httpx.ReadTimeout("fictional-test-key")

    result = run(
        HTTPExtractionProvider(
            configuration(ai_external_requests_enabled=True), transport=httpx.MockTransport(timeout)
        )
    )
    assert result.availability.status == "timeout"


def test_generic_https_adapter_uses_same_response_schema():
    settings = Settings(
        _env_file=None,
        ai_provider="json_http",
        ai_model="chosen-model",
        ai_api_key="fictional-test-key",
        ai_endpoint="https://inference.example.invalid/extract",
        ai_external_requests_enabled=True,
    )

    def handle(request):
        body = json.loads(request.content)
        assert body["model"] == "chosen-model" and body["input"]["requested_fields"] == ["landmark"]
        assert "phone_number" not in body["response_schema"]["properties"]
        return httpx.Response(200, json={"output": {}})

    assert (
        run(
            HTTPExtractionProvider(settings, transport=httpx.MockTransport(handle))
        ).availability.status
        == "available"
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.invalid/extract",
        "https://user:password@example.invalid",
        "https://example.invalid/?key=secret",
    ],
)
def test_unsafe_custom_endpoint_never_calls_transport(endpoint):
    settings = Settings(
        _env_file=None,
        ai_provider="json_http",
        ai_model="chosen",
        ai_api_key="fictional-key",
        ai_endpoint=endpoint,
        ai_external_requests_enabled=True,
    )
    calls = []
    assert (
        run(
            HTTPExtractionProvider(
                settings, transport=httpx.MockTransport(lambda r: calls.append(r))
            )
        ).availability.status
        == "unavailable"
    )
    assert calls == []


def test_privacy_builder_omits_registered_personal_fields_before_future_adapter():
    with TestClient(create_app(Settings(_env_file=None, parser_mode="rules"))) as client:
        parsed = ParseResponse.model_validate(
            client.post(
                "/api/orders/parse",
                json={
                    "raw_text": (
                        "name: Fictional Buyer, phone: 09790000000, Hlaing, COD 25000, "
                        "address: behind fictional red gate"
                    )
                },
            ).json()
        )
    prepared = prepare_ai_request(parsed, 2000)
    assert prepared is not None
    wire = prepared.payload.model_dump_json()
    for private in ("Fictional Buyer", "09790000000", "25000"):
        assert private not in wire


def test_benchmark_labels_are_verbatim_and_scheduling_is_separate():
    rows = json.loads(
        (Path(__file__).parent / "fixtures/phase16_ai_benchmark.json").read_text(encoding="utf-8")
    )
    assert len(rows) >= 10
    for row in rows:
        AIExtractionResponse.model_validate(row["expected_ai"], strict=True)
        for value in row["expected_ai"].values():
            if value:
                assert value["value"] in value["quote"] and value["quote"] in row["text"]
        assert "latitude" not in row["expected_ai"]
    assert any(r.get("expected_time_expression") for r in rows)


@pytest.mark.parametrize("index", [6, 7])
def test_labeled_time_expressions_use_existing_deterministic_rules(index):
    rows = json.loads(
        (Path(__file__).parent / "fixtures/phase16_ai_benchmark.json").read_text(encoding="utf-8")
    )
    row = rows[index]
    with TestClient(create_app(Settings(_env_file=None, parser_mode="rules"))) as client:
        result = client.post("/api/orders/parse", json={"raw_text": row["text"]}).json()
    assert result["address"]["time_window"] == normalize_text(row["expected_time_expression"])[0]


def test_hallucinated_optional_field_is_not_merged_and_deterministic_values_survive():
    settings = configuration(ai_external_requests_enabled=True)
    raw = json.dumps(
        {
            "landmark": {
                "value": "Invented Palace",
                "quote": "behind red gate",
                "fragment_id": "fragment_0",
            }
        }
    )
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": raw}]}}]},
        )
    )
    application = create_app(settings)
    application.dependency_overrides[get_extraction_provider] = lambda: HTTPExtractionProvider(
        settings, transport=transport
    )
    with TestClient(application) as client:
        result = client.post(
            "/api/orders/parse",
            json={"raw_text": "09790000000, Hlaing, COD 12345, address: behind red gate"},
        ).json()
    assert result["ai"]["status"] == "invalid_response"
    assert result["address"]["phone_number"] == "09790000000"
    assert result["address"]["cod_amount"] == 12345
    assert result["address"]["landmark"] != "Invented Palace"


@pytest.mark.parametrize(
    "content",
    [
        b"x" * 65537,
        b'{"candidates":[]}',
        b'{"candidates":[],"candidates":[]}',
        b'{"candidates":[{"finishReason":"MAX_TOKENS"}]}',
    ],
    ids=["oversized", "empty", "duplicate-key", "truncated"],
)
def test_oversized_incomplete_or_ambiguous_provider_envelopes_fail_closed(content):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    result = run(
        HTTPExtractionProvider(
            configuration(ai_external_requests_enabled=True), transport=transport
        )
    )
    assert result.availability.status == "unavailable"
