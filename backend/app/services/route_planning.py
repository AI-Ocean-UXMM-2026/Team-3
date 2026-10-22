"""Persist previews separately; commit approved assignments atomically through existing guards."""

import re
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerRequest
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.rider_models import DeliveryAssignment, RiderProfile
from app.db.routing_models import RoutingPlan, RoutingRateLimit
from app.db.workflow_models import WorkflowRoute
from app.domain.lifecycle import OrderStatus, UserRole
from app.routing.base import RoutingFailure
from app.routing.factory import provider_for
from app.routing.optimizer import optimize
from app.schemas.routing import Coordinate, Geometry, MatrixQuery, RouteQuery, TimeWindow
from app.services.buyer_confirmation import YANGON, lock_order
from app.services.workflow import parcel, prepare_assignment, route_row, set_parcel


def dispatcher(actor):
    if actor.role not in {UserRole.ADMIN, UserRole.DISPATCHER}:
        raise OrderAPIError(403, "ROUTING_ROLE_FORBIDDEN", "Dispatcher authorization is required.")


def charge(session, actor, settings):
    dispatcher(actor)
    session.execute(update(User).where(User.id == actor.id).values(updated_at=User.updated_at))
    bucket = int(utcnow().timestamp()) // 60
    budget = session.get(RoutingRateLimit, actor.id)
    if budget is None:
        budget = RoutingRateLimit(actor_id=actor.id, bucket=bucket, count=0)
        session.add(budget)
    if budget.bucket != bucket:
        budget.bucket, budget.count = bucket, 0
    if budget.count >= settings.routing_requests_per_minute:
        raise OrderAPIError(
            429, "ROUTING_BUDGET_EXCEEDED", "Wait before requesting more routing work."
        )
    budget.count += 1
    session.commit()  # Failed provider calls still consume the persistent actor budget.


def snapshots(session, order_ids, rider_ids):
    return {
        "orders": {
            str(i): o.version if (o := session.get(Order, UUID(str(i)))) else None
            for i in order_ids
        },
        "riders": {
            str(i): {
                "version": p.version,
                "queue_version": p.queue_version,
                "status": p.operational_status,
            }
            for i in rider_ids
            if (p := session.get(RiderProfile, UUID(str(i)))) is not None
        },
    }


def stale(session, plan, settings):
    data = plan.data
    if plan.state == "PREVIEW" and utcnow() > plan.created_at + timedelta(
        minutes=settings.routing_plan_ttl_minutes
    ):
        return True
    return snapshots(session, data["basis"]["orders"], data["basis"]["riders"]) != data["basis"]


def output(session, plan, settings, rider_id=None):
    data = deepcopy(plan.data)
    result = data["result"]
    if rider_id is not None:
        result["vehicles"] = [v for v in result["vehicles"] if v["rider_id"] == str(rider_id)]
        allowed = {
            str(i)
            for i in session.scalars(
                select(DeliveryAssignment.order_id).where(
                    DeliveryAssignment.rider_id == rider_id, DeliveryAssignment.status == "ACTIVE"
                )
            )
        }
        for vehicle in result["vehicles"]:
            old_count = len(vehicle["stops"])
            vehicle["stops"] = [s for s in vehicle["stops"] if s["order_id"] in allowed]
            if len(vehicle["stops"]) != old_count:
                vehicle["geometry"] = None
                vehicle["geometry_warning"] = (
                    "Historical geometry withheld after assignment changes."
                )
        result["vehicles"] = [v for v in result["vehicles"] if v["stops"]]
        result["unassigned"] = []
    return {
        "id": str(plan.id),
        "version": plan.version,
        "state": plan.state,
        "created_at": plan.created_at,
        "stale": stale(session, plan, settings),
        "origin": data["query"]["origin"],
        "operating_window": data["query"]["operating_window"],
        "result": result,
        "routes": {
            k: v
            for k, v in data.get("routes", {}).items()
            if rider_id is None or k == str(rider_id)
        },
    }


def load_plan(session, identifier):
    plan = session.get(RoutingPlan, identifier)
    if plan is None:
        raise OrderAPIError(404, "ROUTE_PLAN_NOT_FOUND", "Route plan not found.")
    return plan


