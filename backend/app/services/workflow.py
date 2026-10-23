"""Native API extensions for the three-sided delivery workflow.

Uses the same orders, buyers and rider assignments as the supplied APIs. Money
is whole MMK; a rider declaration is never treated as physical hub receipt.
"""

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update

from app.core.order_errors import OrderAPIError
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.workflow_models import WorkflowRoute
from app.domain.lifecycle import OrderStatus, UserRole
from app.services.buyer_confirmation import YANGON, lock_order
from app.services.order_management import OrderManagementService
from app.services.riders import active_assignment, bump_queue
from app.services.workspace_scope import order_scope


def admin(actor):
    if actor.role not in {UserRole.ADMIN, UserRole.DISPATCHER}:
        raise OrderAPIError(403, "ROLE_FORBIDDEN", "Admin access required.")


def parcel(order):
    return deepcopy(order.parsing_metadata.get("parcel", {}))


def set_parcel(order, data):
    order.parsing_metadata = {**order.parsing_metadata, "parcel": data}


def route_row(session, identifier, actor, lock=False):
    row = session.scalar(scoped_routes(session, actor).where(WorkflowRoute.id == identifier))
    if row is None:
        raise OrderAPIError(404, "ROUTE_NOT_FOUND", "Route not found.")
    if lock:
        session.execute(
            update(WorkflowRoute)
            .where(WorkflowRoute.id == identifier)
            .values(version=WorkflowRoute.version)
        )
    row = session.get(WorkflowRoute, identifier)
    if row is None or actor.role == UserRole.RIDER and row.rider_id != actor.id:
        raise OrderAPIError(404, "ROUTE_NOT_FOUND", "Route not found.")
    if actor.role not in {UserRole.ADMIN, UserRole.DISPATCHER, UserRole.RIDER}:
        raise OrderAPIError(403, "ROLE_FORBIDDEN", "Route access is unavailable.")
    session.refresh(row)
    if (
        lock and actor.role in {UserRole.ADMIN, UserRole.DISPATCHER}
        and not row.data.get("hub_account_id")
    ):
        row.data = {**row.data, "hub_account_id": str(actor.id)}
    return row


def scoped_routes(session, actor):
    query = select(WorkflowRoute)
    if actor.role == UserRole.RIDER:
        return query.where(WorkflowRoute.rider_id == actor.id)
    admin(actor)
    owner = WorkflowRoute.data["hub_account_id"].as_string()
    # Older routes have no owner marker. Only recover ownership when every
    # attached parcel belongs to this account; unattributed empty routes stay hidden.
    legacy = session.scalars(query.where(owner.is_(None))).all()
    legacy_ids = []
    if legacy:
        own_orders = {
            str(i) for i in session.scalars(select(Order.id).where(order_scope(actor)))
        }
        legacy_ids = [
            r.id for r in legacy if r.data.get("order_ids")
            and all(i in own_orders for i in r.data["order_ids"])
        ]
    return query.where(or_(owner == str(actor.id), WorkflowRoute.id.in_(legacy_ids)))


def attach_order(session, actor, order, assignment, route_id):
    row = route_row(session, route_id, actor, True)
    data = deepcopy(row.data)
    context = parcel(order)
    if data["state"] != "draft" or row.rider_id != assignment.rider_id:
        raise OrderAPIError(409, "ROUTE_NOT_ASSIGNABLE", "Choose this rider's draft route.")
    if not context.get("hub_received_at"):
        raise OrderAPIError(
            409, "HUB_RECEIPT_REQUIRED", "Record physical hub receipt before assignment."
        )
    if context.get("delivery_day") != data["day"]:
        raise OrderAPIError(
            409, "DELIVERY_DAY_MISMATCH", "Parcel and route delivery days must match."
        )
    if context.get("route_id"):
        raise OrderAPIError(409, "ALREADY_ROUTED", "Parcel already belongs to a route.")
    data["order_ids"].append(str(order.id))
    context["route_id"] = str(row.id)
    row.data = data
    set_parcel(order, context)


