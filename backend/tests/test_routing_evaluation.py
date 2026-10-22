"""No live network: synthetic fixtures, explicit prices and MockTransport only."""

import json
from datetime import date
from decimal import Decimal

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.routing.base import RoutingFailure
from app.routing.http import HTTPProvider
from app.schemas.routing import Coordinate, MatrixQuery, RouteQuery
from tools.routing_evaluation import evaluate as lab


def config(provider="google", modes=None, **overrides):
    modes = modes or ["DRIVE"]
    prices = {
        m: {
            "route_per_request": ".01" if m == "DRIVE" else ".03",
            "matrix_unit_price": ".001" if m == "DRIVE" else ".005",
            "matrix_billing_unit": "ELEMENT" if provider == "google" else "REQUEST",
            "route_sku": "TEST_ONLY_ROUTE_" + m,
            "matrix_sku": "TEST_ONLY_MATRIX_" + m,
        }
        for m in modes
    }
    return lab.EvaluationSettings(
        provider=provider,
        modes=modes,
        **{
            "live_enabled": True,
            "max_requests": 7 * len(modes),
            "max_matrix_elements": 49 * len(modes),
            "max_estimated_cost": "1",
            "pricing": {
                "currency": "USD",
                "reviewed_on": date.today(),
                "source": "TEST_RATES_ONLY_NOT_PROVIDER_PRICING",
                "modes": prices,
            },
            **overrides,
        },
    )


def settings(**values):
    return Settings(
        _env_file=None,
        **{
            "environment": "test",
            "routing_external_requests_enabled": True,
            "google_routes_api_key": "synthetic-provider-key",
            "ors_api_key": "synthetic-ors-key",
            "routing_two_wheeler_enabled": True,
            **values,
        },
    )


def response(request):
    body = json.loads(request.content)
    if "computeRoutes" in str(request.url):
        assert body["polylineQuality"] == "OVERVIEW" and not body["computeAlternativeRoutes"]
        assert body["routingPreference"] == "TRAFFIC_UNAWARE"
        assert "*" not in request.headers["X-Goog-FieldMask"]
        a, b = [body[k]["location"]["latLng"] for k in ("origin", "destination")]
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "distanceMeters": 1111,
                        "duration": "123.1s",
                        "polyline": {
                            "geoJsonLinestring": {
                                "type": "LineString",
                                "coordinates": [[p["longitude"], p["latitude"]] for p in [a, b]],
                            }
                        },
                    }
                ]
            },
        )
    if "computeRouteMatrix" in str(request.url):
        assert "status" in request.headers["X-Goog-FieldMask"]
        n, m = len(body["origins"]), len(body["destinations"])
        cells = [
            {
                "originIndex": i,
                "destinationIndex": j,
                "status": {},
                "condition": "ROUTE_EXISTS",
                "distanceMeters": 0 if i == j else i * 100 + j,
                "duration": "0s" if i == j else f"{i * 10 + j}s",
            }
            for i in range(n)
            for j in range(m)
        ]
        # Out-of-order streamed elements must be placed by explicit indices.
        cells[0].pop("originIndex")
        cells[0].pop("destinationIndex")
        cells[n - 1] = {"originIndex": 0, "destinationIndex": n - 1, "condition": "ROUTE_NOT_FOUND"}
        return httpx.Response(200, json=list(reversed(cells)))
    if "/directions/" in str(request.url):
        assert body["units"] == "m" and body["instructions"] is False
        assert body["coordinates"][0] == [96.13, 16.825]
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "geometry": {"type": "LineString", "coordinates": body["coordinates"]},
                        "properties": {"summary": {"distance": 1111, "duration": 123.1}},
                    }
                ]
            },
        )
    n = len(body["locations"])
    return httpx.Response(
        200,
        json={
            "distances": [[0 if i == j else i * 100 + j for j in range(n)] for i in range(n)],
            "durations": [[0 if i == j else i * 10 + j for j in range(n)] for i in range(n)],
        },
    )


def run(tmp_path, cfg=None, handler=response):
    return lab.evaluate(
        cfg or config(),
        settings(),
        execute_live=True,
        ledger_path=tmp_path / "budget.json",
        transport=httpx.MockTransport(handler),
    )


