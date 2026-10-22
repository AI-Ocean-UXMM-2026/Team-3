"""All HTTP responses here are fictional MockTransport responses; no Google calls."""

import json

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.routing.base import RoutingFailure
from tools import google_demo_route as demo


def settings(**changes):
    return Settings(
        _env_file=None,
        **{
            "environment": "test",
            "routing_provider": "google",
            "routing_external_requests_enabled": True,
            "google_routes_api_key": SecretStr("synthetic-test-credential"),
            "buyer_otp_mode": "twilio",
            "buyer_otp_external_sends_enabled": True,
            "buyer_twilio_account_sid": "ACsynthetic-test-only",
            "buyer_twilio_auth_token": SecretStr("synthetic-test-only"),
            "buyer_twilio_verify_service_sid": "VAsynthetic-test-only",
            **changes,
        },
    )


def valid_response():
    return {
        "routes": [
            {
                "distanceMeters": 1700,
                "duration": "345.25s",
                "polyline": {
                    "geoJsonLinestring": {
                        "type": "LineString",
                        "coordinates": [
                            [96.13, 16.825],
                            [96.128, 16.819],
                            [96.125, 16.815],
                        ],
                    },
                },
            }
        ]
    }


def run(tmp_path, handler, **kwargs):
    return demo.execute(
        settings(),
        demo_confirmed=True,
        ledger=tmp_path / "attempt.json",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_plan_is_network_free_and_fixed(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["google_demo_route"])
    monkeypatch.setattr(demo, "load_key", lambda: None)
    monkeypatch.setattr(httpx.Client, "stream", lambda *a, **k: pytest.fail("network forbidden"))
    assert demo.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data["observation"] == "NOT_EXECUTED"
    assert data["maximum_requests"] == 1 and data["matrix_elements"] == 0
    assert data["mode"] == "DRIVE" and data["routing_preference"] == "TRAFFIC_UNAWARE"


def test_exact_request_and_geojson_decoding(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == demo.ENDPOINT and request.method == "POST"
        assert request.headers["X-Goog-FieldMask"] == demo.MASK
        body = json.loads(request.content)
        assert body["travelMode"] == "DRIVE"
        assert body["polylineEncoding"] == "GEO_JSON_LINESTRING"
        assert "trafficModel" not in body and "intermediates" not in body
        assert json.loads((tmp_path / "attempt.json").read_text())["reserved_requests"] == 1
        return httpx.Response(200, json=valid_response())

    result = run(tmp_path, handler)
    assert len(calls) == 1
    assert result["observation"] == "MOCK_HTTP"  # Never claims mock transport is Google live.
    assert result["route"]["duration_seconds"] == 346
    assert result["route"]["geometry"]["coordinates"][0] == [96.13, 16.825]
    assert result["route"]["quality"] == "ROAD_STATIC"
    assert result["route"]["traffic_aware"] is False


def test_reserved_attempt_cannot_be_retried_across_instances(tmp_path):
    run(tmp_path, lambda r: httpx.Response(200, json=valid_response()))
    result = run(tmp_path, lambda r: pytest.fail("second request forbidden"))
    assert result["error"] == "REQUEST_ALREADY_RESERVED_NO_RETRY"
    assert result["external_attempts"] == 0


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429, 500, 503])
def test_errors_are_sanitized_no_retry(tmp_path, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            code,
            json={
                "error": {
                    "code": code,
                    "status": "PERMISSION_DENIED",
                    "message": "Do not leak synthetic-test-credential or provider URLs",
                    "details": [
                        {"reason": "API_KEY_SERVICE_BLOCKED", "metadata": {"key": "secret"}}
                    ],
                }
            },
        )

    result = run(tmp_path, handler)
    assert len(calls) == 1 and result["external_attempts"] == 1
    assert result["http_status"] == code and result["observation"] == "NOT_VERIFIED"
    assert result["google_error"] == {
        "code": code,
        "status": "PERMISSION_DENIED",
        "reasons": ["API_KEY_SERVICE_BLOCKED"],
    }
    assert "synthetic-test-credential" not in json.dumps(result)
    assert "metadata" not in json.dumps(result)


def test_timeout_is_not_retried(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("private credential in exception must not escape")

    result = run(tmp_path, handler)
    assert result["error"] == "ROUTING_TIMEOUT" and len(calls) == 1
    assert "private credential" not in json.dumps(result)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"routes": []},
        {"routes": [{}]},
        {
            "routes": [{"distanceMeters": 10, "duration": "oops", "polyline": {}}],
        },
        {"routes": [{"distanceMeters": -1, "duration": "10s", "polyline": {}}]},
    ],
)
def test_invalid_provider_response_never_claims_success(tmp_path, data):
    result = run(tmp_path, lambda r: httpx.Response(200, json=data))
    assert result["observation"] == "NOT_VERIFIED" and "route" not in result


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"routing_external_requests_enabled": False}, "EXTERNAL_ROUTING_DISABLED"),
        ({"google_routes_api_key": None}, "ROUTING_KEY_MISSING"),
    ],
)
def test_existing_gates_fail_before_reservation(tmp_path, changes, expected):
    path = tmp_path / "attempt.json"
    result = demo.execute(
        settings(**changes),
        demo_confirmed=True,
        ledger=path,
        transport=httpx.MockTransport(lambda r: pytest.fail("network forbidden")),
    )
    assert result["error"] == expected and not path.exists()


