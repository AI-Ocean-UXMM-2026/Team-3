"""Authoritative, bounded allocation. Lock coordinator BEFORE orders/routes/profiles.

Availability/completion drains run only AFTER their original transaction commits.
Every retry rechecks the customer response and reviewed material delivery data.
"""

import asyncio
import hashlib
import json
import logging
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerRequest, ConfirmationLink
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.rider_models import (
    AllocationCoordinator,
    AllocationReceipt,
    AutomaticAllocation,
    DeliveryAssignment,
    RiderProfile,
)
from app.domain.lifecycle import OrderStatus, UserRole
from app.schemas.management import ChangeStatus, OrderResponse
from app.schemas.riders import AssignmentResponse
from app.services.buyer_confirmation import YANGON, lock_order
from app.services.order_management import OrderManagementService, recalculate

logger = logging.getLogger(__name__)

WAITING = ("WAITING_FOR_RIDER", "WAITING_FOR_READINESS")
PREDEPARTURE = {
    OrderStatus.DRAFT,
    OrderStatus.NEEDS_REVIEW,
    OrderStatus.AWAITING_CONFIRMATION,
    OrderStatus.CONFIRMED,
    OrderStatus.READY_FOR_DISPATCH,
}


def lock_allocator(session):
    # Also supports create_all databases used by local integrations. Native UPSERT
    # avoids a check/insert race. This lock is held until transaction completion.
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    session.execute(insert(AllocationCoordinator).values(id=1).on_conflict_do_nothing())
    session.execute(update(AllocationCoordinator).where(AllocationCoordinator.id == 1).values(id=1))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def material_hash(order):
    from app.services.workflow import parcel

    return digest(
        {
            name: getattr(order, name)
            for name in (
                "customer_name",
                "customer_phone",
                "township",
                "street",
                "landmark",
                "building_floor_unit",
                "delivery_instructions",
                "delivery_time_window",
                "latitude",
                "longitude",
                "cod_amount",
            )
        }
        | {"delivery_day": parcel(order).get("delivery_day")}
    )


def customer_response(session, order):
    pending = session.scalar(
        select(BuyerRequest.id)
        .where(
            BuyerRequest.order_id == order.id,
            BuyerRequest.decision == "REVIEW_REQUIRED",
            BuyerRequest.resolution.is_(None),
        )
        .limit(1)
    )
    if pending:
        return None, "Resolve pending customer requests before reconfirming."
    # A rejected later request leaves the previous applied response effective.
    row = session.scalar(
        select(BuyerRequest)
        .where(
            BuyerRequest.order_id == order.id,
            BuyerRequest.kind == "RESPONSE",
            (BuyerRequest.decision == "APPLIED") | (BuyerRequest.resolution == "APPROVE"),
        )
        .order_by(BuyerRequest.created_at.desc(), BuyerRequest.id.desc())
        .limit(1)
    )
    if not row or row.submitted_values.get("action") not in {"AVAILABLE", "RESCHEDULE"}:
        return None, "A recorded customer availability response is required."
    link = session.get(ConfirmationLink, row.link_id)
    if not link or link.revoked_at:
        active_link = session.scalar(
            select(ConfirmationLink.id)
            .where(
                ConfirmationLink.order_id == order.id,
                ConfirmationLink.revoked_at.is_(None),
            )
            .limit(1)
        )
        if not active_link:
            return None, "Customer confirmation was revoked; request a new response."
    return row, None


def require_current_authorization(session, order, assignment):
    pending = session.scalar(select(BuyerRequest.id).where(
        BuyerRequest.order_id == order.id,
        BuyerRequest.decision == "REVIEW_REQUIRED",
        BuyerRequest.resolution.is_(None),
    ).limit(1))
    if pending:
        raise OrderAPIError(409, "RECONFIRMATION_REQUIRED", "Resolve pending customer requests before continuing delivery.")
    if assignment.allocation_cycle is None:
        return
    allocation = session.get(AutomaticAllocation, order.id)
    buyer, issue = customer_response(session, order)
    if (
        issue
        or allocation is None
        or buyer.id != allocation.buyer_response_id
        or assignment.allocation_cycle != allocation.cycle
        or material_hash(order) != allocation.material_hash
    ):
        raise OrderAPIError(
            409,
            "RECONFIRMATION_REQUIRED",
            issue or "Customer details changed; dispatcher reconfirmation is required.",
        )