def test_default_is_plan_only_even_when_native_external_flag_is_on(monkeypatch):
    monkeypatch.setattr(HTTPProvider, "post", lambda *a, **k: pytest.fail("Unexpected HTTP"))
    report = lab.evaluate(lab.EvaluationSettings(), settings())
    assert report["status"] == "PLAN_ONLY" and report["http_requests_attempted"] == 0
    assert (
        report["quote"]["planned_http_requests"] == 7 and report["quote"]["matrix_elements"] == 49
    )
    assert report["quote"]["estimated_cost"] is None
    assert all(v["quality"] == "SIMULATED" for v in report["simulation"].values())


@pytest.mark.parametrize(
    "override,code",
    [
        ({"live_enabled": False}, "EVALUATION_LIVE_DISABLED"),
        ({"max_requests": 6}, "EVALUATION_REQUEST_LIMIT"),
        ({"max_matrix_elements": 48}, "EVALUATION_MATRIX_ELEMENT_LIMIT"),
        ({"max_stops": 5}, "EVALUATION_STOP_LIMIT"),
        ({"max_estimated_cost": ".108"}, "EVALUATION_COST_LIMIT"),
        ({"pricing": None}, "REVIEWED_PRICING_REQUIRED"),
    ],
)
def test_preflight_blocks_before_transport_or_ledger(tmp_path, override, code):
    calls = []
    with pytest.raises(lab.EvaluationBlocked, match=code):
        lab.evaluate(
            config(**override),
            settings(),
            execute_live=True,
            ledger_path=tmp_path / "new.json",
            transport=httpx.MockTransport(lambda r: calls.append(r)),
        )
    assert not calls and not (tmp_path / "new.json").exists()


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"routing_external_requests_enabled": False}, "EXTERNAL_ROUTING_DISABLED"),
        ({"google_routes_api_key": None}, "ROUTING_KEY_MISSING"),
        ({"environment": "production"}, "LOCAL_EVALUATION_ONLY"),
        ({"routing_max_stops": 5}, "EVALUATION_STOP_LIMIT"),
    ],
)
def test_native_security_gates_are_independent(overrides, code, tmp_path):
    with pytest.raises(lab.EvaluationBlocked, match=code):
        lab.evaluate(
            config(), settings(**overrides), execute_live=True, ledger_path=tmp_path / "x.json"
        )
    assert not (tmp_path / "x.json").exists()


def test_mock_google_counts_units_matrix_order_geometry_and_exact_money(tmp_path):
    report = run(tmp_path)
    assert report["status"] == "COMPLETE" and report["network"] == "MOCK_HTTP"
    assert not report["live_verified"] and report["http_requests_attempted"] == 7
    assert Decimal(report["estimated_cost_reserved"]) == Decimal(".109")
    matrix = report["provider_results"][-1]["result"]
    assert matrix["distances"][2][1] == 201 and matrix["durations"][1][2] == 12
    assert matrix["distances"][0][6] is None and matrix["unreachable_cells"] == 1
    route = report["provider_results"][0]
    assert route["result"]["geometry_available"] and route["result"]["duration_seconds"] == 124
    assert route["result"]["geometry_endpoint_offsets_meters"] == {"origin": 0, "destination": 0}
    assert "savings" in route["comparison"]["meaning"]
    encoded = json.dumps(report)
    assert "synthetic-provider-key" not in encoded
    assert "coordinates" not in json.dumps(report["provider_results"])
    ledger = json.loads((tmp_path / "budget.json").read_text())
    assert ledger["requests_reserved"] == 7 and ledger["matrix_elements_reserved"] == 49


def test_two_wheeler_uses_separate_reviewed_prices_and_native_gate(tmp_path):
    cfg = config(modes=["DRIVE", "TWO_WHEELER"])
    with pytest.raises(lab.EvaluationBlocked, match="TWO_WHEELER_NOT_ENABLED"):
        lab.evaluate(cfg, settings(routing_two_wheeler_enabled=False), execute_live=True)
    report = run(tmp_path, cfg)
    assert report["http_requests_attempted"] == 14 and report["matrix_elements_reserved"] == 98
    assert Decimal(report["estimated_cost_reserved"]) == Decimal(".534")


