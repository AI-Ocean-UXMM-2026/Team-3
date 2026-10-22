"""Plan by default. Live execution requires independent gates and reviewed unit prices."""

import argparse
import hashlib
import json
import os
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ai.gateway import reject_constant, unique_keys
from app.core.config import Settings
from app.routing.base import RoutingFailure
from app.routing.http import HTTPProvider
from app.routing.offline import OfflineProvider
from app.schemas.routing import Coordinate, MatrixQuery, Mode, RouteQuery
from app.services.buyer_policy import distance_meters

FIXTURE = Path(__file__).with_name("yangon_points.json")
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class EvaluationBlocked(Exception):
    """Safe code only: no settings, credentials or provider response body."""


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ModePrice(Model):
    route_per_request: Decimal = Field(ge=0, le=1000000, max_digits=20, decimal_places=12)
    matrix_unit_price: Decimal = Field(ge=0, le=1000000, max_digits=20, decimal_places=12)
    matrix_billing_unit: Literal["REQUEST", "ELEMENT"]
    route_sku: str = Field(min_length=1, max_length=100)
    matrix_sku: str = Field(min_length=1, max_length=100)


class Pricing(Model):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reviewed_on: date
    source: str = Field(min_length=1, max_length=300)
    modes: dict[Mode, ModePrice]

    @model_validator(mode="after")
    def reviewed(self):
        if self.reviewed_on > date.today() or not self.source.strip():
            raise ValueError("Pricing must be reviewed, not future dated")
        return self


class EvaluationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANNPYA_ROUTING_EVAL_", env_file=None, extra="forbid", allow_inf_nan=False
    )
    live_enabled: bool = False
    provider: Literal["google", "ors"] = "google"
    modes: list[Mode] = Field(default_factory=lambda: ["DRIVE"], min_length=1, max_length=2)
    max_requests: int = Field(default=0, ge=0, le=32)
    max_matrix_elements: int = Field(default=0, ge=0, le=250)
    max_stops: int = Field(default=6, ge=1, le=10)
    request_timeout_seconds: float = Field(default=10, gt=0, le=30)
    evaluation_timeout_seconds: float = Field(default=60, gt=0, le=120)
    max_estimated_cost: Decimal = Field(
        default=Decimal(0), ge=0, le=1000, max_digits=20, decimal_places=12
    )
    pricing: Pricing | None = None
    pricing_max_age_days: int = Field(default=30, ge=1, le=90)

    @model_validator(mode="after")
    def supported(self):
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("Duplicate modes")
        if self.provider == "ors" and self.modes != ["DRIVE"]:
            raise ValueError("ORS adapter supports driving-car only")
        if self.provider == "google" and self.pricing:
            if any(p.matrix_billing_unit != "ELEMENT" for p in self.pricing.modes.values()):
                raise ValueError("Google matrix billing is per element")
        return self


class Delivery(Model):
    id: str = Field(pattern=r"^SYN-YGN-\d{2}$")
    point: Coordinate
    probe: Literal["ordinary_test_point", "possible_off_road_probe_not_verified"]


class Dataset(Model):
    id: str
    notice: str
    hub: Coordinate
    deliveries: list[Delivery] = Field(min_length=5, max_length=10)

    @model_validator(mode="after")
    def synthetic(self):
        if "FICTIONAL TEST COORDINATES" not in self.notice:
            raise ValueError("Explicit fictional label required")
        if len({p.id for p in self.deliveries}) != len(self.deliveries):
            raise ValueError("Duplicate point IDs")
        for p in [self.hub] + [p.point for p in self.deliveries]:
            if not (16.75 <= p.latitude <= 16.95 and 96.05 <= p.longitude <= 96.25):
                raise ValueError("Point outside the bounded fictional Yangon evaluation area")
        return self


def dataset():
    return Dataset.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def quote(config, data):
    n, modes = len(data.deliveries), len(config.modes)
    elements = (n + 1) ** 2
    estimated = Decimal(0) if config.pricing else None
    if config.pricing:
        for mode in config.modes:
            price = config.pricing.modes.get(mode)
            if price is None:
                estimated = None
                break
            estimated += n * price.route_per_request
            estimated += (
                elements if price.matrix_billing_unit == "ELEMENT" else 1
            ) * price.matrix_unit_price
    return {
        "planned_http_requests": (n + 1) * modes,
        "route_requests": n * modes,
        "matrix_requests": modes,
        "matrix_elements": elements * modes,
        "stops": n,
        "estimated_cost": str(estimated) if estimated is not None else None,
        "currency": config.pricing.currency if config.pricing else None,
        "billing_warning": (
            "Configured estimate only, not an invoice or free-tier guarantee; failures may count."
        ),
    }


