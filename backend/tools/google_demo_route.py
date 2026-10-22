"""One deliberately authorized Demo Key request; default invocation is network-free.

Run from backend: .venv/Scripts/python.exe -m tools.google_demo_route
The normal application configuration, database and provider selection are untouched.
"""

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx2 as httpx
from dotenv import dotenv_values
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.routing.base import RoutingFailure
from app.routing.http import HTTPProvider
from app.schemas.routing import Geometry, RouteQuery

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ENV = ROOT / "backend/.env.google-demo.local"
LEDGER = ROOT / ".tmp/google-demo/prompt26-attempt.json"
ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
MASK = "routes.distanceMeters,routes.duration,routes.polyline.geoJsonLinestring"
ENCODED_MASK = "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline"
QUERY = RouteQuery(
    origin={"latitude": 16.825, "longitude": 96.130},
    destination={"latitude": 16.815, "longitude": 96.125},
)


def plan(encoded_geometry=False):
    return {
        "observation": "NOT_EXECUTED",
        "endpoint": ENDPOINT,
        "method": "POST",
        "maximum_requests": 1,
        "matrix_elements": 0,
        "mode": "DRIVE",
        "routing_preference": "TRAFFIC_UNAWARE",
        "field_mask": ENCODED_MASK if encoded_geometry else MASK,
        "polyline_encoding": "ENCODED_POLYLINE" if encoded_geometry else "GEO_JSON_LINESTRING",
        "query": QUERY.model_dump(),
        "coordinates": "FICTIONAL YANGON TEST POINTS; not customer homes",
        "timeout_seconds": 10,
        "retries": 0,
        "quota": "One Compute Routes query; no matrix, traffic or two-wheeler requests",
        "cost": "Demo Key only; no billing activation. Actual key entitlement unverified.",
    }


def load_key():
    # No default .env loading: this helper must not activate normal app services.
    values = dotenv_values(PRIVATE_ENV) if PRIVATE_ENV.exists() else {}
    for name in ("LANNPYA_GOOGLE_ROUTES_API_KEY", "GOOGLE_ROUTES_API_KEY"):
        value = os.environ.get(name) or values.get(name)
        if value and value.strip():
            return SecretStr(value.strip())
    return None


