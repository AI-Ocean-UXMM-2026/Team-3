"""Provider-neutral routing and bounded planning contracts. No address interpretation."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Coordinate(StrictModel):
    latitude: float = Field(ge=-90, le=90, strict=True)
    longitude: float = Field(ge=-180, le=180, strict=True)


Mode = Literal["DRIVE", "TWO_WHEELER"]
Quality = Literal["SIMULATED", "ROAD_STATIC"]


class RoutingStatus(StrictModel):
    provider: Literal["disabled", "offline", "google", "ors"]
    external_requests_enabled: bool
    key_configured: bool
    simulation_acknowledgement_required: bool
    max_stops: int
    live_verified: Literal[False]
    two_wheeler_enabled: bool


class Geometry(StrictModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(min_length=2, max_length=20000)

    @field_validator("coordinates")
    @classmethod
    def positions(cls, value):
        for point in value:
            if len(point) != 2:
                raise ValueError("Geometry positions must be longitude/latitude pairs")
            Coordinate(latitude=point[1], longitude=point[0])
        return value


class RouteQuery(StrictModel):
    origin: Coordinate
    destination: Coordinate
    mode: Mode = "DRIVE"
    allow_simulation: bool = Field(default=False, strict=True)


class RoadRoute(StrictModel):
    provider: str
    origin: Coordinate
    destination: Coordinate
    mode: Mode
    distance_meters: int = Field(ge=0, le=100000000)
    duration_seconds: int = Field(ge=0, le=10000000)
    geometry: Geometry | None = None
    quality: Quality
    traffic_aware: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)
    attribution: str


class GoogleEstimateQuery(StrictModel):
    order_id: UUID
    origin: Coordinate
    request_id: UUID
    authorize_external_request: Literal[True]

    @field_validator("authorize_external_request", mode="before")
    @classmethod
    def explicit_boolean(cls, value):
        if value is not True:
            raise ValueError("Explicit boolean authorization is required")
        return value


class GoogleEstimate(StrictModel):
    observation: Literal["GOOGLE_LIVE", "GOOGLE_MOCK"]
    order_id: UUID
    request_id: UUID
    route: RoadRoute


class GoogleEstimateStatus(StrictModel):
    enabled: bool
    maximum_requests: int
    reserved_requests: int
    remaining_requests: int
    explicit_consent_required: Literal[True] = True
    matrix_supported: Literal[False] = False


class MatrixQuery(StrictModel):
    locations: list[Coordinate] = Field(min_length=2, max_length=51)
    mode: Mode = "DRIVE"
    allow_simulation: bool = Field(default=False, strict=True)


class RoadMatrix(StrictModel):
    provider: str
    locations: list[Coordinate] = Field(min_length=2, max_length=51)
    mode: Mode
    distances: list[list[int | None]]
    durations: list[list[int | None]]
    quality: Quality
    traffic_aware: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)
    attribution: str

    @model_validator(mode="after")
    def square(self):
        n = len(self.locations)
        for matrix in (self.distances, self.durations):
            if len(matrix) != n or any(len(row) != n for row in matrix):
                raise ValueError("Routing matrix must be square and complete")
            for i, row in enumerate(matrix):
                if row[i] != 0:
                    raise ValueError("Matrix diagonal must be zero")
                if any(
                    v is not None and (isinstance(v, bool) or v < 0 or v > 100000000) for v in row
                ):
                    raise ValueError("Invalid matrix cost")
        for i in range(n):
            for j in range(n):
                if (self.distances[i][j] is None) != (self.durations[i][j] is None):
                    raise ValueError("Unreachable cells must omit both costs")
        return self


class TimeWindow(StrictModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid_window(self):
        if not self.start.tzinfo or not self.end.tzinfo or self.end <= self.start:
            raise ValueError("Provide an increasing timezone-aware window")
        return self


class PlanningRider(StrictModel):
    rider_id: UUID
    capacity: int = Field(default=20, ge=1, le=200, strict=True)


class PlanningOrder(StrictModel):
    order_id: UUID
    demand: int = Field(default=1, ge=1, le=200, strict=True)
    service_seconds: int = Field(default=180, ge=0, le=3600, strict=True)
    priority: int = Field(default=0, ge=0, le=5, strict=True)


class PlanQuery(StrictModel):
    origin: Coordinate
    orders: list[PlanningOrder] = Field(min_length=1, max_length=50)
    riders: list[PlanningRider] = Field(min_length=1, max_length=10)
    operating_window: TimeWindow
    return_to_hub: bool = Field(default=True, strict=True)
    mode: Mode = "DRIVE"
    allow_simulation: bool = Field(default=False, strict=True)
    objective: Literal["duration", "distance"] = "duration"
    solver_seconds: int = Field(default=2, ge=1, le=10, strict=True)

    @model_validator(mode="after")
    def unique_and_bounded(self):
        if len({o.order_id for o in self.orders}) != len(self.orders):
            raise ValueError("Duplicate orders are not permitted")
        if len({r.rider_id for r in self.riders}) != len(self.riders):
            raise ValueError("Duplicate riders are not permitted")
        if (self.operating_window.end - self.operating_window.start).total_seconds() > 86400:
            raise ValueError("Planning horizon cannot exceed 24 hours")
        return self


class PlanCommit(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    acknowledge_unverified_location: bool = Field(strict=True)
    allow_simulation: bool = Field(default=False, strict=True)


class PlannedStop(StrictModel):
    order_id: UUID
    sequence: int = Field(ge=1)
    arrival: datetime
    departure: datetime
    demand: int
    latitude: float
    longitude: float
    priority: int = 0
    delivery_window: TimeWindow | None = None


class PlannedVehicle(StrictModel):
    rider_id: UUID
    stops: list[PlannedStop]
    distance_meters: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    travel_seconds: int = Field(ge=0)
    geometry: Geometry | None = None
    geometry_warning: str | None = None
    capacity: int | None = None
    load: int | None = None


class OptimizationResult(StrictModel):
    solver: Literal["OR-Tools"] = "OR-Tools"
    solver_status: Literal["FEASIBLE", "PARTIAL", "INFEASIBLE", "TIME_LIMIT"]
    globally_optimal: Literal[False] = False
    elapsed_ms: float
    provider: str
    quality: Quality
    traffic_aware: Literal[False] = False
    matrix_size: int
    vehicles: list[PlannedVehicle]
    unassigned: list[dict]
    warnings: list[str]
    attribution: str


class PlanResponse(StrictModel):
    id: UUID
    version: int
    state: Literal["PREVIEW", "COMMITTED"]
    created_at: datetime
    stale: bool
    origin: Coordinate
    operating_window: TimeWindow
    result: OptimizationResult
    routes: dict[str, str]


class PlanPage(StrictModel):
    items: list[PlanResponse]
    total: int
    page: int
    page_size: int
