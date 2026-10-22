"""Local-only, globally bounded single-stop Google estimates. No matrix or result cache."""

import json
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import SecretStr
from sqlalchemy import select

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerRequest
from app.db.models import Order
from app.db.rider_models import DeliveryAssignment
from app.domain.lifecycle import OrderStatus, UserRole
from app.routing.base import RoutingFailure
from app.routing.http import HTTPProvider
from app.schemas.routing import Coordinate, RouteQuery


def permitted(actor):
    if actor.role not in {UserRole.ADMIN, UserRole.DISPATCHER, UserRole.RIDER}:
        raise OrderAPIError(403, "ROUTING_ROLE_FORBIDDEN", "Operational authorization required.")


def enabled(settings):
    return (
        settings.environment in {"local", "test"}
        and settings.google_demo_enabled
        and settings.routing_external_requests_enabled
        and settings.google_demo_max_requests > 0
    )


def status(settings):
    directory = settings.google_demo_budget_directory
    used = sum((directory / f"slot-{i}.json").exists() for i in range(10))
    return {
        "enabled": enabled(settings),
        "maximum_requests": settings.google_demo_max_requests,
        "reserved_requests": used,
        "remaining_requests": max(0, settings.google_demo_max_requests - used),
    }


def reserve(settings, request_id):
    directory = settings.google_demo_budget_directory
    try:
        directory.mkdir(parents=True, exist_ok=True)
        # Global files are shared across workers/actors and survive DB reset/restart.
        if status(settings)["remaining_requests"] == 0:
            raise RoutingFailure("GOOGLE_DEMO_BUDGET_EXHAUSTED", 429)
        try:
            with (directory / f"request-{request_id}.json").open("x", encoding="utf-8") as f:
                json.dump({"reserved": True}, f)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            raise RoutingFailure("GOOGLE_REQUEST_ALREADY_ATTEMPTED", 409) from None
        for i in range(settings.google_demo_max_requests):
            try:
                with (directory / f"slot-{i}.json").open("x", encoding="utf-8") as f:
                    json.dump({"request_id": str(request_id)}, f)
                    f.flush()
                    os.fsync(f.fileno())
                return
            except FileExistsError:
                continue
        raise RoutingFailure("GOOGLE_DEMO_BUDGET_EXHAUSTED", 429)
    except OSError:
        raise RoutingFailure("GOOGLE_DEMO_BUDGET_UNAVAILABLE") from None


def key_for(settings):
    if settings.google_routes_api_key:
        return settings.google_routes_api_key
    # Deliberate local-only reuse of the ignored private file, never a frontend key.
    path = Path(__file__).resolve().parents[2] / ".env.google-demo.local"
    try:
        value = dotenv_values(path).get("GOOGLE_ROUTES_API_KEY") if path.is_file() else None
    except OSError:
        raise RoutingFailure("ROUTING_KEY_UNAVAILABLE") from None
    return SecretStr(value) if value and value.strip() else None


def estimate(session, actor, settings, body, *, transport=None):
    permitted(actor)
    if not enabled(settings):
        raise RoutingFailure("GOOGLE_DEMO_DISABLED")
    order = session.get(Order, body.order_id)
    if order is None:
        raise OrderAPIError(404, "ORDER_NOT_FOUND", "Order not found.")
    if actor.role == UserRole.RIDER and not session.scalar(
        select(DeliveryAssignment.id).where(
            DeliveryAssignment.order_id == order.id,
            DeliveryAssignment.rider_id == actor.id,
            DeliveryAssignment.status == "ACTIVE",
        )
    ):
        raise OrderAPIError(403, "RIDER_ASSIGNMENT_REQUIRED", "Active assignment required.")
    if order.status in {OrderStatus.DELIVERED, OrderStatus.FAILED, OrderStatus.CANCELLED}:
        raise OrderAPIError(409, "ORDER_NOT_ROUTABLE", "A completed order cannot be routed.")
    if (
        order.latitude is None
        or order.longitude is None
        or any(
            order.field_sources.get(k, {}).get("method")
            not in {"manual_correction", "buyer_confirmation"}
            or order.field_sources.get(k, {}).get("requires_review", False)
            for k in ("latitude", "longitude")
        )
        or session.scalar(
            select(BuyerRequest.id)
            .where(
                BuyerRequest.order_id == order.id,
                BuyerRequest.decision == "REVIEW_REQUIRED",
                BuyerRequest.resolution.is_(None),
            )
            .limit(1)
        )
    ):
        raise OrderAPIError(409, "LOCATION_REVIEW_REQUIRED", "Review the delivery pin first.")
    query = RouteQuery(
        origin=body.origin,
        destination=Coordinate(
            latitude=float(order.latitude),
            longitude=float(order.longitude),
        ),
    )
    provider_settings = settings.model_copy(
        update={
            "routing_provider": "google",
            "google_routes_api_key": key_for(settings),
            "routing_two_wheeler_enabled": False,
        }
    )
    provider = HTTPProvider(provider_settings, transport=transport)
    provider.ready("DRIVE")  # Missing keys do not consume a network reservation.
    reserve(settings, body.request_id)
    route = provider.get_route(query)  # Exactly one POST; existing transport retries=0.
    return {
        "observation": "GOOGLE_MOCK" if transport is not None else "GOOGLE_LIVE",
        "order_id": order.id,
        "request_id": body.request_id,
        "route": route,
    }