def store_key():
    if not sys.stdin.isatty():
        raise RoutingFailure("MASKED_INTERACTIVE_TERMINAL_REQUIRED")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", str(PRIVATE_ENV)],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if ignored.returncode != 0:
        raise RoutingFailure("PRIVATE_ENV_MUST_BE_GIT_IGNORED")
    key = getpass.getpass("Google Demo Key (hidden; never paste into chat): ")
    if not key.strip() or any(c.isspace() for c in key) or len(key) > 512:
        raise RoutingFailure("INVALID_KEY_FORMAT")
    # Only this dedicated ignored file is replaced; no application .env is touched.
    # Built-in open supports a custom opener; pathlib.Path.open does not.
    # os.open uses native Windows file handling and preserves inherited Windows ACLs.
    with open(PRIVATE_ENV, "w", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as f:
        f.write("# Private backend-only Demo Key. Live calls remain disabled.\n")
        f.write("GOOGLE_ROUTES_API_KEY=" + key + "\n")


def safe_error(data):
    """Exact canonical Google error identifiers only; never echo free-form messages."""
    error = data.get("error", {}) if isinstance(data, dict) else {}
    if not isinstance(error, dict):
        return {}
    result = {}
    if type(error.get("code")) is int:
        result["code"] = error["code"]
    status = error.get("status")
    if isinstance(status, str) and re.fullmatch(r"[A-Z_]{1,64}", status):
        result["status"] = status
    # ErrorInfo.reason is a machine-readable enum, unlike message/metadata.
    allowed = {
        "API_KEY_INVALID",
        "API_KEY_SERVICE_BLOCKED",
        "API_KEY_HTTP_REFERRER_BLOCKED",
        "API_KEY_IP_ADDRESS_BLOCKED",
        "SERVICE_DISABLED",
        "BILLING_DISABLED",
        "RATE_LIMIT_EXCEEDED",
        "QUOTA_EXCEEDED",
        "CONSUMER_INVALID",
    }
    details = error.get("details", [])
    if isinstance(details, list):
        result["reasons"] = sorted(
            {
                d["reason"]
                for d in details
                if isinstance(d, dict)
                and isinstance(d.get("reason"), str)
                and d["reason"] in allowed
            }
        )
    return result


def decode_polyline(value):
    """Decode Google's five-decimal encoded polyline into validated GeoJSON positions."""
    if not isinstance(value, str) or not value or len(value) > 250000:
        raise ValueError("Invalid encoded geometry")
    positions, index, latitude, longitude = [], 0, 0, 0
    while index < len(value):
        deltas = []
        for _ in range(2):
            number, shift = 0, 0
            while True:
                if index >= len(value) or shift > 30:
                    raise ValueError("Truncated or oversized encoded position")
                chunk = ord(value[index]) - 63
                index += 1
                if not 0 <= chunk <= 63:
                    raise ValueError("Invalid encoded character")
                number |= (chunk & 31) << shift
                shift += 5
                if chunk < 32:
                    break
            deltas.append(~(number >> 1) if number & 1 else number >> 1)
        latitude += deltas[0]
        longitude += deltas[1]
        positions.append([longitude / 100000, latitude / 100000])
        if len(positions) > 20000:
            raise ValueError("Too many geometry positions")
    return Geometry(coordinates=positions).model_dump()


class SingleRequestProvider(HTTPProvider):
    def __init__(self, settings, ledger=LEDGER, *, transport=None, encoded_geometry=False):
        super().__init__(settings, transport=transport)
        self.ledger = ledger
        self.attempts = 0
        self.http_status = None
        self.google_error = {}
        self.encoded_geometry = encoded_geometry

    def get_route_matrix(self, request):
        raise RoutingFailure("MATRIX_FORBIDDEN")

    def post(self, endpoint, body, headers, deadline):
        if endpoint != ENDPOINT or body != {
            "origin": self.waypoint(QUERY.origin),
            "destination": self.waypoint(QUERY.destination),
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",
            "polylineEncoding": "GEO_JSON_LINESTRING",
            "polylineQuality": "OVERVIEW",
            "computeAlternativeRoutes": False,
            "regionCode": "MM",
        }:
            raise RoutingFailure("REQUEST_OUTSIDE_APPROVED_PLAN")
        if self.attempts:
            raise RoutingFailure("ONE_REQUEST_LIMIT_REACHED")
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Atomic, durable, cross-process reservation BEFORE any network activity.
            with self.ledger.open("x", encoding="utf-8") as f:
                json.dump({"reserved_requests": 1, "endpoint": ENDPOINT}, f)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            raise RoutingFailure("REQUEST_ALREADY_RESERVED_NO_RETRY") from None
        self.attempts = 1
        remaining = min(10, deadline - time.monotonic())
        if remaining <= 0:
            raise RoutingFailure("ROUTING_TIMEOUT", 504)
        headers = {
            **headers,
            "X-Goog-FieldMask": ENCODED_MASK if self.encoded_geometry else MASK,
        }
        if self.encoded_geometry:
            body = {**body, "polylineEncoding": "ENCODED_POLYLINE"}
        try:
            with httpx.Client(
                timeout=remaining,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport or httpx.HTTPTransport(retries=0, trust_env=False),
            ) as client:
                with client.stream("POST", endpoint, headers=headers, json=body) as response:
                    self.http_status = response.status_code
                    try:
                        data = self.read_json(response, deadline)
                    except (ValueError, TypeError, RecursionError):
                        raise RoutingFailure("ROUTING_INVALID_RESPONSE", 502) from None
                    if response.status_code != 200:
                        self.google_error = safe_error(data)
                        raise RoutingFailure("GOOGLE_REQUEST_REJECTED")
                    if self.encoded_geometry and isinstance(data, dict) and data.get("routes"):
                        polyline = data["routes"][0]["polyline"]
                        polyline["geoJsonLinestring"] = decode_polyline(polyline["encodedPolyline"])
                    return data
        except httpx.TimeoutException:
            raise RoutingFailure("ROUTING_TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise RoutingFailure("ROUTING_PROVIDER_UNAVAILABLE") from None


def execute(
    settings, *, demo_confirmed=False, ledger=LEDGER, transport=None, encoded_geometry=False
):
    # Calling this function cannot silently turn on the existing live-request gate.
    if not demo_confirmed:
        raise RoutingFailure("DEMO_KEY_CONFIRMATION_REQUIRED")
    if settings.routing_provider != "google" or settings.environment == "production":
        raise RoutingFailure("LOCAL_GOOGLE_CONFIGURATION_REQUIRED")
    provider = SingleRequestProvider(
        settings, ledger, transport=transport, encoded_geometry=encoded_geometry
    )
    result = {"observation": "NOT_VERIFIED", "external_attempts": 0}
    try:
        route = provider.get_route(QUERY)
        result.update(
            observation="MOCK_HTTP" if transport is not None else "GOOGLE_LIVE",
            route=route.model_dump(mode="json"),
            geometry_format="GeoJSON LineString [longitude, latitude]",
            map_policy="Google routes must be displayed on a Google map",
        )
    except RoutingFailure as exc:
        result.update(error=exc.code, google_error=provider.google_error)
    result.update(external_attempts=provider.attempts, http_status=provider.http_status)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-key", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--confirm-demo-key", action="store_true")
    parser.add_argument("--encoded-geometry", action="store_true")
    args = parser.parse_args()
    try:
        if args.store_key:
            if args.execute_live:
                raise RoutingFailure("STORE_AND_EXECUTE_MUST_BE_SEPARATE")
            store_key()
            print('{"key_stored":true,"external_requests":0}')
            return 0
        if not args.execute_live:
            print(
                json.dumps(
                    {**plan(args.encoded_geometry), "key_configured": load_key() is not None},
                    indent=2,
                )
            )
            return 0
        settings = Settings(
            _env_file=None,
            routing_provider="google",
            google_routes_api_key=load_key(),
            routing_request_timeout_seconds=10,
            routing_two_wheeler_enabled=False,
        )
        result = execute(
            settings, demo_confirmed=args.confirm_demo_key, encoded_geometry=args.encoded_geometry
        )
        # No raw geometry caching or provider messages in logs. The route remains in memory.
        route = result.pop("route", None)
        if route:
            result["validated_route"] = {
                "distance_meters": route["distance_meters"],
                "duration_seconds": route["duration_seconds"],
                "geometry_points": len(route["geometry"]["coordinates"]),
                "quality": route["quality"],
                "traffic_aware": route["traffic_aware"],
            }
        print(json.dumps(result, indent=2))
        return 0 if result["observation"] == "GOOGLE_LIVE" else 1
    except (RoutingFailure, OSError, ValidationError) as exc:
        code = exc.code if isinstance(exc, RoutingFailure) else "LOCAL_FILE_OPERATION_FAILED"
        print(json.dumps({"error": code, "observation": "NOT_EXECUTED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