def preview(session, actor, settings, query, provider=None):
    dispatcher(actor)
    if len(query.orders) > settings.routing_max_stops:
        raise OrderAPIError(
            422, "ROUTING_STOP_LIMIT", "Too many selected orders for this configuration."
        )
    if query.operating_window.end <= utcnow():
        raise OrderAPIError(
            422, "PLANNING_WINDOW_PASSED", "Choose a current or future operating window."
        )
    stops, invalid, profiles = [], [], []
    for rider in query.riders:
        p = session.get(RiderProfile, rider.rider_id)
        if p is None:
            raise OrderAPIError(404, "RIDER_NOT_FOUND", "Selected rider not found.")
        if p.operational_status == "AVAILABLE":
            profiles.append(rider)
    for selected in query.orders:
        order = session.get(Order, selected.order_id)
        if order is None:
            raise OrderAPIError(404, "ORDER_NOT_FOUND", "Selected order not found.")
        reason = None
        context = parcel(order)
        if order.status in {OrderStatus.DELIVERED, OrderStatus.FAILED, OrderStatus.CANCELLED}:
            reason = "TERMINAL_ORDER_EXCLUDED"
        elif order.latitude is None or order.longitude is None:
            reason = "MISSING_DELIVERY_PIN"
        elif any(
            order.field_sources.get(k, {}).get("method")
            not in {"manual_correction", "buyer_confirmation"}
            or order.field_sources.get(k, {}).get("requires_review", False)
            for k in ("latitude", "longitude")
        ):
            reason = "LOCATION_REVIEW_REQUIRED"
        elif order.confidence_level == "RED" or not context.get("hub_received_at"):
            reason = "ADDRESS_REVIEW_OR_HUB_RECEIPT_REQUIRED"
        elif session.scalar(
            select(BuyerRequest.id)
            .where(
                BuyerRequest.order_id == order.id,
                BuyerRequest.decision == "REVIEW_REQUIRED",
                BuyerRequest.resolution.is_(None),
            )
            .limit(1)
        ):
            reason = "BUYER_REVIEW_REQUIRED"
        elif not context.get("delivery_day"):
            reason = "PARCEL_DELIVERY_DAY_REQUIRED"
        elif (
            context["delivery_day"]
            != query.operating_window.start.astimezone(YANGON).date().isoformat()
        ):
            reason = "PARCEL_DELIVERY_DAY_MISMATCH"
        window = None
        if order.delivery_time_window and order.delivery_time_window != "Any time":
            from app.services.workflow import delivery_window

            resolved = delivery_window(order)
            if resolved:
                window = TimeWindow(start=resolved[0], end=resolved[1])
            else:
                # Native MTT clock-only windows are anchored to the parcel delivery day.
                match = re.fullmatch(
                    r"(\d{2}:\d{2})\s*[\u2013-]\s*(\d{2}:\d{2})", order.delivery_time_window
                )
                try:
                    window = (
                        TimeWindow(
                            start=datetime.fromisoformat(
                                context["delivery_day"] + "T" + match[1] + ":00"
                            ).replace(tzinfo=YANGON),
                            end=datetime.fromisoformat(
                                context["delivery_day"] + "T" + match[2] + ":00"
                            ).replace(tzinfo=YANGON),
                        )
                        if match
                        else None
                    )
                except (ValueError, KeyError):
                    window = None
                if window is None:
                    reason = reason or "UNSTRUCTURED_TIME_WINDOW_REQUIRES_REVIEW"
        if reason:
            invalid.append({"order_id": str(order.id), "reason": reason})
            continue
        assignment = session.scalar(
            select(DeliveryAssignment).where(
                DeliveryAssignment.order_id == order.id, DeliveryAssignment.status == "ACTIVE"
            )
        )
        stops.append(
            {
                "order_id": str(order.id),
                "coordinate": Coordinate(
                    latitude=float(order.latitude), longitude=float(order.longitude)
                ),
                "demand": selected.demand,
                "service_seconds": selected.service_seconds,
                "priority": selected.priority,
                "window": window,
                "rider_id": str(assignment.rider_id) if assignment else None,
            }
        )
    basis = snapshots(
        session, [o.order_id for o in query.orders], [r.rider_id for r in query.riders]
    )
    session.commit()  # Release read transactions before bounded provider work.
    provider = provider or provider_for(settings, query.allow_simulation)
    matrix = (
        provider.get_route_matrix(
            MatrixQuery(
                locations=[query.origin] + [s["coordinate"] for s in stops],
                mode=query.mode,
                allow_simulation=query.allow_simulation,
            )
        )
        if stops
        else None
    )
    if matrix is None:
        from app.schemas.routing import OptimizationResult

        result = OptimizationResult(
            solver_status="INFEASIBLE",
            elapsed_ms=0,
            provider=settings.routing_provider,
            quality="SIMULATED" if settings.routing_provider == "offline" else "ROAD_STATIC",
            matrix_size=0,
            vehicles=[],
            unassigned=[],
            warnings=["No eligible stops."],
            attribution="No matrix requested",
        )
    else:
        result = optimize(query, matrix, stops, profiles)
        for vehicle in result.vehicles:
            points = [query.origin] + [
                Coordinate(latitude=s.latitude, longitude=s.longitude) for s in vehicle.stops
            ]
            if query.return_to_hub:
                points.append(query.origin)
            coordinates = []
            try:
                for a, b in zip(points, points[1:]):
                    leg = provider.get_route(
                        RouteQuery(
                            origin=a,
                            destination=b,
                            mode=query.mode,
                            allow_simulation=query.allow_simulation,
                        )
                    )
                    if not leg.geometry:
                        raise RoutingFailure("ROUTING_GEOMETRY_UNAVAILABLE", 502)
                    coordinates.extend(leg.geometry.coordinates)
                    if len(coordinates) > 20000:
                        raise RoutingFailure("ROUTING_GEOMETRY_TOO_LARGE", 502)
                if coordinates:
                    vehicle.geometry = Geometry(coordinates=coordinates)
            except RoutingFailure as exc:
                vehicle.geometry_warning = (
                    f"Geometry unavailable ({exc.code}); matrix estimates retained."
                )
    result.unassigned.extend(invalid)
    if invalid:
        result.solver_status = "PARTIAL" if result.vehicles else "INFEASIBLE"
    plan = RoutingPlan(
        actor_id=actor.id,
        data={
            "query": query.model_dump(mode="json"),
            "basis": basis,
            "input_basis": basis,
            "result": result.model_dump(mode="json"),
        },
    )
    session.add(plan)
    session.commit()
    return output(session, plan, settings)