def project(order, allocation):
    from app.services.workflow import parcel, set_parcel

    context = parcel(order)
    context["allocation"] = {
        "status": allocation.status,
        "reason": allocation.reason,
        "cycle": allocation.cycle,
        "buyer_response_id": str(allocation.buyer_response_id),
        "dispatcher_id": str(allocation.dispatcher_id),
    }
    set_parcel(order, context)


def output(session, order, allocation, assignment=None):
    from app.db.workflow_models import WorkflowRoute
    from app.services.workflow import parcel, response

    session.flush()
    route_id = parcel(order).get("route_id")
    return {
        "order": OrderResponse.model_validate(order).model_dump(mode="json"),
        "allocation_status": allocation.status,
        "reason": allocation.reason,
        "assignment": AssignmentResponse.model_validate(assignment).model_dump(mode="json")
        if assignment
        else None,
        "route": response(session, session.get(WorkflowRoute, UUID(route_id)))
        if route_id
        else None,
    }


def readiness(order, catalog):
    from app.services.workflow import parcel

    context = parcel(order)
    if not context.get("hub_received_at"):
        return "Confirm physical hub receipt before allocation."
    if context.get("incident"):
        return "Resolve the parcel incident before allocation."
    if not context.get("delivery_day"):
        return "Set a delivery day before allocation."
    if date.fromisoformat(context["delivery_day"]) < utcnow().astimezone(YANGON).date():
        return "Delivery day has passed; review and reconfirm the schedule."
    if order.latitude is None or order.longitude is None:
        return "Review and save a delivery point before allocation."
    recalculate(order, catalog)
    if order.confidence_level == "RED" or not order.customer_phone or not order.township:
        return "Critical delivery details require dispatcher review."
    if order.cod_amount is None:
        return "Set an explicit COD amount, including zero for prepaid."
    return None


