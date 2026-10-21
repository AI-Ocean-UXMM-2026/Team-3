import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.base import AddressProvider, AIProviderError, ProviderInput, ProviderOutput
from app.ai.mock import MockAddressProvider
from app.core.config import Settings
from app.main import create_app
from app.schemas.orders import AddressFields, ParseResponse


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None, parser_mode="mock"))) as client:
        yield client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "LannPya AI"}


@pytest.mark.parametrize(
    "text",
    [
        "လှိုင်မြို့နယ် ဗဟိုလမ်း အဆွေတော်နား",
        "Hlaing, Baho Road",
        " a ",
        "x" * 10000,
    ],
)
def test_valid_mock_parse(client, text):
    response = client.post("/api/orders/parse", json={"raw_text": text})
    assert response.status_code == 200
    result = ParseResponse.model_validate(response.json())
    assert result.is_mock is True
    assert result.provider == "mock"
    assert "MOCK DATA" in result.notice
    assert result.confidence == "RED"
    assert all(value is None for value in result.address.model_dump().values())
    assert {reason.code for reason in result.validation_reasons} == {
        "MOCK_NOT_VERIFIED",
        "MISSING_PHONE_NUMBER",
        "MISSING_TOWNSHIP",
    }
    assert "raw_text" not in response.json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"raw_text": ""},
        {"raw_text": " \n\t "},
        {"raw_text": None},
        {"raw_text": 123},
        {"raw_text": True},
        {"raw_text": []},
        {"raw_text": "x" * 10001},
        {"raw_text": "hello", "unexpected": "private"},
    ],
)
def test_invalid_requests(client, payload):
    response = client.post("/api/orders/parse", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]
    assert all(set(item) == {"location", "message", "type"} for item in error["details"])
    assert "private" not in response.text


def test_invalid_json(client):
    response = client.post(
        "/api/orders/parse",
        content='{"raw_text":',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_provider_interface_and_mock():
    with pytest.raises(TypeError):
        AddressProvider()
    result = asyncio.run(MockAddressProvider().parse(ProviderInput(raw_text="hello")))
    assert isinstance(result, ProviderOutput)
    assert result.is_mock
    assert result.address == AddressFields()


def test_provider_schemas_validate():
    with pytest.raises(ValidationError):
        ProviderInput(raw_text=" ")
    with pytest.raises(ValidationError):
        ProviderOutput(address={"cod_amount": -1}, is_mock=True)
    with pytest.raises(ValidationError):
        ProviderOutput(address={}, is_mock="true")


class BrokenProvider(AddressProvider):
    @property
    def name(self):
        return "test"

    async def parse(self, request):
        raise AIProviderError("private upstream details")


class InvalidProvider(BrokenProvider):
    async def parse(self, request):
        return {"address": {"cod_amount": -1}, "is_mock": True}


class RealProvider(BrokenProvider):
    async def parse(self, request):
        return ProviderOutput(address=AddressFields(), is_mock=False)


class UnexpectedProvider(BrokenProvider):
    async def parse(self, request):
        raise RuntimeError("private upstream details")


@pytest.mark.parametrize("provider", [BrokenProvider(), InvalidProvider(), RealProvider()])
def test_provider_failure_and_injection(provider):
    with TestClient(create_app(Settings(_env_file=None, parser_mode="mock"), provider)) as client:
        response = client.post("/api/orders/parse", json={"raw_text": "hello"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_PROVIDER_ERROR"
    assert "private" not in response.text


def test_unexpected_error_is_sanitized():
    with TestClient(
        create_app(Settings(_env_file=None, parser_mode="mock"), UnexpectedProvider()),
        raise_server_exceptions=False,
    ) as client:
        response = client.post("/api/orders/parse", json={"raw_text": "hello"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private" not in response.text


def test_configurable_cors():
    origin = "http://localhost:4321"
    with TestClient(create_app(Settings(_env_file=None, cors_origins=[origin]))) as client:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/orders/parse", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        headers["Origin"] = "https://untrusted.example"
        response = client.options("/api/orders/parse", headers=headers)
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_cors_on_validation_error(client):
    response = client.post(
        "/api/orders/parse", json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_provider_configuration(monkeypatch):
    monkeypatch.setenv("LANNPYA_AI_PROVIDER", "unimplemented")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_environment_configuration(monkeypatch):
    monkeypatch.setenv("LANNPYA_CORS_ORIGINS", '["http://localhost:4321"]')
    assert Settings(_env_file=None).cors_origins == ["http://localhost:4321"]


@pytest.mark.parametrize(
    "origin", ["*", "file://local", "http://localhost/path", "http://u:p@localhost"]
)
def test_invalid_cors_configuration(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


def test_http_errors_and_openapi(client):
    assert client.get("/missing").json()["error"]["code"] == "HTTP_ERROR"
    assert client.get("/api/orders/parse").status_code == 405
    schema = client.get("/openapi.json").json()
    assert "ParseResponse" in schema["components"]["schemas"]
    assert "ErrorResponse" in schema["components"]["schemas"]