def test_ors_request_pricing_is_not_google_element_pricing(tmp_path):
    report = run(tmp_path, config(provider="ors"))
    assert report["http_requests_attempted"] == 7
    assert Decimal(report["estimated_cost_reserved"]) == Decimal(".061")
    with pytest.raises(ValidationError):
        config(provider="ors", modes=["TWO_WHEELER"])


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_account_and_provider_failures_stop_without_retries(tmp_path, status):
    calls = []

    def fail(r):
        calls.append(r)
        return httpx.Response(status, text="PRIVATE synthetic-provider-key")

    report = run(tmp_path, handler=fail)
    assert report["status"] == "STOPPED" and len(calls) == 1
    assert report["http_requests_attempted"] == 1 and Decimal(
        report["estimated_cost_reserved"]
    ) == Decimal(".01")
    assert "PRIVATE" not in json.dumps(report) and "synthetic-provider-key" not in json.dumps(
        report
    )


def test_timeout_and_malformed_json_are_not_simulation_fallbacks(tmp_path):
    def timeout(r):
        raise httpx.ReadTimeout("PRIVATE synthetic-provider-key")

    for i, handler in enumerate([timeout, lambda r: httpx.Response(200, text="not json")]):
        folder = tmp_path / str(i)
        folder.mkdir()
        report = run(folder, handler=handler)
        assert report["http_requests_attempted"] == 1 and report["status"] == "STOPPED"
        assert "result" not in report["provider_results"][0]
        assert all(v["quality"] == "SIMULATED" for v in report["simulation"].values())


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("max_requests", 1, "EVALUATION_REQUEST_LIMIT"),
        ("max_estimated_cost", Decimal(".01"), "EVALUATION_COST_LIMIT"),
        ("max_matrix_elements", 0, "EVALUATION_MATRIX_ELEMENT_LIMIT"),
    ],
)
def test_each_http_attempt_rechecks_budget_after_preflight(tmp_path, field, value, code):
    cfg = config()
    calls = []

    def changed(r):
        calls.append(r)
        setattr(cfg, field, value)
        return response(r)

    report = run(tmp_path, cfg, changed)
    assert report["status"] == "STOPPED" and report["stop_code"] == code
    assert len(calls) == (6 if field == "max_matrix_elements" else 1)


def test_existing_ledger_prevents_accidental_reexecution(tmp_path):
    (tmp_path / "budget.json").write_text("existing review ledger")
    with pytest.raises(lab.EvaluationBlocked, match="ALREADY_STARTED"):
        run(tmp_path, handler=lambda r: pytest.fail("Unexpected HTTP"))
    assert (tmp_path / "budget.json").read_text() == "existing review ledger"


@pytest.mark.parametrize(
    "code,normalized",
    [
        (2009, "ROUTE_NOT_FOUND"),
        (2010, "ROUTING_POINT_NOT_FOUND"),
        (6010, "ROUTING_POINT_NOT_FOUND"),
    ],
)
def test_ors_missing_roads_are_safe_typed_failures(code, normalized):
    p = HTTPProvider(
        settings(routing_provider="ors"),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(404, json={"error": {"code": code, "message": "PRIVATE key"}})
        ),
    )
    data = lab.dataset()
    with pytest.raises(RoutingFailure, match=normalized) as e:
        p.get_route(RouteQuery(origin=data.hub, destination=data.deliveries[0].point))
    assert "PRIVATE" not in str(e.value)


def test_unreachable_probe_is_recorded_without_fake_success(tmp_path):
    calls = []

    def first_missing(r):
        calls.append(r)
        return (
            httpx.Response(404, json={"error": {"code": 2009}}) if len(calls) == 1 else response(r)
        )

    report = run(tmp_path, config(provider="ors"), first_missing)
    assert report["status"] == "COMPLETED_WITH_PROVIDER_ERRORS" and len(calls) == 7
    assert report["provider_results"][0]["error_code"] == "ROUTE_NOT_FOUND"
    assert "result" not in report["provider_results"][0]


def test_google_chunked_matrix_accounts_for_all_cells_and_global_indices():
    points = [Coordinate(latitude=16.8 + i * 0.0001, longitude=96.1) for i in range(21)]
    calls = []

    def chunk(r):
        body = json.loads(r.content)
        calls.append(body)
        result = []
        for i, a in enumerate(body["origins"]):
            for j, b in enumerate(body["destinations"]):
                same = a["waypoint"] == b["waypoint"]
                result.append(
                    {
                        "originIndex": i,
                        "destinationIndex": j,
                        "condition": "ROUTE_EXISTS",
                        "distanceMeters": 0 if same else 42,
                        "duration": "0s" if same else "10s",
                    }
                )
        return httpx.Response(200, json=result)

    p = HTTPProvider(settings(routing_provider="google"), transport=httpx.MockTransport(chunk))
    matrix = p.get_route_matrix(MatrixQuery(locations=points))
    assert len(calls) == 4
    assert sum(len(c["origins"]) * len(c["destinations"]) for c in calls) == 441
    assert matrix.distances[20][0] == 42 and matrix.distances[20][20] == 0