def blockers(config, settings, q, execute_live):
    codes = []
    if not execute_live:
        codes.append("CLI_LIVE_OPT_IN_REQUIRED")
    if not config.live_enabled:
        codes.append("EVALUATION_LIVE_DISABLED")
    if settings.environment not in {"local", "test"}:
        codes.append("LOCAL_EVALUATION_ONLY")
    if not settings.routing_external_requests_enabled:
        codes.append("EXTERNAL_ROUTING_DISABLED")
    if q["stops"] > config.max_stops or q["stops"] > settings.routing_max_stops:
        codes.append("EVALUATION_STOP_LIMIT")
    if q["planned_http_requests"] > config.max_requests:
        codes.append("EVALUATION_REQUEST_LIMIT")
    if q["matrix_elements"] > config.max_matrix_elements:
        codes.append("EVALUATION_MATRIX_ELEMENT_LIMIT")
    if q["estimated_cost"] is None:
        codes.append("REVIEWED_PRICING_REQUIRED")
    elif Decimal(q["estimated_cost"]) > config.max_estimated_cost:
        codes.append("EVALUATION_COST_LIMIT")
    if config.pricing and config.pricing.reviewed_on < date.today() - timedelta(
        days=config.pricing_max_age_days
    ):
        codes.append("PRICING_REVIEW_EXPIRED")
    key = settings.google_routes_api_key if config.provider == "google" else settings.ors_api_key
    if not key or not key.get_secret_value().strip():
        codes.append("ROUTING_KEY_MISSING")
    if "TWO_WHEELER" in config.modes and not settings.routing_two_wheeler_enabled:
        codes.append("TWO_WHEELER_NOT_ENABLED")
    return codes


class Budget:
    """Reserve before every actual HTTP attempt, including unsuccessful requests."""

    def __init__(self, config, ledger_path):
        self.config = config
        self.requests, self.elements, self.cost = 0, 0, Decimal(0)
        self.attempts = 0
        self.deadline = time.monotonic() + config.evaluation_timeout_seconds
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.file = ledger_path.open("x", encoding="utf-8")
        except FileExistsError:
            raise EvaluationBlocked("EVALUATION_ALREADY_STARTED") from None
        try:
            self.save("STARTED")
        except OSError:
            self.file.close()
            raise EvaluationBlocked("LEDGER_UNWRITABLE") from None

    def save(self, state):
        self.file.seek(0)
        json.dump(
            {
                "state": state,
                "requests_reserved": self.requests,
                "matrix_elements_reserved": self.elements,
                "estimated_cost_reserved": str(self.cost),
            },
            self.file,
        )
        self.file.truncate()
        self.file.flush()
        os.fsync(self.file.fileno())

    def reserve(self, kind, mode, elements=0):
        if time.monotonic() >= self.deadline:
            raise EvaluationBlocked("EVALUATION_TIMEOUT")
        price = self.config.pricing.modes[mode]
        increment = (
            price.route_per_request
            if kind == "route"
            else price.matrix_unit_price
            * (elements if price.matrix_billing_unit == "ELEMENT" else 1)
        )
        if self.requests + 1 > self.config.max_requests:
            raise EvaluationBlocked("EVALUATION_REQUEST_LIMIT")
        if self.elements + elements > self.config.max_matrix_elements:
            raise EvaluationBlocked("EVALUATION_MATRIX_ELEMENT_LIMIT")
        if self.cost + increment > self.config.max_estimated_cost:
            raise EvaluationBlocked("EVALUATION_COST_LIMIT")
        self.requests += 1
        self.elements += elements
        self.cost += increment
        self.save("REQUEST_RESERVED")  # Disk failure stops before any external request.

    def close(self):
        self.file.close()