def detach_order(session, actor, order):
    context = parcel(order)
    if not context.get("route_id"):
        return
    row = route_row(session, UUID(context["route_id"]), actor, True)
    if row.data["state"] != "draft":
        raise OrderAPIError(409, "ROUTE_DEPARTED", "A departed route cannot be unassigned.")
    data = deepcopy(row.data)
    data["order_ids"] = [i for i in data["order_ids"] if i != str(order.id)]
    row.data = data
    context.pop("route_id", None)
    set_parcel(order, context)


def validate_delivery_route(session, actor, order, action):
    context = parcel(order)
    if not context.get("route_id"):
        return  # Retain the supplied legacy, per-parcel API contract.
    row = route_row(session, UUID(context["route_id"]), actor)
    if row.data["state"] != "dispatched":
        raise OrderAPIError(409, "ROUTE_NOT_DEPARTED", "Admin must dispatch the route first.")
    if action == "DELIVERED":
        if row.data["day"] != utcnow().astimezone(YANGON).date().isoformat():
            raise OrderAPIError(
                409, "WRONG_DELIVERY_DAY", "This route is not scheduled for today (Yangon)."
            )
        window = delivery_window(order)
        if window and not window[0] <= utcnow() < window[1]:
            raise OrderAPIError(
                409, "OUTSIDE_DELIVERY_WINDOW", "Delivery is outside the approved customer window."
            )


def delivery_window(order):
    value = order.delivery_time_window or ""
    if "/" not in value:
        return None
    try:
        start, end = [datetime.fromisoformat(part) for part in value.split("/", 1)]
        return (start, end) if start.tzinfo and end.tzinfo and start < end else None
    except ValueError:
        return None


def record_collection(order, body, actor):
    context = parcel(order)
    actual = body.actual_amount
    if actual is None:
        if context.get("route_id"):
            raise OrderAPIError(
                422,
                "ACTUAL_CASH_REQUIRED",
                "Enter cash actually collected, including zero for prepaid.",
            )
        return
    if order.cod_amount == 0 and actual != 0:
        raise OrderAPIError(422, "PREPAID_ZERO_ONLY", "Prepaid deliveries collect zero cash.")
    expected = int(order.cod_amount)
    if actual != expected and not (body.difference_reason or "").strip():
        raise OrderAPIError(
            422, "DIFFERENCE_REASON_REQUIRED", "Explain the difference from expected COD."
        )
    context["collection"] = {
        "expected": expected,
        "actual": actual,
        "reason": body.difference_reason or "",
        "resolution": None,
        "by": str(actor.id),
        "at": utcnow().isoformat(),
    }
    set_parcel(order, context)


def orders_for(session, row):
    return [session.get(Order, UUID(i)) for i in row.data["order_ids"]]


def closeout_blockers(session, row):
    issues = []
    for order in orders_for(session, row):
        context = parcel(order)
        collection = context.get("collection")
        if order.status != OrderStatus.DELIVERED and not (
            order.status == OrderStatus.FAILED and context.get("return_received_at")
        ):
            issues.append(f"{order.id}: finish delivery or receive physical return")
        if order.status == OrderStatus.DELIVERED and not collection:
            issues.append(f"{order.id}: actual cash collection missing")
        if (
            collection
            and collection["actual"] != collection["expected"]
            and not collection.get("resolution")
        ):
            issues.append(f"{order.id}: resolve collection difference")
        if context.get("incident"):
            issues.append(f"{order.id}: resolve incident")
    return issues


def response(session, row):
    data = deepcopy(row.data)
    data.pop("operations", None)
    items = []
    for order in orders_for(session, row):
        context = parcel(order)
        items.append(
            {
                "id": str(order.id),
                "name": order.customer_name,
                "status": order.status.value,
                "item": context.get("item"),
                "return_received": bool(context.get("return_received_at")),
                "collection": context.get("collection"),
                "incident": context.get("incident"),
            }
        )
    return {
        "id": str(row.id),
        "rider_id": str(row.rider_id),
        "version": row.version,
        **data,
        "items": items,
        "blockers": closeout_blockers(session, row),
        "recorded_total": sum(
            (parcel(o).get("collection") or {}).get("actual", 0) for o in orders_for(session, row)
        ),
    }


