"""Server-only Google Routes and ORS adapters; external requests are opt-in."""

import json
import math
import re
import time

import httpx2 as httpx
from pydantic import ValidationError

from app.ai.gateway import reject_constant, unique_keys
from app.routing.base import RoadProvider, RoutingFailure
from app.schemas.routing import Geometry, RoadMatrix, RoadRoute


def cost(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100000000:
        raise ValueError("Invalid provider cost")
    return math.ceil(value)


def seconds(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,9})?s", value):
        raise ValueError("Invalid protobuf duration")
    return cost(float(value[:-1]))


class HTTPProvider(RoadProvider):
    def __init__(self, settings, *, transport=None):
        self.settings, self.transport = settings, transport
        self.name = settings.routing_provider
        self.deadline = time.monotonic() + settings.routing_request_timeout_seconds

    def ready(self, mode):
        if not self.settings.routing_external_requests_enabled:
            raise RoutingFailure("EXTERNAL_ROUTING_DISABLED")
        key = (
            self.settings.google_routes_api_key
            if self.name == "google"
            else self.settings.ors_api_key
        )
        if not key or not key.get_secret_value().strip():
            raise RoutingFailure("ROUTING_KEY_MISSING")
        if mode == "TWO_WHEELER" and (
            self.name != "google" or not self.settings.routing_two_wheeler_enabled
        ):
            raise RoutingFailure("ROUTING_MODE_UNSUPPORTED", 422)
        return key.get_secret_value()

    @staticmethod
    def read_json(response, deadline):
        content = bytearray()
        for chunk in response.iter_bytes():
            if time.monotonic() > deadline:
                raise RoutingFailure("ROUTING_TIMEOUT", 504)
            content.extend(chunk)
            if len(content) > 2000000:
                raise RoutingFailure("ROUTING_RESPONSE_TOO_LARGE", 502)
        return json.loads(content, object_pairs_hook=unique_keys, parse_constant=reject_constant)

    def post(self, endpoint, body, headers, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RoutingFailure("ROUTING_TIMEOUT", 504)
        try:
            with httpx.Client(
                timeout=remaining,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport or httpx.HTTPTransport(retries=0, trust_env=False),
            ) as client:
                with client.stream("POST", endpoint, json=body, headers=headers) as response:
                    if response.status_code == 429:
                        raise RoutingFailure("ROUTING_RATE_LIMITED", 429)
                    if response.status_code in {401, 403}:
                        raise RoutingFailure("ROUTING_CREDENTIAL_OR_QUOTA_REJECTED")
                    if response.status_code in {400, 404}:
                        if self.name == "ors":
                            try:
                                data = self.read_json(response, deadline)
                                code = data.get("error", {}).get("code")
                            except (ValueError, TypeError, AttributeError):
                                code = None
                            if code == 2009:
                                raise RoutingFailure("ROUTE_NOT_FOUND", 422)
                            if code in {2010, 6010}:
                                raise RoutingFailure("ROUTING_POINT_NOT_FOUND", 422)
                        raise RoutingFailure("ROUTING_REQUEST_UNSUPPORTED", 422)
                    if response.status_code != 200:
                        raise RoutingFailure("ROUTING_PROVIDER_UNAVAILABLE")
                    return self.read_json(response, deadline)
        except httpx.TimeoutException:
            raise RoutingFailure("ROUTING_TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise RoutingFailure("ROUTING_PROVIDER_UNAVAILABLE") from None
        except (ValueError, TypeError, RecursionError):
            raise RoutingFailure("ROUTING_INVALID_RESPONSE", 502) from None

    @staticmethod
    def waypoint(point):
        return {"location": {"latLng": point.model_dump()}}

    @property
    def attribution(self):
        return (
            "Google Maps"
            if self.name == "google"
            else "openrouteservice / OpenStreetMap contributors"
        )

    def get_route(self, request):
        key = self.ready(request.mode)
        deadline = self.deadline
        try:
            if self.name == "google":
                data = self.post(
                    "https://routes.googleapis.com/directions/v2:computeRoutes",
                    {
                        "origin": self.waypoint(request.origin),
                        "destination": self.waypoint(request.destination),
                        "travelMode": request.mode,
                        "routingPreference": "TRAFFIC_UNAWARE",
                        "polylineEncoding": "GEO_JSON_LINESTRING",
                        "polylineQuality": "OVERVIEW",
                        "computeAlternativeRoutes": False,
                        "regionCode": "MM",
                    },
                    {
                        "X-Goog-Api-Key": key,
                        "X-Goog-FieldMask": (
                            "routes.distanceMeters,routes.duration,"
                            "routes.polyline.geoJsonLinestring,fallbackInfo"
                        ),
                    },
                    deadline,
                )
                if not data.get("routes"):
                    raise RoutingFailure("ROUTE_NOT_FOUND", 422)
                if data.get("fallbackInfo"):
                    raise RoutingFailure("ROUTING_UNSUPPORTED_FALLBACK", 502)
                route = data["routes"][0]
                distance, duration = cost(route["distanceMeters"]), seconds(route["duration"])
                geometry = Geometry.model_validate(route["polyline"]["geoJsonLinestring"])
            else:
                data = self.post(
                    "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
                    {
                        "coordinates": [
                            [p.longitude, p.latitude] for p in (request.origin, request.destination)
                        ],
                        "units": "m",
                        "instructions": False,
                    },
                    {"Authorization": key},
                    deadline,
                )
                if not data.get("features"):
                    raise RoutingFailure("ROUTE_NOT_FOUND", 422)
                feature = data["features"][0]
                summary = feature["properties"]["summary"]
                distance, duration = cost(summary["distance"]), cost(summary["duration"])
                geometry = Geometry.model_validate(feature["geometry"])
            return RoadRoute(
                provider=self.name,
                origin=request.origin,
                destination=request.destination,
                mode=request.mode,
                distance_meters=distance,
                duration_seconds=duration,
                geometry=geometry,
                quality="ROAD_STATIC",
                attribution=self.attribution,
                warnings=["Static provider estimate; not live traffic or guaranteed arrival."],
            )
        except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
            raise RoutingFailure("ROUTING_INVALID_RESPONSE", 502) from None

    def get_route_matrix(self, request):
        key = self.ready(request.mode)
        deadline = self.deadline
        n = len(request.locations)
        distances, durations = [[None] * n for _ in range(n)], [[None] * n for _ in range(n)]
        try:
            if self.name == "google":
                # At most 400 cells per call, below the 625-element static matrix limit.
                for a in range(0, n, 20):
                    for b in range(0, n, 20):
                        origins, destinations = (
                            request.locations[a : a + 20],
                            request.locations[b : b + 20],
                        )
                        data = self.post(
                            "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                            {
                                "origins": [{"waypoint": self.waypoint(p)} for p in origins],
                                "destinations": [
                                    {"waypoint": self.waypoint(p)} for p in destinations
                                ],
                                "travelMode": request.mode,
                                "routingPreference": "TRAFFIC_UNAWARE",
                            },
                            {
                                "X-Goog-Api-Key": key,
                                "X-Goog-FieldMask": (
                                    "originIndex,destinationIndex,status,condition,"
                                    "distanceMeters,duration,fallbackInfo"
                                ),
                            },
                            deadline,
                        )
                        seen = set()
                        for cell in data:
                            i, j = cell.get("originIndex", 0), cell.get("destinationIndex", 0)
                            if (
                                type(i) is not int
                                or type(j) is not int
                                or not 0 <= i < len(origins)
                                or not 0 <= j < len(destinations)
                                or (i, j) in seen
                            ):
                                raise ValueError("Invalid matrix index")
                            seen.add((i, j))
                            if cell.get("status", {}).get("code", 0) != 0:
                                raise RoutingFailure("ROUTING_MATRIX_ELEMENT_ERROR", 502)
                            if cell.get("fallbackInfo"):
                                raise RoutingFailure("ROUTING_UNSUPPORTED_FALLBACK", 502)
                            if cell.get("condition") == "ROUTE_EXISTS":
                                same = origins[i] == destinations[j]
                                distances[a + i][b + j] = cost(
                                    cell.get("distanceMeters", 0)
                                    if same
                                    else cell["distanceMeters"]
                                )
                                durations[a + i][b + j] = seconds(
                                    cell.get("duration", "0s") if same else cell["duration"]
                                )
                            elif cell.get("condition") != "ROUTE_NOT_FOUND":
                                raise ValueError("Invalid matrix condition")
                        if len(seen) != len(origins) * len(destinations):
                            raise ValueError("Missing matrix elements")
            else:
                if n * n > 3500:
                    raise RoutingFailure("ROUTING_MATRIX_LIMIT", 422)
                data = self.post(
                    "https://api.openrouteservice.org/v2/matrix/driving-car",
                    {
                        "locations": [[p.longitude, p.latitude] for p in request.locations],
                        "metrics": ["distance", "duration"],
                        "units": "m",
                    },
                    {"Authorization": key},
                    deadline,
                )
                distances = [
                    [None if v is None else cost(v) for v in row] for row in data["distances"]
                ]
                durations = [
                    [None if v is None else cost(v) for v in row] for row in data["durations"]
                ]
            return RoadMatrix(
                provider=self.name,
                locations=request.locations,
                mode=request.mode,
                distances=distances,
                durations=durations,
                quality="ROAD_STATIC",
                attribution=self.attribution,
                warnings=["Static matrix; no live traffic."],
            )
        except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
            raise RoutingFailure("ROUTING_INVALID_RESPONSE", 502) from None
