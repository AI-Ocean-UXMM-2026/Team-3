from copy import deepcopy
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.order_errors import OrderAPIError
from app.db.models import DeliveryEvent, Order, User, utcnow
from app.domain.lifecycle import (
    ALLOWED_TRANSITIONS,
    EDITABLE_STATUSES,
    MERCHANT_TRANSITIONS,
    OrderStatus,
    UserRole,
)
from app.parsing.places import LocationCatalog
from app.parsing.triage import classify
from app.schemas.management import (
    ChangeStatus,
    CorrectOrder,
    CreateOrder,
    EventPage,
    EventResponse,
    OrderPage,
    OrderResponse,
)
from app.schemas.orders import AddressFields, FieldSource, NormalizationInfo, ParseResponse

PARSER_TO_ORDER = {
    "customer_name": "customer_name",
    "phone_number": "customer_phone",
    "township": "township",
    "street": "street",
    "landmark": "landmark",
    "building_floor_unit": "building_floor_unit",
    "cod_amount": "cod_amount",
    "delivery_instructions": "delivery_instructions",
    "time_window": "delivery_time_window",
}
EDITABLE_FIELDS = set(CorrectOrder.model_fields) - {"expected_version"}


def manual_source(actor: User, old: dict | None = None, missing: bool = False) -> dict:
    return {
        "method": "manual_correction",
        "status": "missing" if missing else "extracted",
        "verified": False,
        "requires_review": False,
        "evidence": [],
        "actor_id": str(actor.id),
        "corrected_at": utcnow().isoformat(),
        "original_source": deepcopy(old.get("original_source", old)) if old else None,
    }


def recalculate(order: Order, catalog: LocationCatalog) -> None:
    address = AddressFields(
        **{
            field: (
                int(order.cod_amount)
                if field == "cod_amount" and order.cod_amount is not None
                else getattr(order, stored)
            )
            for field, stored in PARSER_TO_ORDER.items()
        }
    )
    sources = {}
    for field, stored in PARSER_TO_ORDER.items():
        source = deepcopy(order.field_sources.get(stored, {}))
        if source.get("method") in {"manual_correction", "buyer_confirmation"}:
            source["method"] = "rule"
        if field in {"street", "landmark"}:
            source["verified"], source["dataset"] = False, None
        sources[field] = FieldSource.model_validate(source)
    normalization = NormalizationInfo.model_validate(
        order.parsing_metadata.get(
            "normalization",
            {"encoding": "non_myanmar"},
        )
    )
    # Corrected current critical fields can be validated independently of an old
    # message's encoding; original warnings remain in parsing_metadata for review.
    if all(
        order.field_sources.get(f, {}).get("method") == "manual_correction"
        for f in ("customer_phone", "township")
    ):
        for warning in normalization.warnings:
            if warning.code in {"ENCODING_UNCERTAIN", "ZAWGYI_CONVERSION_FAILED"}:
                warning.code = "ORIGINAL_ENCODING_REVIEW"
    confidence, reasons, verification = classify(address, sources, normalization, catalog)
    order.confidence_level = confidence
    order.confidence_reasons = [reason.model_dump() for reason in reasons]
    metadata = deepcopy(order.parsing_metadata)
    metadata["location_verification"] = verification.model_dump(mode="json")
    order.parsing_metadata = metadata
    order.manual_review_required = confidence != "GREEN" or order.ai_availability_status in {
        "timeout",
        "rate_limited",
        "invalid_response",
        "unavailable",
    }
    # Only catalog verification is copied back; manual coordinates never feed triage.
    stored_sources = deepcopy(order.field_sources)
    for field in ("street", "landmark"):
        stored_sources[field]["verified"] = sources[field].verified
        stored_sources[field]["dataset"] = sources[field].dataset
    order.field_sources = stored_sources