def create_route(session, actor, body, *, commit=True):
    admin(actor)
    from app.db.rider_models import RiderProfile

    user = session.get(User, body.rider_id)
    if not user or user.role != UserRole.RIDER or not session.get(RiderProfile, body.rider_id):
        raise OrderAPIError(422, "RIDER_REQUIRED", "Choose an existing rider.")
    if body.day < utcnow().astimezone(YANGON).date():
        raise OrderAPIError(422, "PAST_ROUTE_DAY", "Choose today or a future day.")
    row = WorkflowRoute(
        id=uuid4(),
        rider_id=body.rider_id,
        data={
            "hub_account_id": str(actor.id),
            "day": body.day.isoformat(),
            "state": "draft",
            "order_ids": [],
            "handover": None,
            "events": [],
            "operations": {},
        },
    )
    session.add(row)
    session.flush()
    result = response(session, row)
    if commit:
        session.commit()
    return result


def prepare_assignment(session, actor, identifier, body, settings, catalog, *, commit=True):
    """One transaction for receipt, review, optional route creation and assignment.

    Existing service guards still run. Nothing departs until an explicit DISPATCH.
    A failed/stale attempt must not leave a stray route or half-ready parcel.
    """
    admin(actor)
    from app.services.automatic_assignment import lock_allocator

    lock_allocator(session)
    from app.db.rider_models import DeliveryAssignment
    from app.schemas.management import ChangeStatus, OrderResponse
    from app.schemas.riders import AssignmentResponse, AssignOrder
    from app.services.riders import RiderService

    lock_order(session, identifier)
    management = OrderManagementService(
        session,
        actor,
        catalog,
        require_cod_confirmation=settings.rider_require_cod_confirmation,
        commit=False,
    )
    order = management.get(identifier)
    session.refresh(order)
    context = parcel(order)
    fingerprint = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    receipt = context.get("preparation") or {}

    def result(assignment, route_id):
        return {
            "order": OrderResponse.model_validate(order).model_dump(mode="json"),
            "assignment": AssignmentResponse.model_validate(assignment).model_dump(mode="json"),
            "route": response(session, route_row(session, UUID(str(route_id)), actor)),
        }

    if receipt.get("request_id") == str(body.request_id) and receipt.get("actor_id") == str(
        actor.id
    ):
        if receipt.get("fingerprint") != fingerprint:
            raise OrderAPIError(
                409, "REQUEST_CONFLICT", "Request ID was used with different preparation details."
            )
        assignment = session.get(DeliveryAssignment, UUID(receipt["assignment_id"]))
        return result(assignment, receipt["route_id"])
    management.check_version(order, body.expected_version)
    if order.status not in {
        OrderStatus.DRAFT,
        OrderStatus.NEEDS_REVIEW,
        OrderStatus.AWAITING_CONFIRMATION,
        OrderStatus.CONFIRMED,
        OrderStatus.READY_FOR_DISPATCH,
    } or context.get("route_id"):
        raise OrderAPIError(
            409, "ORDER_NOT_PREPARABLE", "Choose an unassigned, pre-departure parcel."
        )
    if not body.acknowledge_unverified_location:
        raise OrderAPIError(
            422,
            "LOCATION_ACKNOWLEDGEMENT_REQUIRED",
            "Review the delivery point and explicitly acknowledge its unverified map accuracy.",
        )
    if order.latitude is None or order.longitude is None:
        raise OrderAPIError(409, "LOCATION_REQUIRED", "Review and save a delivery point first.")
    if context.get("incident"):
        raise OrderAPIError(409, "INCIDENT_OPEN", "Resolve the parcel incident first.")
    if not context.get("delivery_day"):
        raise OrderAPIError(422, "DELIVERY_DAY_REQUIRED", "Set a parcel delivery day first.")
    if body.receive_at_hub and not context.get("hub_received_at"):
        context["hub_received_at"] = utcnow().isoformat()
        context.setdefault("operations_history", []).append(
            {
                "action": "RECEIVE",
                "at": utcnow().isoformat(),
                "by": str(actor.id),
                "reason": "Explicit physical receipt during prepare and assign",
            }
        )
        set_parcel(order, context)
        session.flush()
    if not context.get("hub_received_at"):
        raise OrderAPIError(
            409,
            "HUB_RECEIPT_REQUIRED",
            "Confirm the parcel is physically at the hub before assignment.",
        )
    if order.status == OrderStatus.DRAFT:
        management.change_status(
            identifier,
            ChangeStatus(expected_version=order.version, status=OrderStatus.NEEDS_REVIEW),
        )
    if order.status in {OrderStatus.NEEDS_REVIEW, OrderStatus.AWAITING_CONFIRMATION}:
        management.change_status(
            identifier, ChangeStatus(expected_version=order.version, status=OrderStatus.CONFIRMED)
        )
    if order.status == OrderStatus.CONFIRMED:
        management.change_status(
            identifier,
            ChangeStatus(
                expected_version=order.version,
                status=OrderStatus.READY_FOR_DISPATCH,
                acknowledge_unverified_location=True,
            ),
        )
    rider_service = RiderService(session, actor, settings, catalog, commit=False)
    if body.route_id:
        route = route_row(session, body.route_id, actor, True)
    else:
        created = create_route(
            session,
            actor,
            SimpleNamespace(
                rider_id=body.rider_id, day=date.fromisoformat(context["delivery_day"])
            ),
            commit=False,
        )
        route = route_row(session, UUID(created["id"]), actor, True)
    assigned = rider_service.assign(
        identifier,
        AssignOrder(
            expected_version=order.version,
            rider_id=route.rider_id,
            route_id=route.id,
            stop_sequence=len(route.data["order_ids"]) + 1,
        ),
    )
    context = parcel(order)
    context["preparation"] = {
        "request_id": str(body.request_id),
        "actor_id": str(actor.id),
        "fingerprint": fingerprint,
        "route_id": str(route.id),
        "assignment_id": str(assigned["assignment"].id),
    }
    set_parcel(order, context)
    session.flush()
    assignment = session.get(DeliveryAssignment, assigned["assignment"].id)
    output = result(assignment, route.id)
    if commit:
        session.commit()
    return output