def test_environment_limits_parse_and_unknown_or_nonfinite_configuration_rejected(monkeypatch):
    monkeypatch.setenv("LANNPYA_ROUTING_EVAL_MAX_REQUESTS", "7")
    assert lab.EvaluationSettings().max_requests == 7
    for bad in [
        {"max_estimated_cost": "NaN"},
        {"request_timeout_seconds": float("inf")},
        {"max_matrix_elements": 251},
        {"google_routes_api_key": "never-in-config"},
        {"modes": ["DRIVE", "DRIVE"]},
    ]:
        with pytest.raises(ValidationError):
            lab.EvaluationSettings(**bad)


def test_cli_writes_valid_plan_without_connecting_to_database(tmp_path, monkeypatch, capsys):
    output = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["evaluate", "--output", str(output)])
    monkeypatch.setattr(
        lab, "Settings", lambda **kw: settings(routing_external_requests_enabled=False)
    )
    monkeypatch.setattr(HTTPProvider, "post", lambda *a, **kw: pytest.fail("No HTTP allowed"))
    assert lab.main() == 0
    assert json.loads(output.read_text())["http_requests_attempted"] == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PLAN_ONLY"


def test_stale_or_incomplete_pricing_is_never_used_for_live_calls(tmp_path):
    from datetime import timedelta

    cfg = config()
    cfg.pricing.reviewed_on = date.today() - timedelta(days=31)
    with pytest.raises(lab.EvaluationBlocked, match="PRICING_REVIEW_EXPIRED"):
        run(tmp_path, cfg, lambda r: pytest.fail("Unexpected HTTP"))
    cfg = config(modes=["DRIVE", "TWO_WHEELER"])
    cfg.pricing.modes.pop("TWO_WHEELER")
    with pytest.raises(lab.EvaluationBlocked, match="REVIEWED_PRICING_REQUIRED"):
        run(tmp_path, cfg, lambda r: pytest.fail("Unexpected HTTP"))


def test_whole_evaluation_deadline_stops_before_any_call(tmp_path, monkeypatch):
    original = lab.Budget

    class Expired(original):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.deadline = 0

    monkeypatch.setattr(lab, "Budget", Expired)
    report = run(tmp_path, handler=lambda r: pytest.fail("Unexpected HTTP"))
    assert report["status"] == "STOPPED" and report["stop_code"] == "EVALUATION_TIMEOUT"
    assert report["http_requests_attempted"] == 0


def test_unwritable_ledger_fails_closed_before_network(tmp_path, monkeypatch):
    def broken(*args):
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr(lab.Budget, "save", broken)
    with pytest.raises(lab.EvaluationBlocked, match="LEDGER_UNWRITABLE"):
        run(tmp_path, handler=lambda r: pytest.fail("Unexpected HTTP"))


def test_concurrent_evaluations_cannot_reuse_the_same_ledger(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    calls = []

    def count(r):
        calls.append(r)
        return response(r)

    def attempt(_):
        try:
            return run(tmp_path, handler=count)["status"]
        except lab.EvaluationBlocked as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == ["COMPLETE", "EVALUATION_ALREADY_STARTED"]
    assert len(calls) == 7


def test_cli_invalid_configuration_is_safe_and_does_not_echo_values(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "bad.json"
    cfg.write_text('{"google_routes_api_key":"PRIVATE DO NOT DISPLAY"}')
    monkeypatch.setattr(
        "sys.argv", ["evaluate", "--config", str(cfg), "--output", str(tmp_path / "out.json")]
    )
    assert lab.main() == 2
    assert "PRIVATE" not in capsys.readouterr().out
    assert not (tmp_path / "out.json").exists()


@pytest.mark.parametrize("rate", ["-0.01", "NaN", "Infinity"])
def test_negative_or_nonfinite_rates_cannot_create_budget_credit(rate):
    raw = config().model_dump(mode="json")
    raw["pricing"]["modes"]["DRIVE"]["route_per_request"] = rate
    with pytest.raises(ValidationError):
        lab.EvaluationSettings(**raw)
