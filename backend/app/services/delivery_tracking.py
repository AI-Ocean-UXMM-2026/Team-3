"""Order-scoped last GPS report and one shared, cached OSRM road route."""

from datetime import datetime, timedelta
from math import hypot

import httpx2 as httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.order_errors import OrderAPIError
from app.db.models import Order, utcnow
from app.db.rider_models import DeliveryAssignment, DeliveryPosition
from app.domain.lifecycle import OrderStatus, UserRole
from app.schemas.routing import Geometry


class PositionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False, strict=True)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False, strict=True)
    accuracy: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    captured_at: AwareDatetime = Field(default_factory=utcnow)


def road_route(origin, destination):
    """Coordinates only; provider failure never becomes a fabricated road route."""
    try:
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
        )
        with httpx.Client(timeout=4, follow_redirects=False, trust_env=False) as client:
            response = client.get(
                url,
                params={"overview": "simplified", "geometries": "geojson", "alternatives": "false"},
            )
            response.raise_for_status()
            route = response.json()["routes"][0]
        geometry = Geometry.model_validate(route["geometry"])
        distance, duration = float(route["distance"]), float(route["duration"])
        if not 0 <= distance <= 2000000 or not 0 <= duration <= 604800:
            return None
        return {
            "geometry": geometry.model_dump(),
            "distance_meters": distance,
            "duration_seconds": duration,
            "provider": "osrm",
            "traffic_aware": False,
        }
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return None


def assignment_for(session, order):
    if order.status != OrderStatus.OUT_FOR_DELIVERY:
        return None
    return session.scalar(
        select(DeliveryAssignment).where(
            DeliveryAssignment.order_id == order.id,
            DeliveryAssignment.status == "ACTIVE",
            DeliveryAssignment.response_status == "ACCEPTED",
        )
    )


def snapshot(session, order):
    assignment = assignment_for(session, order)
    row = session.get(DeliveryPosition, assignment.id) if assignment else None
    empty = {
        "state": "unavailable",
        "position": None,
        "destination": None,
        "route": None,
        "updated_at": None,
    }
    if (
        row is None
        or order.latitude is None
        or order.longitude is None
        or utcnow() - row.captured_at > timedelta(minutes=10)
    ):
        return empty
    destination = {"lat": float(order.latitude), "lng": float(order.longitude)}
    data = row.data
    return {
        "state": "stale" if utcnow() - row.captured_at > timedelta(seconds=90) else "live",
        "position": data["position"],
        "destination": destination,
        "route": data["route"] if data["destination"] == destination else None,
        "updated_at": row.captured_at.isoformat(),
    }


def rider_order(session, actor, rider_id, order_id):
    if actor.role != UserRole.RIDER:
        raise OrderAPIError(403, "RIDER_REQUIRED", "Only the assigned rider can share GPS.")
    assignment = session.scalar(
        select(DeliveryAssignment)
        .where(
            DeliveryAssignment.order_id == order_id,
            DeliveryAssignment.rider_id == actor.id,
            DeliveryAssignment.rider_id == rider_id,
        )
        .order_by(DeliveryAssignment.assigned_at.desc())
        .limit(1)
    )
    if assignment is None:
        raise OrderAPIError(404, "ASSIGNED_DELIVERY_NOT_FOUND", "Assigned delivery not found.")
    order = session.get(Order, order_id)
    active = assignment_for(session, order)
    if active and active.rider_id != actor.id:
        raise OrderAPIError(404, "ASSIGNED_DELIVERY_NOT_FOUND", "Assigned delivery not found.")
    return order


def publish(session, actor, rider_id, order_id, body):
    order = rider_order(session, actor, rider_id, order_id)
    assignment = assignment_for(session, order)
    if assignment is None or assignment.rider_id != actor.id:
        raise OrderAPIError(409, "TRACKING_CLOSED", "GPS sharing is available during delivery.")
    now = utcnow()
    if not now - timedelta(minutes=5) <= body.captured_at <= now + timedelta(seconds=30):
        raise OrderAPIError(422, "GPS_TIME_INVALID", "Refresh your device location and retry.")
    if order.latitude is None or order.longitude is None:
        raise OrderAPIError(
            409, "DELIVERY_POINT_REQUIRED", "A confirmed delivery point is required."
        )
    old = session.get(DeliveryPosition, assignment.id)
    if old and body.captured_at <= old.captured_at:
        return snapshot(session, order)
    if old and now - old.captured_at < timedelta(seconds=3):
        return snapshot(session, order)
    point = {"lat": body.latitude, "lng": body.longitude, "accuracy": body.accuracy}
    destination = {"lat": float(order.latitude), "lng": float(order.longitude)}
    route_time = old.data.get("route_calculated_at") if old else None
    route_origin = old.data.get("route_origin", point) if old else point
    if (
        old
        and old.data["destination"] == destination
        and old.data["route"]
        and (
            route_time
            and now - datetime.fromisoformat(route_time) < timedelta(seconds=30)
            and hypot(
                point["lat"] - route_origin["lat"],
                point["lng"] - route_origin["lng"],
            )
            < 0.0005
        )
    ):
        route = old.data["route"]
    else:
        route = road_route(point, destination)
        route_time, route_origin = now.isoformat(), point
    # Do not overwrite a newer fix if slow route calculations finish out of order.
    insert = sqlite_insert if session.bind.dialect.name == "sqlite" else pg_insert
    data = {
        "position": point,
        "destination": destination,
        "route": route,
        "route_calculated_at": route_time,
        "route_origin": route_origin,
    }
    statement = insert(DeliveryPosition).values(
        assignment_id=assignment.id, captured_at=body.captured_at, data=data
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[DeliveryPosition.assignment_id],
            set_={"captured_at": body.captured_at, "data": data},
            where=DeliveryPosition.captured_at < body.captured_at,
        )
    )
    session.commit()
    session.expire_all()
    return snapshot(session, order)