def commit(session, actor, settings, identifier, body, catalog):
    from app.services.automatic_assignment import lock_allocator

    lock_allocator(session)
    dispatcher(actor)
    session.execute(
        update(RoutingPlan).where(RoutingPlan.id == identifier).values(version=RoutingPlan.version)
    )
    plan = load_plan(session, identifier)
    session.refresh(plan)
    if plan.state == "COMMITTED":
        if body.expected_version not in {plan.version, plan.version - 1}:
            raise OrderAPIError(409, "VERSION_CONFLICT", "Refresh this route plan.")
        return output(session, plan, settings)
    if body.expected_version != plan.version:
        raise OrderAPIError(409, "VERSION_CONFLICT", "Refresh this route plan.")
    for identifier in sorted(plan.data["basis"]["orders"]):
        lock_order(session, UUID(identifier))
    for identifier in sorted(plan.data["basis"]["riders"]):
        session.execute(
            update(RiderProfile)
            .where(RiderProfile.id == UUID(identifier))
            .values(queue_version=RiderProfile.queue_version)
        )
    session.expire_all()
    if stale(session, plan, settings):
        raise OrderAPIError(
            409, "ROUTE_PLAN_STALE", "Orders or riders changed; preview a new plan."
        )
    data = deepcopy(plan.data)
    if not body.acknowledge_unverified_location:
        raise OrderAPIError(
            422, "LOCATION_ACKNOWLEDGEMENT_REQUIRED", "Acknowledge pin accuracy limitations."
        )
    if data["result"]["quality"] == "SIMULATED" and not body.allow_simulation:
        raise OrderAPIError(
            422, "SIMULATION_ACKNOWLEDGEMENT_REQUIRED", "Acknowledge simulated routing data."
        )
    if not data["result"]["vehicles"]:
        raise OrderAPIError(409, "NO_FEASIBLE_STOPS", "No stops can be committed from this plan.")
    for vehicle in data["result"]["vehicles"]:
        rider_id = UUID(vehicle["rider_id"])
        active = list(
            session.scalars(
                select(DeliveryAssignment).where(
                    DeliveryAssignment.rider_id == rider_id, DeliveryAssignment.status == "ACTIVE"
                )
            )
        )
        if any(str(a.order_id) not in {s["order_id"] for s in vehicle["stops"]} for a in active):
            raise OrderAPIError(
                409,
                "INCLUDE_ALL_ACTIVE_STOPS",
                "Include this rider's active stops before committing.",
            )
        route_ids = {parcel(session.get(Order, a.order_id)).get("route_id") for a in active}
        route_ids.discard(None)
        if len(route_ids) > 1:
            raise OrderAPIError(
                409, "MULTIPLE_ACTIVE_ROUTES", "Resolve multiple active routes before replanning."
            )
        route = route_row(session, UUID(next(iter(route_ids))), actor, True) if route_ids else None
        for stop in vehicle["stops"]:
            order = session.get(Order, UUID(stop["order_id"]))
            assignment = session.scalar(
                select(DeliveryAssignment).where(
                    DeliveryAssignment.order_id == order.id, DeliveryAssignment.status == "ACTIVE"
                )
            )
            if assignment is None:
                if route and route.data["state"] != "draft":
                    raise OrderAPIError(
                        409, "DEPARTED_ROUTE", "New parcels cannot be added after departure."
                    )
                prepared = prepare_assignment(
                    session,
                    actor,
                    order.id,
                    SimpleNamespace(
                        request_id=uuid4(),
                        expected_version=order.version,
                        route_id=route.id if route else None,
                        rider_id=None if route else rider_id,
                        receive_at_hub=False,
                        acknowledge_unverified_location=True,
                        model_dump=lambda **_: {"plan_id": str(plan.id), "order_id": str(order.id)},
                    ),
                    settings,
                    catalog,
                    commit=False,
                )
                route = session.get(WorkflowRoute, UUID(prepared["route"]["id"]))
                assignment = session.get(DeliveryAssignment, UUID(prepared["assignment"]["id"]))
            if assignment.rider_id != rider_id:
                raise OrderAPIError(
                    409, "ASSIGNMENT_CHANGED", "Existing rider assignments must be preserved."
                )
            assignment.stop_sequence = stop["sequence"]
            context = parcel(order)
            context["routing"] = {
                "plan_id": str(plan.id),
                "sequence": stop["sequence"],
                "assignment_id": str(assignment.id),
            }
            set_parcel(order, context)
            order.updated_at = utcnow()
            session.add(
                DeliveryEvent(
                    order_id=order.id,
                    event_type="RIDER_SEQUENCE_CHANGED",
                    previous_status=order.status,
                    new_status=order.status,
                    event_metadata={
                        "actor_id": str(actor.id),
                        "plan_id": str(plan.id),
                        "sequence": stop["sequence"],
                    },
                )
            )
        if route is not None:
            # Preserve completed/failed stops while reordering the remaining selected stops.
            route_data = deepcopy(route.data)
            chosen = [s["order_id"] for s in vehicle["stops"]]
            route_data["order_ids"] = [
                i for i in route_data["order_ids"] if i not in chosen
            ] + chosen
            route.data = route_data
            data.setdefault("routes", {})[str(rider_id)] = str(route.id)
        session.get(RiderProfile, rider_id).queue_version += 1
    session.flush()
    data["basis"] = snapshots(session, data["basis"]["orders"], data["basis"]["riders"])
    plan.data, plan.state = data, "COMMITTED"
    session.commit()
    return output(session, plan, settings)