def test_demo_confirmation_required(tmp_path):
    with pytest.raises(RoutingFailure, match="DEMO_KEY_CONFIRMATION_REQUIRED"):
        demo.execute(settings(), ledger=tmp_path / "attempt.json")


def test_production_forbidden(tmp_path):
    with pytest.raises(RoutingFailure, match="LOCAL_GOOGLE_CONFIGURATION_REQUIRED"):
        demo.execute(
            settings(environment="production"),
            demo_confirmed=True,
            ledger=tmp_path / "attempt.json",
        )


def test_no_matrix_and_no_second_call(tmp_path):
    provider = demo.SingleRequestProvider(
        settings(),
        tmp_path / "attempt.json",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=valid_response())),
    )
    with pytest.raises(RoutingFailure, match="MATRIX_FORBIDDEN"):
        provider.get_route_matrix(None)
    provider.get_route(demo.QUERY)
    with pytest.raises(RoutingFailure, match="ONE_REQUEST_LIMIT_REACHED"):
        provider.get_route(demo.QUERY)


def test_masked_entry_refuses_piped_input(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(RoutingFailure, match="MASKED_INTERACTIVE_TERMINAL_REQUIRED"):
        demo.store_key()


@pytest.mark.parametrize("existing_file", [False, True])
def test_store_key_command_writes_only_private_dummy_file(
    tmp_path, monkeypatch, capsys, existing_file
):
    private_file = tmp_path / ".env.google-demo.local"
    dummy_key = "dummy-regression-key-not-a-real-credential"
    if existing_file:
        private_file.write_text("GOOGLE_ROUTES_API_KEY=previous-dummy\n", encoding="utf-8")
    prompts = []
    monkeypatch.setattr(demo, "PRIVATE_ENV", private_file)
    monkeypatch.setattr("sys.argv", ["google_demo_route", "--store-key"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        demo.subprocess,
        "run",
        lambda *args, **kwargs: demo.subprocess.CompletedProcess(args, 0),
    )

    def hidden_input(prompt):
        prompts.append(prompt)
        return dummy_key

    monkeypatch.setattr(demo.getpass, "getpass", hidden_input)
    monkeypatch.setattr(demo, "load_key", lambda: pytest.fail("Storage must not read back keys"))
    monkeypatch.setattr(demo, "execute", lambda *a, **k: pytest.fail("No Google calls permitted"))

    assert demo.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"key_stored": True, "external_requests": 0}
    assert dummy_key not in captured.out + captured.err
    assert len(prompts) == 1  # Entry still goes through getpass, not input().
    # This is exclusively a temporary test file containing a dummy credential.
    assert private_file.read_text(encoding="utf-8") == (
        "# Private backend-only Demo Key. Live calls remain disabled.\n"
        f"GOOGLE_ROUTES_API_KEY={dummy_key}\n"
    )
    assert list(tmp_path.iterdir()) == [private_file]


def test_private_file_is_loaded_without_activating_external_calls(tmp_path, monkeypatch):
    path = tmp_path / ".env.private"
    path.write_text("GOOGLE_ROUTES_API_KEY=synthetic-only-key\n", encoding="utf-8")
    monkeypatch.setattr(demo, "PRIVATE_ENV", path)
    for name in ("LANNPYA_GOOGLE_ROUTES_API_KEY", "GOOGLE_ROUTES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert demo.load_key().get_secret_value() == "synthetic-only-key"
    assert "synthetic-only-key" not in repr(demo.load_key())


def test_error_details_with_unexpected_shapes():
    assert demo.safe_error({"error": {"details": [{"reason": []}, None]}}) == {"reasons": []}
    assert demo.safe_error({"error": "unexpected"}) == {}


def test_encoded_geometry_request_uses_only_three_fields_and_one_attempt(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["X-Goog-FieldMask"] == demo.ENCODED_MASK
        body = json.loads(request.content)
        assert body["polylineEncoding"] == "ENCODED_POLYLINE"
        assert body["travelMode"] == "DRIVE"
        assert body["routingPreference"] == "TRAFFIC_UNAWARE"
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "distanceMeters": 1000,
                        "duration": "120s",
                        "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                    }
                ]
            },
        )

    result = demo.execute(
        settings(),
        demo_confirmed=True,
        ledger=tmp_path / "encoded-attempt.json",
        encoded_geometry=True,
        transport=httpx.MockTransport(handler),
    )
    assert result["observation"] == "MOCK_HTTP" and len(calls) == 1
    assert result["route"]["geometry"]["coordinates"] == [
        [-120.2, 38.5],
        [-120.95, 40.7],
        [-126.453, 43.252],
    ]


@pytest.mark.parametrize("value", ["", "_", "!", "???????????????~", None])
def test_invalid_encoded_geometry_rejected(value):
    with pytest.raises(ValueError):
        demo.decode_polyline(value)