class GuardedProvider(HTTPProvider):
    def __init__(self, settings, budget, *, transport=None):
        super().__init__(settings, transport=transport)
        self.budget = budget
        self.deadline = min(self.deadline, budget.deadline)

    def post(self, endpoint, body, headers, deadline):
        prefix = (
            "https://routes.googleapis.com/"
            if self.name == "google"
            else "https://api.openrouteservice.org/"
        )
        if not endpoint.startswith(prefix):
            raise EvaluationBlocked("UNEXPECTED_PROVIDER_ENDPOINT")
        if endpoint in {
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
        }:
            kind, elements = "route", 0
        elif endpoint == "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix":
            kind, elements = "matrix", len(body["origins"]) * len(body["destinations"])
        elif endpoint == "https://api.openrouteservice.org/v2/matrix/driving-car":
            kind, elements = "matrix", len(body["locations"]) ** 2
        else:
            raise EvaluationBlocked("UNEXPECTED_PROVIDER_ENDPOINT")
        self.budget.reserve(kind, body.get("travelMode", "DRIVE"), elements)
        if time.monotonic() >= min(deadline, self.budget.deadline):
            raise EvaluationBlocked("EVALUATION_TIMEOUT")
        self.budget.attempts += 1
        return super().post(endpoint, body, headers, min(deadline, self.budget.deadline))


def summary(route):
    offsets = None
    if route.geometry:
        first, last = route.geometry.coordinates[0], route.geometry.coordinates[-1]
        offsets = {
            "origin": round(
                distance_meters(route.origin.latitude, route.origin.longitude, first[1], first[0]),
                3,
            ),
            "destination": round(
                distance_meters(
                    route.destination.latitude, route.destination.longitude, last[1], last[0]
                ),
                3,
            ),
        }
    return {
        "provider": route.provider,
        "quality": route.quality,
        "distance_meters": route.distance_meters,
        "duration_seconds": route.duration_seconds,
        "traffic_aware": route.traffic_aware,
        "geometry_available": route.geometry is not None,
        "geometry_points": len(route.geometry.coordinates) if route.geometry else 0,
        "geometry_endpoint_offsets_meters": offsets,
        "warnings": route.warnings,
    }


def compare(real, simulated):
    return {
        "distance_delta_meters": real.distance_meters - simulated.distance_meters,
        "duration_delta_seconds": real.duration_seconds - simulated.duration_seconds,
        "meaning": "Provider static estimate versus invented fixture; not savings or accuracy.",
    }