def attempt(session, order, allocation, actor, settings, catalog):
    """Single bounded attempt; caller owns coordinator and order locks."""
    from app.db.workflow_models import WorkflowRoute
    from app.services.riders import active_assignment, lock_profile
    from app.services.workflow import parcel

    owner = session.get(User, allocation.dispatcher_id)
    if owner is None or not session.scalar(
        OrderManagementService(session, owner, catalog).scoped().where(Order.id == order.id)
    ):
        allocation.status = "CANCELLED"
        allocation.reason = "The owning hub must reconfirm this order."
        project(order, allocation)
        return None
    buyer, issue = customer_response(session, order)
    if (
        issue
        or buyer.id != allocation.buyer_response_id
        or material_hash(order) != allocation.material_hash
    ):
        allocation.status = "WAITING_FOR_READINESS"
        allocation.reason = (
            issue or "Customer details changed; dispatcher reconfirmation is required."
        )
        project(order, allocation)
        return None
    if order.status not in PREDEPARTURE or active_assignment(session, order.id):
        allocation.status, allocation.reason = (
            "CANCELLED",
            "Order is no longer available for allocation.",
        )
        project(order, allocation)
        return None
    issue = readiness(order, catalog)
    if issue:
        allocation.status, allocation.reason = "WAITING_FOR_READINESS", issue
        project(order, allocation)
        return None
    management = OrderManagementService(
        session, session.get(User, allocation.dispatcher_id), catalog, commit=False
    )
    if order.status == OrderStatus.DRAFT:
        management.change_status(
            order.id, ChangeStatus(expected_version=order.version, status=OrderStatus.NEEDS_REVIEW)
        )
    if order.status in {OrderStatus.NEEDS_REVIEW, OrderStatus.AWAITING_CONFIRMATION}:
        management.change_status(
            order.id, ChangeStatus(expected_version=order.version, status=OrderStatus.CONFIRMED)
        )
    if order.status == OrderStatus.CONFIRMED:
        management.change_status(
            order.id,
            ChangeStatus(
                expected_version=order.version,
                status=OrderStatus.READY_FOR_DISPATCH,
                acknowledge_unverified_location=True,
            ),
        )
    excluded = set(
        session.scalars(
            select(DeliveryAssignment.rider_id).where(
                DeliveryAssignment.order_id == order.id,
                DeliveryAssignment.allocation_cycle == allocation.cycle,
                DeliveryAssignment.response_status == "DECLINED",
            )
        )
    )
    candidates = session.scalars(
        select(RiderProfile.id)
        .join(User, User.id == RiderProfile.id)
        .where(
            RiderProfile.operational_status == "AVAILABLE",
            User.role == UserRole.RIDER,
            ~select(DeliveryAssignment.id)
            .where(
                DeliveryAssignment.rider_id == RiderProfile.id,
                DeliveryAssignment.status == "ACTIVE",
            )
            .exists(),
        )
        .order_by(RiderProfile.id)
    ).all()
    chosen = None
    for identifier in candidates:
        if identifier in excluded:
            continue
        lock_profile(session, identifier)
        profile = session.get(RiderProfile, identifier)
        session.refresh(profile)
        busy = session.scalar(
            select(DeliveryAssignment.id)
            .where(
                DeliveryAssignment.rider_id == identifier,
                DeliveryAssignment.status == "ACTIVE",
            )
            .limit(1)
        )
        if profile.operational_status == "AVAILABLE" and not busy:
            chosen = profile
            break
    if chosen is None:
        allocation.status = "WAITING_FOR_RIDER"
        allocation.reason = (
            "Waiting for an available rider with no active assignment or pending offer."
        )
        project(order, allocation)
        return None
    context = parcel(order)
    route = WorkflowRoute(
        id=uuid4(),
        rider_id=chosen.id,
        data={
            "hub_account_id": str(allocation.dispatcher_id),
            "day": context["delivery_day"],
            "state": "draft",
            "order_ids": [],
            "handover": None,
            "events": [],
            "operations": {},
        },
    )
    session.add(route)
    assignment = DeliveryAssignment(
        id=uuid4(),
        order_id=order.id,
        rider_id=chosen.id,
        dispatcher_id=allocation.dispatcher_id,
        response_status="PENDING",
        allocation_cycle=allocation.cycle,
        stop_sequence=1,
    )
    session.add(assignment)
    session.flush()
    # attach_order's actor check is intentionally not used for a replacement
    # chosen on a declining rider's behalf; membership is constructed internally.
    route.data = {**route.data, "order_ids": [str(order.id)]}
    context["route_id"] = str(route.id)
    from app.services.workflow import set_parcel

    set_parcel(order, context)
    previous, order.status = order.status, OrderStatus.ASSIGNED
    chosen.queue_version += 1
    allocation.status, allocation.reason = (
        "ASSIGNED",
        "Rider offer is awaiting explicit acceptance.",
    )
    project(order, allocation)
    session.add(
        DeliveryEvent(
            order_id=order.id,
            event_type="RIDER_ASSIGNED",
            previous_status=previous,
            new_status=order.status,
            event_metadata={
                "actor_id": str(actor.id) if actor.id else None,
                "actor_role": actor.role.value,
                "dispatcher_id": str(allocation.dispatcher_id),
                "assignment_id": str(assignment.id),
                "rider_id": str(chosen.id),
                "allocation_cycle": allocation.cycle,
                "response_status": "PENDING",
            },
        )
    )
    return assignment


