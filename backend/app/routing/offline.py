import json
from math import ceil
from pathlib import Path

from app.routing.base import RoadProvider, RoutingFailure
from app.schemas.routing import Geometry, RoadMatrix, RoadRoute, RouteQuery
from app.services.buyer_policy import distance_meters

FIXTURE = json.loads((Path(__file__).parents[1] / "data/routing_fixture.json").read_text())


class OfflineProvider(RoadProvider):
    """An explicit synthetic grid graph, never a disguised straight-line road estimate."""

    def node(self, p):
        f = FIXTURE
        if not (
            f["latitude_min"] <= p.latitude <= f["latitude_max"]
            and f["longitude_min"] <= p.longitude <= f["longitude_max"]
        ):
            raise RoutingFailure("OUTSIDE_SYNTHETIC_FIXTURE", 422)
        return (
            round((p.latitude - f["latitude_min"]) / f["step_degrees"]),
            round((p.longitude - f["longitude_min"]) / f["step_degrees"]),
        )

    def position(self, node):
        return [
            round(FIXTURE["longitude_min"] + node[1] * FIXTURE["step_degrees"], 7),
            round(FIXTURE["latitude_min"] + node[0] * FIXTURE["step_degrees"], 7),
        ]

    def get_route(self, request):
        if not request.allow_simulation:
            raise RoutingFailure("SIMULATION_ACKNOWLEDGEMENT_REQUIRED", 422)
        a, b = self.node(request.origin), self.node(request.destination)
        nodes = [a]
        for axis in (0, 1):
            while nodes[-1][axis] != b[axis]:
                nxt = list(nodes[-1])
                nxt[axis] += 1 if b[axis] > nxt[axis] else -1
                nodes.append(tuple(nxt))
        positions = [self.position(n) for n in nodes]
        connector = sum(
            distance_meters(p.latitude, p.longitude, xy[1], xy[0])
            for p, xy in ((request.origin, positions[0]), (request.destination, positions[-1]))
        )
        ns, ew = abs(a[0] - b[0]), abs(a[1] - b[1])
        if request.origin == request.destination:
            connector, ns, ew = 0, 0, 0
        geometry = [
            [request.origin.longitude, request.origin.latitude],
            *positions,
            [request.destination.longitude, request.destination.latitude],
        ]
        return RoadRoute(
            provider=FIXTURE["id"],
            origin=request.origin,
            destination=request.destination,
            mode=request.mode,
            quality="SIMULATED",
            attribution="LannPya synthetic test graph",
            distance_meters=ceil(
                ns * FIXTURE["north_south_edge_meters"]
                + ew * FIXTURE["east_west_edge_meters"]
                + connector
            ),
            duration_seconds=ceil(
                ns * FIXTURE["north_south_edge_seconds"]
                + ew * FIXTURE["east_west_edge_seconds"]
                + connector / FIXTURE["connector_speed_meters_per_second"]
            ),
            geometry=Geometry(coordinates=geometry),
            warnings=[FIXTURE["notice"]],
        )

    def get_route_matrix(self, request):
        routes = [
            [
                self.get_route(
                    RouteQuery(
                        origin=a,
                        destination=b,
                        mode=request.mode,
                        allow_simulation=request.allow_simulation,
                    )
                )
                for b in request.locations
            ]
            for a in request.locations
        ]
        return RoadMatrix(
            provider=FIXTURE["id"],
            locations=request.locations,
            mode=request.mode,
            distances=[[r.distance_meters for r in row] for row in routes],
            durations=[[r.duration_seconds for r in row] for row in routes],
            quality="SIMULATED",
            warnings=[FIXTURE["notice"]],
            attribution="LannPya synthetic test graph",
        )