class OrderManagementService:
    def __init__(
        self, session: Session, actor: User, catalog: LocationCatalog, require_cod_confirmation=True
    ):
        self.session, self.actor, self.catalog = session, actor, catalog
        self.require_cod_confirmation = require_cod_confirmation

    def scoped(self):
        query = select(Order)
        if self.actor.role == UserRole.MERCHANT:
            query = query.where(Order.merchant_id == self.actor.id)
        return query

    def get(self, order_id) -> Order:
        row = self.session.scalar(self.scoped().where(Order.id == order_id))
        if row is None:
            raise OrderAPIError(404, "ORDER_NOT_FOUND", "Order not found.")
        return row

    def event(self, order: Order, event_type: str, previous, metadata: dict):
        self.session.add(
            DeliveryEvent(
                order_id=order.id,
                event_type=event_type,
                previous_status=previous,
                new_status=order.status,
                event_metadata={"actor_id": str(self.actor.id), **metadata},
            )
        )

    def committed_response(self, order: Order) -> OrderResponse:
        self.session.flush()
        response = OrderResponse.model_validate(order)
        self.session.commit()  # Before returning the successful HTTP response.
        return response

    def create(self, body: CreateOrder, parsed: ParseResponse | None, mode: str) -> OrderResponse:
        if self.actor.role == UserRole.MERCHANT and body.merchant_id != self.actor.id:
            raise OrderAPIError(
                403, "MERCHANT_SCOPE_FORBIDDEN", "Cannot create orders for another merchant."
            )
        merchant = self.session.get(User, body.merchant_id)
        if merchant is None or merchant.role != UserRole.MERCHANT:
            raise OrderAPIError(
                422, "INVALID_MERCHANT", "merchant_id must identify an existing merchant."
            )
        order = Order(
            id=uuid4(),
            merchant_id=merchant.id,
            status=OrderStatus.DRAFT,
            version=1,
            parsing_mode=mode,
            ai_availability_status="not_requested",
            field_sources={
                field: FieldSource().model_dump()
                for field in (*EDITABLE_FIELDS, "building_floor_unit")
            },
            parsing_metadata={"normalization": {"encoding": "non_myanmar"}},
        )
        if parsed is not None:
            order.original_message, order.normalized_message = (
                parsed.original_text,
                parsed.normalized_text,
            )
            for field, stored in PARSER_TO_ORDER.items():
                value = getattr(parsed.address, field)
                limit = getattr(Order.__table__.c[stored].type, "length", None)
                if isinstance(value, str) and limit is not None and len(value) > limit:
                    raise OrderAPIError(
                        422,
                        "ORDER_FIELD_TOO_LONG",
                        f"Parsed {stored} exceeds the order field length limit.",
                    )
                setattr(order, stored, value)
                order.field_sources[stored] = parsed.field_sources[field].model_dump(mode="json")
            order.ai_availability_status = parsed.ai.status
            order.confidence_level, order.manual_review_required = (
                parsed.confidence,
                parsed.manual_review_required,
            )
            order.confidence_reasons = [r.model_dump() for r in parsed.validation_reasons]
            order.parsing_metadata = {
                "normalization": parsed.normalization.model_dump(mode="json"),
                "ai": parsed.ai.model_dump(mode="json"),
                "location_verification": parsed.location_verification.model_dump(mode="json"),
            }
        else:
            for field in body.structured.model_fields_set:
                value = getattr(body.structured, field)
                setattr(order, field, value)
                order.field_sources[field] = manual_source(self.actor, missing=value is None)
            self.combine_parts(order)
            recalculate(order, self.catalog)
        self.session.add(order)
        self.session.flush()
        self.event(order, "ORDER_CREATED", None, {"parsing_mode": mode})
        return self.committed_response(order)

    def combine_parts(self, order: Order):
        value = "; ".join(
            f"{f}: {getattr(order, f)}"
            for f in ("building", "floor", "unit")
            if getattr(order, f) is not None
        )
        order.building_floor_unit = value or None
        sources = deepcopy(order.field_sources)
        sources["building_floor_unit"] = manual_source(
            self.actor,
            sources.get("building_floor_unit"),
            missing=not value,
        )
        order.field_sources = sources

    def correct(self, order_id, body: CorrectOrder) -> OrderResponse:
        order = self.get(order_id)
        self.check_version(order, body.expected_version)
        if order.status not in EDITABLE_STATUSES:
            raise OrderAPIError(
                409, "ORDER_NOT_EDITABLE", "Order cannot be corrected in its current status."
            )
        changed = sorted(
            field
            for field in body.model_fields_set - {"expected_version"}
            if (
                getattr(order, field) != getattr(body, field)
                or order.field_sources.get(field, {}).get("method") == "ai"
                or order.field_sources.get(field, {}).get("requires_review")
                or order.field_sources.get(field, {}).get("status") in {"ambiguous", "invalid"}
            )
        )
        if not changed:
            return OrderResponse.model_validate(order)
        sources = deepcopy(order.field_sources)
        for field in changed:
            value = getattr(body, field)
            setattr(order, field, value)
            sources[field] = manual_source(self.actor, sources.get(field), missing=value is None)
        order.field_sources = sources
        if set(changed) & {"building", "floor", "unit"}:
            self.combine_parts(order)
        recalculate(order, self.catalog)
        previous = order.status
        if order.status != OrderStatus.DRAFT:
            order.status = OrderStatus.NEEDS_REVIEW
        self.event(order, "ORDER_CORRECTED", previous, {"changed_fields": changed})
        if "customer_phone" in changed:
            self.session.flush()
            from app.services.buyer_confirmation import revoke_phone_links

            revoke_phone_links(self.session, order)
        return self.committed_response(order)

    @staticmethod
    def check_version(order: Order, expected: int):
        if order.version != expected:
            raise OrderAPIError(
                409,
                "VERSION_CONFLICT",
                "Order changed; retrieve the latest version before updating.",
            )

    def change_status(self, order_id, body: ChangeStatus) -> OrderResponse:
        order = self.get(order_id)
        self.check_version(order, body.expected_version)
        if body.status not in ALLOWED_TRANSITIONS[order.status]:
            raise OrderAPIError(
                409, "INVALID_STATUS_TRANSITION", "Requested status transition is not allowed."
            )
        if self.actor.role == UserRole.MERCHANT and body.status not in MERCHANT_TRANSITIONS:
            raise OrderAPIError(
                403, "ROLE_FORBIDDEN", "This status change requires a dispatcher or admin."
            )
        from app.services.riders import dispatcher_status_guard

        dispatcher_status_guard(self.session, order, body.status)
        if body.status == OrderStatus.DELIVERED:
            if order.cod_amount is None:
                raise OrderAPIError(
                    409, "COD_AMOUNT_REQUIRED", "COD amount requires dispatcher review."
                )
            if (
                order.cod_amount > 0
                and self.require_cod_confirmation
                and body.cod_collected is not True
            ):
                raise OrderAPIError(
                    409,
                    "COD_CONFIRMATION_REQUIRED",
                    "Explicit COD collection confirmation is required.",
                )
        if body.status in {OrderStatus.CONFIRMED, OrderStatus.READY_FOR_DISPATCH}:
            from app.db.buyer_models import BuyerRequest

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
                    409,
                    "BUYER_REVIEW_REQUIRED",
                    "Resolve pending buyer requests before confirming dispatch.",
                )
            recalculate(order, self.catalog)
        if body.status in {OrderStatus.CONFIRMED, OrderStatus.READY_FOR_DISPATCH}:
            if order.confidence_level == "RED" or not order.customer_phone or not order.township:
                raise OrderAPIError(
                    409,
                    "ORDER_VALIDATION_REQUIRED",
                    "Resolve critical contact/address validation failures first.",
                )
        if (
            body.status == OrderStatus.READY_FOR_DISPATCH
            and order.confidence_level != "GREEN"
            and not body.acknowledge_unverified_location
        ):
            raise OrderAPIError(
                409,
                "LOCATION_ACKNOWLEDGEMENT_REQUIRED",
                "Dispatcher must explicitly acknowledge the unverified location.",
            )
        previous = order.status
        order.status = body.status
        if body.status == OrderStatus.DELIVERED:
            metadata = deepcopy(order.parsing_metadata)
            metadata["delivery_completion"] = {
                "cod_collected": body.cod_collected,
                "actor_id": str(self.actor.id),
                "confirmed_at": utcnow().isoformat(),
            }
            order.parsing_metadata = metadata
        self.session.flush()
        from app.services.buyer_confirmation import delivery_link_policy

        delivery_link_policy(self.session, order)
        from app.services.riders import dispatcher_status_sync

        dispatcher_status_sync(self.session, order, self.actor, previous)
        self.event(
            order,
            "STATUS_CHANGED",
            previous,
            {
                "cod_collected": body.cod_collected,
                "unverified_location_acknowledged": body.status == OrderStatus.READY_FOR_DISPATCH
                and order.confidence_level != "GREEN"
                and body.acknowledge_unverified_location,
            },
        )
        return self.committed_response(order)

    def list(self, page: int, page_size: int, status=None, confidence=None, q=None) -> OrderPage:
        query = self.scoped()
        if status is not None:
            query = query.where(Order.status == status)
        if confidence is not None:
            query = query.where(Order.confidence_level == confidence)
        if q is not None:
            query = query.where(
                or_(
                    *[
                        field.icontains(q, autoescape=True)
                        for field in (
                            Order.customer_name,
                            Order.customer_phone,
                            Order.township,
                            Order.street,
                            Order.landmark,
                        )
                    ]
                )
            )
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.session.scalars(
            query.order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return OrderPage(
            items=[OrderResponse.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def events(self, order_id, page: int, page_size: int) -> EventPage:
        self.get(order_id)  # Same not-found response for absent and out-of-scope orders.
        query = select(DeliveryEvent).where(DeliveryEvent.order_id == order_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.session.scalars(
            query.order_by(DeliveryEvent.created_at, DeliveryEvent.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return EventPage(
            items=[EventResponse.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