def reconfirm(session, actor, identifier, body, settings, catalog):
    from app.services.workflow import admin, parcel, set_parcel

    admin(actor)
    lock_allocator(session)
    OrderManagementService(session, actor, catalog).get(identifier)
    lock_order(session, identifier)
    fingerprint = digest({"order_id": str(identifier), **body.model_dump(mode="json")})
    receipt = session.scalar(
        select(AllocationReceipt).where(
            AllocationReceipt.actor_id == actor.id,
            AllocationReceipt.request_id == body.request_id,
        )
    )
    if receipt:
        if receipt.payload_hash != fingerprint:
            raise OrderAPIError(
                409,
                "REQUEST_CONFLICT",
                "Request ID was used with different reconfirmation details.",
            )
        return receipt.result
    order = session.get(Order, identifier)
    if order is None:
        raise OrderAPIError(404, "ORDER_NOT_FOUND", "Order not found.")
    session.refresh(order)
    OrderManagementService.check_version(order, body.expected_version)
    if order.status not in PREDEPARTURE or parcel(order).get("route_id"):
        raise OrderAPIError(
            409, "ORDER_NOT_PREPARABLE", "Choose an unassigned, pre-departure parcel."
        )
    if not body.acknowledge_unverified_location:
        raise OrderAPIError(
            422,
            "LOCATION_ACKNOWLEDGEMENT_REQUIRED",
            "Explicitly acknowledge review of the delivery location.",
        )
    buyer, issue = customer_response(session, order)
    if issue:
        raise OrderAPIError(409, "CUSTOMER_RESPONSE_REQUIRED", issue)
    allocation = session.get(AutomaticAllocation, identifier)
    current_hash = material_hash(order)
    if allocation is None:
        allocation = AutomaticAllocation(
            order_id=identifier,
            dispatcher_id=actor.id,
            buyer_response_id=buyer.id,
            material_hash=current_hash,
            cycle=1,
            status="WAITING_FOR_READINESS",
            reason="Dispatcher reconfirmed the customer response.",
        )
        session.add(allocation)
    elif allocation.buyer_response_id != buyer.id or allocation.material_hash != current_hash:
        allocation.cycle += 1
        allocation.buyer_response_id, allocation.material_hash = buyer.id, current_hash
    allocation.dispatcher_id = actor.id
    if body.receive_at_hub:
        context = parcel(order)
        if not context.get("hub_received_at"):
            context["hub_received_at"] = utcnow().isoformat()
            context.setdefault("operations_history", []).append(
                {
                    "action": "RECEIVE",
                    "at": utcnow().isoformat(),
                    "by": str(actor.id),
                    "reason": "Explicit physical receipt during reconfirmation",
                }
            )
            set_parcel(order, context)
    session.add(
        DeliveryEvent(
            order_id=order.id,
            event_type="STATUS_CHANGED",
            previous_status=order.status,
            new_status=order.status,
            event_metadata={
                "action": "DISPATCHER_RECONFIRMED",
                "actor_id": str(actor.id),
                "buyer_response_id": str(buyer.id),
                "allocation_cycle": allocation.cycle,
            },
        )
    )
    assignment = attempt(session, order, allocation, actor, settings, catalog)
    result = output(session, order, allocation, assignment)
    session.add(
        AllocationReceipt(
            actor_id=actor.id,
            order_id=identifier,
            request_id=body.request_id,
            payload_hash=fingerprint,
            result=result,
        )
    )
    session.commit()
    return result


def drain_waiting(session, settings, catalog, *, limit=50):
    """Call with a fresh transaction only; bounded and oldest-first, safe on restart."""
    lock_allocator(session)
    rows = session.scalars(
        select(AutomaticAllocation)
        .where(
            AutomaticAllocation.status.in_(WAITING),
        )
        .order_by(
            AutomaticAllocation.updated_at,
            AutomaticAllocation.created_at,
            AutomaticAllocation.order_id,
        )
        .limit(limit)
    ).all()
    for allocation in rows:
        lock_order(session, allocation.order_id)
        order = session.get(Order, allocation.order_id)
        session.refresh(order)
        actor = session.get(User, allocation.dispatcher_id)
        if actor.role not in {UserRole.ADMIN, UserRole.DISPATCHER}:
            allocation.status, allocation.reason = (
                "CANCELLED",
                "Dispatcher authorization is no longer valid.",
            )
            project(order, allocation)
        else:
            system = SimpleNamespace(id=None, role=SimpleNamespace(value="SYSTEM"))
            attempt(session, order, allocation, system, settings, catalog)
        allocation.updated_at = utcnow()
    session.commit()


def recover_waiting(database, settings, catalog):
    """Independent transaction; log no order, phone or database exception text."""
    try:
        with database.sessions() as session:
            drain_waiting(session, settings, catalog)
    except Exception as exc:
        logger.warning("Automatic allocation recovery deferred: %s", type(exc).__name__)


async def recovery_worker(database, settings, catalog, stop):
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except TimeoutError:
            await asyncio.to_thread(recover_waiting, database, settings, catalog)
