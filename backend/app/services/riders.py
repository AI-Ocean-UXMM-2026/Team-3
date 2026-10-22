import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

from sqlalchemy import func, select, update

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerRequest
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.db.rider_models import DeliveryAssignment, RiderActionReceipt, RiderProfile
from app.domain.lifecycle import ALLOWED_TRANSITIONS, OrderStatus, UserRole
from app.schemas.riders import ActionResult, AssignmentResponse, QueueDelivery, RiderResponse
from app.services.buyer_confirmation import delivery_link_policy, lock_order
from app.services.order_management import OrderManagementService, recalculate


def active_assignment(session, order_id):
    return session.scalar(
        select(DeliveryAssignment).where(
            DeliveryAssignment.order_id == order_id, DeliveryAssignment.status == "ACTIVE"
        )
    )


def lock_profile(session, rider_id):
    session.execute(
        update(RiderProfile)
        .where(RiderProfile.id == rider_id)
        .values(version=RiderProfile.version, updated_at=RiderProfile.updated_at)
    )


def bump_queue(session, rider_id):
    lock_profile(session, rider_id)
    profile = session.get(RiderProfile, rider_id)
    session.refresh(profile)
    profile.queue_version += 1


def dispatcher_status_guard(session, order, target):
    if active_assignment(session, order.id) and target in {
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.DELIVERED,
        OrderStatus.FAILED,
    }:
        raise OrderAPIError(
            409, "USE_RIDER_DELIVERY_ACTION", "Use the assigned rider delivery action endpoint."
        )


def dispatcher_status_sync(session, order, actor, previous):
    assignment = active_assignment(session, order.id)
    if assignment and order.status in {OrderStatus.READY_FOR_DISPATCH, OrderStatus.CANCELLED}:
        assignment.status = "CANCELLED" if order.status == OrderStatus.CANCELLED else "UNASSIGNED"
        assignment.ended_at = utcnow()
        bump_queue(session, assignment.rider_id)
        session.add(
            DeliveryEvent(
                order_id=order.id,
                event_type="RIDER_UNASSIGNED",
                previous_status=previous,
                new_status=order.status,
                event_metadata={
                    "actor_id": str(actor.id),
                    "actor_role": actor.role.value,
                    "rider_id": str(assignment.rider_id),
                    "assignment_id": str(assignment.id),
                },
            )
        )


