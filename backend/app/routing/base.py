from abc import ABC, abstractmethod

from app.schemas.routing import MatrixQuery, RoadMatrix, RoadRoute, RouteQuery


class RoutingFailure(Exception):
    def __init__(self, code, status=503):
        self.code, self.status = code, status
        super().__init__(code)  # Never retain provider payloads, keys or coordinate URLs.


class RoadProvider(ABC):
    @abstractmethod
    def get_route(self, request: RouteQuery) -> RoadRoute: ...

    @abstractmethod
    def get_route_matrix(self, request: MatrixQuery) -> RoadMatrix: ...