def route_action(session, actor, identifier, body):
    from app.services.automatic_assignment import lock_allocator

    lock_allocator(session)
    row = route_row(session, identifier, actor, True)
    data = deepcopy(row.data)
    fingerprint = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    key = f"{actor.id}:{body.request_id}"
    previous = data["operations"].get(key)
    if previous:
        if previous != fingerprint:
            raise OrderAPIError(
                409, "REQUEST_CONFLICT", "Request ID was already used with different data."
            )
        return response(session, row)
    if body.expected_version != row.version:
        raise OrderAPIError(409, "VERSION_CONFLICT", "Route changed; refresh before saving.")
    if data["state"] == "closed":
        raise OrderAPIError(409, "ROUTE_CLOSED", "This route is already closed.")
    if body.action == "HANDOVER":
        if actor.role != UserRole.RIDER or actor.id != row.rider_id:
            raise OrderAPIError(
                403, "ASSIGNED_RIDER_REQUIRED", "Only the assigned rider can hand over cash."
            )
    else:
        admin(actor)
    orders = orders_for(session, row)
    total = sum((parcel(o).get("collection") or {}).get("actual", 0) for o in orders)
    if body.action == "DISPATCH":
        if data["state"] != "draft" or not orders:
            raise OrderAPIError(409, "NONEMPTY_DRAFT_REQUIRED", "Choose a nonempty draft route.")
        if data["day"] != utcnow().astimezone(YANGON).date().isoformat():
            raise OrderAPIError(
                409,
                "WRONG_DELIVERY_DAY",
                "Departure is allowed only on the route's Yangon delivery day.",
            )
        for order in orders:
            lock_order(session, order.id)
            session.refresh(order)
            context = parcel(order)
            assignment = active_assignment(session, order.id)
            if assignment and assignment.response_status != "ACCEPTED":
                raise OrderAPIError(
                    409,
                    "OFFER_ACCEPTANCE_REQUIRED",
                    "Every rider offer must be accepted before departure.",
                )
            if assignment:
                from app.services.automatic_assignment import require_current_authorization

                require_current_authorization(session, order, assignment)
            if (
                order.status != OrderStatus.ASSIGNED
                or not assignment
                or assignment.rider_id != row.rider_id
                or not context.get("hub_received_at")
                or context.get("delivery_day") != data["day"]
                or context.get("incident")
            ):
                raise OrderAPIError(
                    409,
                    "PARCEL_NOT_READY",
                    (
                        f"{order.id}: check assignment, physical hub receipt, "
                        "delivery day and incidents."
                    ),
                )
            window = delivery_window(order)
            if window and utcnow() >= window[1]:
                raise OrderAPIError(
                    409, "DELIVERY_WINDOW_ENDED", f"{order.id}: approved delivery window has ended."
                )
            order.status = OrderStatus.OUT_FOR_DELIVERY
            session.add(
                DeliveryEvent(
                    order_id=order.id,
                    event_type="DELIVERY_STARTED",
                    previous_status=OrderStatus.ASSIGNED,
                    new_status=order.status,
                    event_metadata={"actor_id": str(actor.id), "route_id": str(row.id)},
                )
            )
        bump_queue(session, row.rider_id)
        data["state"] = "dispatched"
    elif body.action == "HANDOVER":
        if (
            data["state"] not in {"dispatched", "closing"}
            or (data.get("handover") or {}).get("status") == "received"
        ):
            raise OrderAPIError(
                409,
                "HANDOVER_NOT_ALLOWED",
                "Cash is already received or the route has not departed.",
            )
        unfinished = [
            o
            for o in orders
            if o.status != OrderStatus.DELIVERED
            and not (o.status == OrderStatus.FAILED and parcel(o).get("return_received_at"))
        ]
        if unfinished:
            raise OrderAPIError(
                409,
                "STOPS_INCOMPLETE",
                "Finish all stops and receive physical returns before handover.",
            )
        if body.amount is None or body.recorded_total != total:
            raise OrderAPIError(409, "CASH_CHANGED", "Refresh and review the recorded cash total.")
        if body.amount != total and not (body.reason or "").strip():
            raise OrderAPIError(
                422, "DIFFERENCE_REASON_REQUIRED", "Explain the handover cash difference."
            )
        data.setdefault("handover_history", []).append(deepcopy(data.get("handover")))
        data["handover"] = {
            "declared": body.amount,
            "recorded": total,
            "reason": body.reason or "",
            "status": "submitted",
            "by": str(actor.id),
        }
        data["state"] = "closing"
    elif body.action == "RECEIVE_CLOSE":
        handover = data.get("handover")
        if (
            data["state"] != "closing"
            or not handover
            or handover["status"] not in {"submitted", "disputed"}
        ):
            raise OrderAPIError(409, "HANDOVER_REQUIRED", "Rider must submit handover first.")
        if body.amount is None:
            raise OrderAPIError(
                422,
                "ACTUAL_RECEIPT_REQUIRED",
                "Enter the amount physically counted, including zero.",
            )
        differs = body.amount != handover["declared"] or body.amount != total
        if differs and not (body.reason or "").strip():
            raise OrderAPIError(
                422, "DIFFERENCE_REASON_REQUIRED", "Explain the hub receipt difference."
            )
        handover.update(
            received=body.amount,
            status="disputed" if differs and not body.resolve else "received",
            received_by=str(actor.id),
            resolution=body.reason if body.resolve else None,
        )
        data.setdefault("receipt_history", []).append(
            {
                "amount": body.amount,
                "by": str(actor.id),
                "at": utcnow().isoformat(),
                "reason": body.reason,
                "resolved": body.resolve,
            }
        )
        if handover["status"] == "received" and not closeout_blockers(session, row):
            data["state"] = "closed"
    elif body.action == "CLOSE":
        if (
            data["state"] != "closing"
            or (data.get("handover") or {}).get("status") != "received"
            or closeout_blockers(session, row)
        ):
            raise OrderAPIError(
                409,
                "CLOSEOUT_BLOCKED",
                "Resolve parcels, returns, incidents and cash differences first.",
            )
        data["state"] = "closed"
    data["operations"][key] = fingerprint
    data["events"].append(
        {
            "action": body.action,
            "by": str(actor.id),
            "at": utcnow().isoformat(),
            "reason": body.reason,
        }
    )
    if data["state"] == "closed":
        data["closed_at"] = utcnow().isoformat()
        data["events"].append({"action": "CLOSED", "by": str(actor.id), "at": data["closed_at"]})
    row.data = data
    session.flush()
    result = response(session, row)
    session.commit()
    return result