class RiderService:
    def __init__(self, session, actor, settings, catalog, *, commit=True):
        self.session, self.actor, self.settings, self.catalog = session, actor, settings, catalog
        self.commit = commit

    def dispatcher(self):
        if self.actor.role not in {UserRole.DISPATCHER, UserRole.ADMIN}:
            raise OrderAPIError(403, "ROLE_FORBIDDEN", "Dispatcher or admin access is required.")

    def rider(self, rider_id):
        if self.actor.role == UserRole.RIDER and self.actor.id != rider_id:
            raise OrderAPIError(404, "RIDER_NOT_FOUND", "Rider not found.")
        profile = self.session.get(RiderProfile, rider_id)
        user = self.session.get(User, rider_id)
        if profile is None or user is None or user.role != UserRole.RIDER:
            raise OrderAPIError(404, "RIDER_NOT_FOUND", "Rider not found.")
        return profile, user

    def rider_response(self, profile, user):
        return RiderResponse(
            id=profile.id,
            name=user.name,
            email=None if user.email.endswith("@riders.invalid") else user.email,
            contact_phone=profile.contact_phone,
            operational_status=profile.operational_status,
            version=profile.version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def create(self, body):
        self.dispatcher()
        identifier = uuid4()
        user = User(
            id=identifier,
            name=body.name,
            email=body.email or f"{identifier}@riders.invalid",
            role=UserRole.RIDER,
        )
        self.session.add(user)
        self.session.flush()
        profile = RiderProfile(
            id=identifier,
            contact_phone=body.contact_phone,
            operational_status=body.operational_status,
        )
        self.session.add(profile)
        self.session.flush()
        result = self.rider_response(profile, user)
        self.session.commit()
        return result

    def list(self, page, page_size, operational_status=None):
        query = (
            select(RiderProfile, User)
            .join(User, RiderProfile.id == User.id)
            .where(User.role == UserRole.RIDER)
        )
        if self.actor.role == UserRole.RIDER:
            query = query.where(RiderProfile.id == self.actor.id)
        if operational_status:
            query = query.where(RiderProfile.operational_status == operational_status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.session.execute(
            query.order_by(User.name, User.id).offset((page - 1) * page_size).limit(page_size)
        )
        return {
            "items": [self.rider_response(profile, user) for profile, user in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def patch(self, rider_id, body):
        profile, user = self.rider(rider_id)
        lock_profile(self.session, rider_id)
        self.session.refresh(profile)
        if profile.version != body.expected_version:
            raise OrderAPIError(
                409, "VERSION_CONFLICT", "Rider changed; retrieve the latest version."
            )
        if profile.operational_status != body.operational_status:
            profile.operational_status = body.operational_status
            profile.queue_version += 1
        self.session.flush()
        result = self.rider_response(profile, user)
        self.session.commit()
        return result

    def order(self, order_id, expected):
        lock_order(self.session, order_id)
        order = self.session.get(Order, order_id)
        if order is None:
            raise OrderAPIError(404, "ORDER_NOT_FOUND", "Order not found.")
        self.session.refresh(order)
        OrderManagementService.check_version(order, expected)
        return order

    def event(self, order, assignment, kind, previous, extra=None):
        self.session.add(
            DeliveryEvent(
                order_id=order.id,
                event_type=kind,
                previous_status=previous,
                new_status=order.status,
                event_metadata={
                    "actor_id": str(self.actor.id),
                    "actor_role": self.actor.role.value,
                    "rider_id": str(assignment.rider_id),
                    "assignment_id": str(assignment.id),
                    **(extra or {}),
                },
            )
        )

    def assignment_result(self, order, assignment):
        self.session.flush()
        result = {
            "assignment": AssignmentResponse.model_validate(assignment),
            "order_status": order.status,
            "order_version": order.version,
        }
        if self.commit:
            self.session.commit()
        return result

    def assign(self, order_id, body):
        self.dispatcher()
        order = self.order(order_id, body.expected_version)
        profile, _ = self.rider(body.rider_id)
        lock_profile(self.session, profile.id)
        self.session.refresh(profile)
        if profile.operational_status != "AVAILABLE":
            raise OrderAPIError(
                409, "RIDER_NOT_AVAILABLE", "Rider must be available for assignment."
            )
        if order.status != OrderStatus.READY_FOR_DISPATCH or active_assignment(
            self.session, order.id
        ):
            raise OrderAPIError(
                409, "ORDER_NOT_ASSIGNABLE", "Order must be ready and not already assigned."
            )
        pending = self.session.scalar(
            select(BuyerRequest.id)
            .where(
                BuyerRequest.order_id == order.id,
                BuyerRequest.decision == "REVIEW_REQUIRED",
                BuyerRequest.resolution.is_(None),
            )
            .limit(1)
        )
        if pending:
            raise OrderAPIError(
                409, "BUYER_REVIEW_REQUIRED", "Resolve pending buyer requests before assignment."
            )
        recalculate(order, self.catalog)
        if order.confidence_level == "RED" or not order.customer_phone or not order.township:
            raise OrderAPIError(
                409, "ORDER_VALIDATION_REQUIRED", "Critical delivery details need review."
            )
        if order.cod_amount is None:
            raise OrderAPIError(
                409,
                "COD_AMOUNT_REQUIRED",
                "Set an explicit COD amount; use zero for prepaid orders.",
            )
        if order.parsing_metadata.get("parcel") and body.route_id is None:
            raise OrderAPIError(
                422, "ROUTE_REQUIRED", "Choose a rider route for workspace parcels."
            )
        count = self.session.scalar(
            select(func.count())
            .select_from(DeliveryAssignment)
            .where(DeliveryAssignment.rider_id == profile.id, DeliveryAssignment.status == "ACTIVE")
        )
        if count >= self.settings.rider_max_active_assignments:
            raise OrderAPIError(
                409, "RIDER_QUEUE_FULL", "Rider has reached the active assignment limit."
            )
        assignment = DeliveryAssignment(
            id=uuid4(),
            order_id=order.id,
            rider_id=profile.id,
            dispatcher_id=self.actor.id,
            stop_sequence=body.stop_sequence,
        )
        self.session.add(assignment)
        previous = order.status
        order.status = OrderStatus.ASSIGNED
        profile.queue_version += 1
        self.event(order, assignment, "RIDER_ASSIGNED", previous)
        if body.route_id is not None:
            from app.services.workflow import attach_order

            attach_order(self.session, self.actor, order, assignment, body.route_id)
        return self.assignment_result(order, assignment)

    def unassign(self, order_id, body):
        self.dispatcher()
        order = self.order(order_id, body.expected_version)
        assignment = active_assignment(self.session, order.id)
        if assignment is None or order.status != OrderStatus.ASSIGNED:
            raise OrderAPIError(
                409,
                "UNASSIGN_NOT_ALLOWED",
                "Only an assigned, not-started delivery can be unassigned.",
            )
        from app.services.workflow import detach_order

        detach_order(self.session, self.actor, order)
        assignment.status, assignment.ended_at = "UNASSIGNED", utcnow()
        previous, order.status = order.status, OrderStatus.READY_FOR_DISPATCH
        bump_queue(self.session, assignment.rider_id)
        self.event(order, assignment, "RIDER_UNASSIGNED", previous)
        return self.assignment_result(order, assignment)

    def sequence(self, order_id, body):
        self.dispatcher()
        order = self.order(order_id, body.expected_version)
        assignment = active_assignment(self.session, order.id)
        if assignment is None or order.status != OrderStatus.ASSIGNED:
            raise OrderAPIError(
                409, "ORDER_NOT_ASSIGNABLE", "Stop order can only change before delivery starts."
            )
        if assignment.stop_sequence != body.stop_sequence:
            assignment.stop_sequence = body.stop_sequence
            order.updated_at = utcnow()
            bump_queue(self.session, assignment.rider_id)
            self.event(order, assignment, "RIDER_SEQUENCE_CHANGED", order.status)
        return self.assignment_result(order, assignment)

    def action(self, rider_id, order_id, body):
        self.rider(rider_id)
        lock_order(self.session, order_id)
        lock_profile(self.session, rider_id)
        payload_hash = hashlib.sha256(
            (
                str(rider_id)
                + str(order_id)
                + json.dumps(body.model_dump(mode="json"), sort_keys=True)
            ).encode()
        ).hexdigest()
        receipt = self.session.scalar(
            select(RiderActionReceipt).where(
                RiderActionReceipt.actor_id == self.actor.id,
                RiderActionReceipt.request_id == body.request_id,
            )
        )
        if receipt:
            if receipt.payload_hash != payload_hash:
                raise OrderAPIError(
                    409,
                    "RIDER_REQUEST_CONFLICT",
                    "Request ID was used for different delivery data.",
                )
            return ActionResult.model_validate(receipt.result)
        assignment = active_assignment(self.session, order_id)
        if assignment is None or assignment.rider_id != rider_id:
            raise OrderAPIError(404, "ASSIGNED_DELIVERY_NOT_FOUND", "Assigned delivery not found.")
        order = self.session.get(Order, order_id)
        self.session.refresh(order)
        OrderManagementService.check_version(order, body.expected_version)
        from app.services.workflow import record_collection, validate_delivery_route

        validate_delivery_route(self.session, self.actor, order, body.action)
        target = (
            OrderStatus.OUT_FOR_DELIVERY if body.action == "START" else OrderStatus(body.action)
        )
        if target not in ALLOWED_TRANSITIONS[order.status]:
            raise OrderAPIError(
                409, "INVALID_STATUS_TRANSITION", "Delivery action is not allowed in this status."
            )
        profile = self.session.get(RiderProfile, rider_id)
        self.session.refresh(profile)
        if body.action == "START" and profile.operational_status != "AVAILABLE":
            raise OrderAPIError(
                409, "RIDER_NOT_AVAILABLE", "Rider must be available to start delivery."
            )
        if body.action == "DELIVERED":
            if order.cod_amount is None:
                raise OrderAPIError(
                    409, "COD_AMOUNT_REQUIRED", "COD amount requires dispatcher review."
                )
            record_collection(order, body, self.actor)
            if (
                order.cod_amount > 0
                and self.settings.rider_require_cod_confirmation
                and body.cod_collected is not True
            ):
                raise OrderAPIError(
                    409,
                    "COD_CONFIRMATION_REQUIRED",
                    "Explicit COD collection confirmation is required.",
                )
            assignment.status, assignment.ended_at = "COMPLETED", utcnow()
            assignment.cod_collected = body.cod_collected
        elif body.action == "FAILED":
            assignment.status, assignment.ended_at = "FAILED", utcnow()
            assignment.failure_reason, assignment.failure_note = (
                body.failure_reason,
                body.failure_note,
            )
        previous, order.status = order.status, target
        profile.queue_version += 1
        self.session.flush()
        delivery_link_policy(self.session, order)
        event_type = {
            "START": "DELIVERY_STARTED",
            "DELIVERED": "DELIVERY_COMPLETED",
            "FAILED": "DELIVERY_FAILED",
        }[body.action]
        self.event(
            order,
            assignment,
            event_type,
            previous,
            {"cod_collected": assignment.cod_collected, "failure_reason": body.failure_reason},
        )
        self.session.flush()
        result = ActionResult(
            request_id=body.request_id,
            assignment_id=assignment.id,
            order_id=order.id,
            rider_id=rider_id,
            status=order.status,
            assignment_status=assignment.status,
            order_version=order.version,
            cod_collected=assignment.cod_collected,
            failure_reason=assignment.failure_reason,
            updated_at=order.updated_at,
        )
        self.session.add(
            RiderActionReceipt(
                actor_id=self.actor.id,
                rider_id=rider_id,
                order_id=order.id,
                assignment_id=assignment.id,
                request_id=body.request_id,
                payload_hash=payload_hash,
                result=result.model_dump(mode="json"),
            )
        )
        self.session.commit()
        return result

    def history(self, order_id, page, page_size):
        self.dispatcher()
        OrderManagementService(self.session, self.actor, self.catalog).get(order_id)
        query = select(DeliveryAssignment).where(DeliveryAssignment.order_id == order_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = self.session.scalars(
            query.order_by(DeliveryAssignment.assigned_at, DeliveryAssignment.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return {
            "items": [AssignmentResponse.model_validate(row) for row in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def queue(self, rider_id, cursor):
        profile, _ = self.rider(rider_id)
        rows = self.session.execute(
            select(DeliveryAssignment, Order)
            .join(Order, DeliveryAssignment.order_id == Order.id)
            .where(
                DeliveryAssignment.rider_id == rider_id,
                DeliveryAssignment.status == "ACTIVE",
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY]),
            )
        )
        rows = list(rows)
        requests = {}
        if rows:
            for request in self.session.scalars(
                select(BuyerRequest)
                .where(BuyerRequest.order_id.in_([order.id for _, order in rows]))
                .order_by(BuyerRequest.created_at, BuyerRequest.id)
            ):
                requests.setdefault(request.order_id, []).append(request)
        items = []
        for assignment, order in rows:
            confirmed_pin = (
                order.latitude is not None
                and order.longitude is not None
                and all(
                    order.field_sources.get(field, {}).get("method") == "buyer_confirmation"
                    and not order.field_sources.get(field, {}).get("requires_review", True)
                    for field in ("latitude", "longitude")
                )
            )
            window_start = None
            if (
                order.delivery_time_window
                and order.field_sources.get("delivery_time_window", {}).get("method")
                == "buyer_confirmation"
            ):
                try:
                    start, end = [
                        datetime.fromisoformat(value)
                        for value in order.delivery_time_window.split("/")
                    ]
                    if start.tzinfo and end.tzinfo and start < end:
                        window_start = start.astimezone(UTC)
                except (ValueError, TypeError):
                    pass  # Freeform parser windows remain visible but do not affect priority.
            confirmation = {
                "location": "CONFIRMED" if confirmed_pin else "NOT_CONFIRMED",
                "availability": "NOT_CONFIRMED",
                "pending_review": False,
                "last_confirmed_at": None,
            }
            for request in requests.get(order.id, []):
                if request.decision == "REVIEW_REQUIRED" and request.resolution is None:
                    confirmation["pending_review"] = True
                if request.decision == "APPLIED" or request.resolution == "APPROVE":
                    confirmation["last_confirmed_at"] = request.resolved_at or request.created_at
                    action = request.submitted_values.get("action")
                    if action in {"AVAILABLE", "RESCHEDULE", "LEAVE_WITH_SECURITY"}:
                        confirmation["availability"] = action
            nav = (
                "https://www.google.com/maps/dir/?"
                + urlencode(
                    {
                        "api": "1",
                        "destination": f"{order.latitude},{order.longitude}",
                        "travelmode": "driving",
                    }
                )
                if confirmed_pin
                else None
            )
            item = QueueDelivery(
                assignment_id=assignment.id,
                order_id=order.id,
                status=order.status,
                order_version=order.version,
                stop_sequence=assignment.stop_sequence,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                township=order.township,
                street=order.street,
                landmark=order.landmark,
                building_floor_unit=order.building_floor_unit,
                delivery_instructions=order.delivery_instructions,
                delivery_time_window=order.delivery_time_window,
                confirmed_window_start=window_start,
                cod_amount=format(order.cod_amount, ".0f")
                if order.cod_amount is not None
                else None,
                latitude=order.latitude,
                longitude=order.longitude,
                coordinate_status="BUYER_CONFIRMED"
                if confirmed_pin
                else "MISSING"
                if order.latitude is None
                else "UNCONFIRMED",
                navigation_ready=confirmed_pin,
                navigation_url=nav,
                confidence_level=order.confidence_level,
                location_verification=order.parsing_metadata.get(
                    "location_verification",
                    {"status": "unverified", "dataset": None, "source_url": None},
                ),
                buyer_confirmation=confirmation,
                updated_at=order.updated_at,
            )
            items.append((item, assignment.assigned_at, order.created_at))
        planned_ids = {
            order.id
            for assignment, order in rows
            if order.parsing_metadata.get("parcel", {}).get("routing", {}).get("assignment_id")
            == str(assignment.id)
        }
        items.sort(
            key=lambda row: (
                0 if row[0].status == OrderStatus.OUT_FOR_DELIVERY else 1,
                0 if row[0].order_id in planned_ids else 1,
                (row[0].stop_sequence or 10001) if row[0].order_id in planned_ids else 0,
                row[0].confirmed_window_start is None,
                row[0].confirmed_window_start or datetime.max.replace(tzinfo=UTC),
                row[0].stop_sequence is None,
                row[0].stop_sequence or 0,
                row[1],
                row[2],
                str(row[0].order_id),
                str(row[0].assignment_id),
            )
        )
        deliveries = [row[0] for row in items]
        serialized = {
            "rider_id": str(rider_id),
            "queue_version": profile.queue_version,
            "operational_status": profile.operational_status,
            "items": [item.model_dump(mode="json") for item in deliveries],
        }
        current = hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()
        return {
            "rider_id": rider_id,
            "operational_status": profile.operational_status,
            "cursor": current,
            "unchanged": current == cursor,
            "total": len(deliveries),
            "items": [] if current == cursor else deliveries,
            "generated_at": utcnow(),
        }