def evaluate(config, settings, *, execute_live=False, ledger_path=None, transport=None):
    data = dataset()
    q = quote(config, data)
    blocked = blockers(config, settings, q, execute_live)
    baseline = OfflineProvider()
    routes = {
        d.id: baseline.get_route(
            RouteQuery(origin=data.hub, destination=d.point, allow_simulation=True)
        )
        for d in data.deliveries
    }
    matrix_input = MatrixQuery(locations=[data.hub] + [d.point for d in data.deliveries])
    baseline_matrix = baseline.get_route_matrix(
        matrix_input.model_copy(update={"allow_simulation": True})
    )
    report = {
        "status": "PLAN_ONLY",
        "dataset": data.model_dump(mode="json"),
        "quote": q,
        "execution_blockers": blocked,
        "http_requests_attempted": 0,
        "network": "NONE",
        "live_verified": False,
        "simulation": {k: summary(v) for k, v in routes.items()},
        "simulation_matrix": baseline_matrix.model_dump(mode="json"),
        "provider_results": [],
        "limitations": [
            "Fictional coordinates; missing roads/reachability have no verified ground truth.",
            "No raw geometry persisted; inspect transient geometry only under provider terms.",
            "Static travel estimates, not live traffic or observed rider travel times.",
        ],
    }
    if not execute_live:
        return report
    if blocked:
        raise EvaluationBlocked(",".join(blocked))
    if ledger_path is None:
        raise EvaluationBlocked("EXCLUSIVE_LEDGER_REQUIRED")
    budget = Budget(config, ledger_path)
    try:
        report["network"] = "MOCK_HTTP" if transport is not None else "EXTERNAL_HTTP"
        report["status"] = "COMPLETE"
        for mode in config.modes:
            for delivery in [*data.deliveries, None]:
                started = time.perf_counter()
                item = {"mode": mode, "case": delivery.id if delivery else "matrix"}
                remaining = min(
                    config.request_timeout_seconds,
                    settings.routing_request_timeout_seconds,
                    budget.deadline - time.monotonic(),
                )
                if remaining <= 0:
                    raise EvaluationBlocked("EVALUATION_TIMEOUT")
                configured = settings.model_copy(
                    update={
                        "routing_provider": config.provider,
                        "routing_request_timeout_seconds": remaining,
                    }
                )
                provider = GuardedProvider(configured, budget, transport=transport)
                try:
                    if delivery:
                        route = provider.get_route(
                            RouteQuery(origin=data.hub, destination=delivery.point, mode=mode)
                        )
                        item.update(
                            result=summary(route), comparison=compare(route, routes[delivery.id])
                        )
                    else:
                        matrix = provider.get_route_matrix(
                            matrix_input.model_copy(update={"mode": mode})
                        )
                        cells = len(matrix.locations) ** 2
                        item["result"] = {
                            "provider": matrix.provider,
                            "quality": matrix.quality,
                            "matrix_cells": cells,
                            "distances": matrix.distances,
                            "durations": matrix.durations,
                            "unreachable_cells": sum(
                                v is None for row in matrix.distances for v in row
                            ),
                        }
                        item["comparison"] = {
                            "distance_delta_meters": [
                                [
                                    None if v is None else v - baseline_matrix.distances[i][j]
                                    for j, v in enumerate(row)
                                ]
                                for i, row in enumerate(matrix.distances)
                            ],
                            "duration_delta_seconds": [
                                [
                                    None if v is None else v - baseline_matrix.durations[i][j]
                                    for j, v in enumerate(row)
                                ]
                                for i, row in enumerate(matrix.durations)
                            ],
                            "meaning": "Provider vs invented graph; no accuracy or savings claim.",
                        }
                    item["status"] = "OK"
                except RoutingFailure as exc:
                    item.update(status="PROVIDER_ERROR", error_code=exc.code)
                    report["status"] = "COMPLETED_WITH_PROVIDER_ERRORS"
                    # Stop on account/rate/quota/time/system errors; never retry.
                    if exc.code not in {"ROUTE_NOT_FOUND", "ROUTING_POINT_NOT_FOUND"}:
                        item["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                        report["provider_results"].append(item)
                        raise EvaluationBlocked("PROVIDER_FAILURE_STOP") from None
                item["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                report["provider_results"].append(item)
    except EvaluationBlocked as exc:
        report.update(status="STOPPED", stop_code=str(exc))
    finally:
        report.update(
            http_requests_attempted=budget.attempts,
            requests_reserved=budget.requests,
            matrix_elements_reserved=budget.elements,
            estimated_cost_reserved=str(budget.cost),
        )
        try:
            budget.save(report["status"])
        finally:
            budget.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--evaluation-id")
    args = parser.parse_args()
    try:
        raw = args.config.read_bytes() if args.config else b"{}"
        if len(raw) > 65536:
            raise EvaluationBlocked("CONFIG_TOO_LARGE")
        config = EvaluationSettings(
            **json.loads(raw, object_pairs_hook=unique_keys, parse_constant=reject_constant)
        )
        settings = Settings(_env_file=None)  # No database connection or .env file is opened.
        identifier = args.evaluation_id or ""
        if args.execute_live and (
            not identifier
            or not all(c.isalnum() or c == "-" for c in identifier)
            or len(identifier) > 64
        ):
            raise EvaluationBlocked("EXPLICIT_UNIQUE_EVALUATION_ID_REQUIRED")
        ledger = BACKEND_ROOT.parent / ".tmp" / "routing-evaluations" / (identifier + ".json")
        report = evaluate(config, settings, execute_live=args.execute_live, ledger_path=ledger)
        report["config_sha256"] = hashlib.sha256(raw).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "http_requests_attempted": report["http_requests_attempted"],
                    "planned_requests": report["quote"]["planned_http_requests"],
                }
            )
        )
        return 0 if report["status"] in {"PLAN_ONLY", "COMPLETE"} else 1
    except (EvaluationBlocked, RoutingFailure) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": str(exc)}))
        return 2
    except (ValidationError, ValueError, TypeError, OSError):
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "Invalid configuration or output/ledger access; no keys are printed.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