def order_operation(session, actor, identifier, body):
    admin(actor)
    from app.services.automatic_assignment import lock_allocator

    lock_allocator(session)
    lock_order(session, identifier)
    order = OrderManagementService(session, actor, None).get(identifier)
    session.refresh(order)
    OrderManagementService.check_version(order, body.expected_version)
    context = parcel(order)
    if context.get("route_id") and body.action != "REMOVE_FROM_BOARD":
        row = route_row(session, UUID(context["route_id"]), actor, True)
        if row.data["state"] == "closed":
            raise OrderAPIError(
                409, "ROUTE_CLOSED", "Closed cash and custody records cannot be changed."
            )
    if body.action == "REMOVE_FROM_BOARD":
        context["dispatcher_deleted_at"] = utcnow().isoformat()
        OrderManagementService(session, actor, None).event(
            order, "ORDER_CORRECTED", order.status, {"action": "REMOVE_FROM_BOARD"}
        )
    elif body.action == "RECEIVE":
        if order.status in {
            OrderStatus.OUT_FOR_DELIVERY,
            OrderStatus.DELIVERED,
            OrderStatus.FAILED,
            OrderStatus.CANCELLED,
        }:
            raise OrderAPIError(409, "RECEIPT_NOT_ALLOWED", "Receive the parcel before departure.")
        context["hub_received_at"] = context.get("hub_received_at") or utcnow().isoformat()
    elif body.action == "RETURN_RECEIVED":
        if order.status != OrderStatus.FAILED:
            raise OrderAPIError(
                409,
                "RETURN_NOT_ALLOWED",
                "Record a failed delivery before receiving its physical return.",
            )
        context["return_received_at"] = context.get("return_received_at") or utcnow().isoformat()
    else:
        if not (body.reason or "").strip():
            raise OrderAPIError(422, "REASON_REQUIRED", "Enter a review or resolution reason.")
        if body.action == "RESOLVE_DIFFERENCE":
            if not context.get("collection"):
                raise OrderAPIError(409, "NO_COLLECTION", "No cash collection to review.")
            context["collection"]["resolution"] = {
                "reason": body.reason,
                "by": str(actor.id),
                "at": utcnow().isoformat(),
            }
        elif body.action == "INCIDENT":
            context["incident"] = body.reason
        elif body.action == "RESOLVE_INCIDENT":
            context["incident"] = None
    context.setdefault("operations_history", []).append(
        {
            "action": body.action,
            "at": utcnow().isoformat(),
            "by": str(actor.id),
            "reason": body.reason,
        }
    )
    set_parcel(order, context)
    session.flush()
    from app.schemas.management import OrderResponse

    result = OrderResponse.model_validate(order)
    session.commit()
    return result
