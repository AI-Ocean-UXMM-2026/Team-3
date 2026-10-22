import hashlib
import hmac
import json
import re
import secrets
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerOtpChallenge, BuyerRequest, BuyerSession, ConfirmationLink, LocationReference
from app.db.models import DeliveryEvent, Order, utcnow
from app.domain.lifecycle import OrderStatus, UserRole
from app.services.buyer_policy import distance_meters
from app.services.order_management import OrderManagementService, recalculate

PRE_DISPATCH = {OrderStatus.NEEDS_REVIEW, OrderStatus.AWAITING_CONFIRMATION, OrderStatus.CONFIRMED}
YANGON = timezone(timedelta(hours=6, minutes=30))


def sync_parcel_schedule(order, changes):
    """Keep the new route delivery day aligned with an applied buyer window."""
    window = changes.get("delivery_time_window")
    if order.parsing_metadata.get("parcel") and window and "/" in window:
        start = datetime.fromisoformat(window.split("/", 1)[0])
        metadata = deepcopy(order.parsing_metadata)
        metadata["parcel"]["delivery_day"] = start.astimezone(YANGON).date().isoformat()
        order.parsing_metadata = metadata


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def phone_binding(link_hash, phone):
    return hmac.new(link_hash.encode(), (phone or "").encode(), hashlib.sha256).hexdigest()


def lock_order(session, order_id):
    # An UPDATE, even to the same value, acquires a write lock on both SQLite and PG.
    # Every buyer mutation locks order THEN link: counters and order status stay serialized.
    session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(version=Order.version, updated_at=Order.updated_at)
    )


def delivery_link_policy(session, order):
    """Called inside the dispatcher status transaction after the order row is flushed."""
    if order.status == OrderStatus.DELIVERED:
        until = utcnow() + timedelta(hours=24)
        active_link_ids = select(ConfirmationLink.id).where(
            ConfirmationLink.order_id == order.id,
            ConfirmationLink.revoked_at.is_(None),
            ConfirmationLink.locked_at.is_(None),
            ConfirmationLink.expires_at > utcnow(),
        )
        session.execute(
            update(BuyerOtpChallenge)
            .where(BuyerOtpChallenge.link_id.in_(active_link_ids), BuyerOtpChallenge.status == "PENDING")
            .values(status="REVOKED", demo_code=None)
        )
        session.execute(
            update(ConfirmationLink)
            .where(
                ConfirmationLink.order_id == order.id,
                ConfirmationLink.revoked_at.is_(None),
                ConfirmationLink.locked_at.is_(None),
                ConfirmationLink.expires_at > utcnow(),
            )
            .values(delivered_view_until=until, generation=ConfirmationLink.generation + 1)
        )
    elif order.status == OrderStatus.CANCELLED:
        active_link_ids = select(ConfirmationLink.id).where(
            ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None)
        )
        session.execute(
            update(BuyerOtpChallenge)
            .where(BuyerOtpChallenge.link_id.in_(active_link_ids), BuyerOtpChallenge.status == "PENDING")
            .values(status="REVOKED", demo_code=None)
        )
        session.execute(
            update(ConfirmationLink)
            .where(ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None))
            .values(revoked_at=utcnow(), generation=ConfirmationLink.generation + 1)
        )


def revoke_phone_links(session, order):
    link_ids = select(ConfirmationLink.id).where(
        ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None)
    )
    session.execute(
        update(BuyerOtpChallenge)
        .where(BuyerOtpChallenge.link_id.in_(link_ids), BuyerOtpChallenge.status == "PENDING")
        .values(status="REVOKED", demo_code=None)
    )
    session.execute(
        update(ConfirmationLink)
        .where(ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None))
        .values(revoked_at=utcnow(), generation=ConfirmationLink.generation + 1)
    )


class BuyerConfirmationService:
    def __init__(self, session, settings, catalog, boundaries):
        self.session, self.settings, self.catalog, self.boundaries = (
            session,
            settings,
            catalog,
            boundaries,
        )

    def event(self, order, kind, metadata, previous=None):
        self.session.add(
            DeliveryEvent(
                order_id=order.id,
                event_type=kind,
                previous_status=previous or order.status,
                new_status=order.status,
                event_metadata=metadata,
            )
        )

    def management_order(self, order_id, actor):
        order = OrderManagementService(self.session, actor, self.catalog).get(order_id)
        lock_order(self.session, order.id)
        self.session.refresh(order)
        return order

    def generate(self, order_id, actor):
        from app.schemas.management import EditableOrderFields

        order = self.management_order(order_id, actor)
        try:
            valid_phone = EditableOrderFields.valid_mobile(order.customer_phone)
        except ValueError:
            valid_phone = None
        if order.status not in PRE_DISPATCH or not valid_phone:
            raise OrderAPIError(
                409,
                "CONFIRMATION_NOT_ELIGIBLE",
                "Order needs a valid phone and pre-dispatch review status.",
            )
        now = utcnow()
        old_link_ids = select(ConfirmationLink.id).where(
            ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None)
        )
        self.session.execute(
            update(BuyerOtpChallenge)
            .where(BuyerOtpChallenge.link_id.in_(old_link_ids), BuyerOtpChallenge.status == "PENDING")
            .values(status="REVOKED", demo_code=None)
        )
        self.session.execute(
            update(ConfirmationLink)
            .where(ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None))
            .values(revoked_at=now, generation=ConfirmationLink.generation + 1)
        )
        token = secrets.token_urlsafe(32)
        token_hash = digest(token)
        link = ConfirmationLink(
            order_id=order.id,
            token_hash=token_hash,
            phone_binding=phone_binding(token_hash, order.customer_phone),
            expires_at=now + timedelta(hours=self.settings.buyer_link_hours),
        )
        self.session.add(link)
        self.session.flush()
        self.event(
            order, "BUYER_LINK_CREATED", {"link_id": str(link.id), "actor_id": str(actor.id)}
        )
        self.session.commit()
        relative = f"/confirm/{token}"
        return {
            "link_id": link.id,
            "confirmation_url": relative,
            "absolute_url": self.settings.buyer_frontend_base_url + relative
            if self.settings.buyer_frontend_base_url
            else None,
            "expires_at": link.expires_at,
        }

    def revoke(self, order_id, actor):
        order = self.management_order(order_id, actor)
        active_link_ids = select(ConfirmationLink.id).where(
            ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None)
        )
        self.session.execute(
            update(BuyerOtpChallenge)
            .where(BuyerOtpChallenge.link_id.in_(active_link_ids), BuyerOtpChallenge.status == "PENDING")
            .values(status="REVOKED", demo_code=None)
        )
        result = self.session.execute(
            update(ConfirmationLink)
            .where(ConfirmationLink.order_id == order.id, ConfirmationLink.revoked_at.is_(None))
            .values(revoked_at=utcnow(), generation=ConfirmationLink.generation + 1)
        )
        if result.rowcount:
            self.event(order, "BUYER_LINK_REVOKED", {"actor_id": str(actor.id)})
        self.session.commit()
        return {"revoked": True}

    def link(self, token, mutate=False):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise OrderAPIError(
                404, "CONFIRMATION_UNAVAILABLE", "Confirmation link is unavailable."
            )
        token_hash = digest(token)
        if mutate:
            order_id = (
                select(ConfirmationLink.order_id)
                .where(ConfirmationLink.token_hash == token_hash)
                .scalar_subquery()
            )
            self.session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(version=Order.version, updated_at=Order.updated_at)
            )
            self.session.execute(
                update(ConfirmationLink)
                .where(ConfirmationLink.token_hash == token_hash)
                .values(nonce=ConfirmationLink.nonce + 1)
            )
        link = self.session.scalar(
            select(ConfirmationLink).where(ConfirmationLink.token_hash == token_hash)
        )
        if link is None:
            raise OrderAPIError(
                404, "CONFIRMATION_UNAVAILABLE", "Confirmation link is unavailable."
            )
        order = self.session.get(Order, link.order_id)
        if (
            link.revoked_at
            or order.status == OrderStatus.CANCELLED
            or not hmac.compare_digest(
                link.phone_binding, phone_binding(link.token_hash, order.customer_phone)
            )
        ):
            raise OrderAPIError(
                404, "CONFIRMATION_UNAVAILABLE", "Confirmation link is unavailable."
            )
        expires = (
            link.delivered_view_until if order.status == OrderStatus.DELIVERED else link.expires_at
        )
        if expires is None or expires <= utcnow():
            raise OrderAPIError(410, "CONFIRMATION_EXPIRED", "Confirmation link has expired.")
        return link, order, expires

    def card(self, token):
        link, order, expires = self.link(token)
        # No registered user name is claimed to be trustworthy merchant branding.
        return {
            "order_reference": str(order.id),
            "shop_display_name": None,
            "delivery_status": order.status,
            "state": "LOCKED"
            if link.locked_at
            else "VIEW_ONLY"
            if order.status == OrderStatus.DELIVERED
            else "VERIFICATION_REQUIRED",
            "expires_at": expires,
        }

    def mutable(self, link, order):
        if link.locked_at or link.failed_attempts >= 3:
            raise OrderAPIError(
                423, "CONFIRMATION_LOCKED", "Confirmation is locked; contact the shop."
            )
        if order.status not in PRE_DISPATCH:
            raise OrderAPIError(
                409, "BUYER_CHANGES_CLOSED", "Delivery details cannot be changed at this stage."
            )

    def verify(self, token, body):
        from app.services.buyer_otp import BuyerOtpService

        return BuyerOtpService(self.session, self.settings).verify(token, body.code)

    def authorize(self, token, credential):
        link, order, _ = self.link(token, mutate=True)
        self.mutable(link, order)
        if not credential or not re.fullmatch(r"[A-Za-z0-9_-]{43}", credential):
            raise OrderAPIError(
                401, "BUYER_AUTHORIZATION_REQUIRED", "Valid buyer authorization is required."
            )
        auth = self.session.scalar(
            select(BuyerSession).where(BuyerSession.token_hash == digest(credential))
        )
        if (
            auth is None
            or auth.link_id != link.id
            or auth.generation != link.generation
            or auth.expires_at <= utcnow()
        ):
            raise OrderAPIError(
                401, "BUYER_AUTHORIZATION_REQUIRED", "Valid buyer authorization is required."
            )
        return link, order

    def details(self, token, credential):
        link, order = self.authorize(token, credential)
        result = {
            field: getattr(order, field)
            for field in (
                "township",
                "street",
                "landmark",
                "building_floor_unit",
                "latitude",
                "longitude",
                "delivery_time_window",
                "delivery_instructions",
            )
        }
        result.update(
            {
                "order_reference": str(order.id),
                "status": order.status,
                "initial_pin_requires_review": self.session.get(LocationReference, order.id)
                is None,
                "policy": {
                    "automatic_adjustment_meters": 500,
                    "rescheduling_enabled": self.settings.buyer_rescheduling_enabled,
                    "leave_with_security_enabled": self.settings.buyer_leave_with_security_enabled,
                    "cutoff_hour_yangon": self.settings.buyer_cutoff_hour,
                    "timezone": "Asia/Yangon",
                    "min_notice_minutes": self.settings.buyer_min_notice_minutes,
                    "max_schedule_days": self.settings.buyer_max_schedule_days,
                    "cross_township_fee_mmk": self.settings.buyer_cross_township_fee_mmk,
                },
            }
        )
        self.session.commit()
        return result

    def previous_retry(self, link, body, kind):
        payload_hash = digest(kind + json.dumps(body.model_dump(mode="json"), sort_keys=True))
        previous = self.session.scalar(
            select(BuyerRequest).where(
                BuyerRequest.link_id == link.id, BuyerRequest.request_id == body.request_id
            )
        )
        if previous and previous.payload_hash != payload_hash:
            raise OrderAPIError(
                409, "BUYER_REQUEST_CONFLICT", "Request ID was already used for different data."
            )
        return payload_hash, previous

    def result(self, row, order):
        return {
            "request_id": row.request_id,
            "decision": row.decision,
            "reason_codes": row.reason_codes,
            "order_status": order.status,
            "confidence_level": order.confidence_level,
            "submitted_at": row.created_at,
            "confirmed_at": row.created_at
            if row.decision == "APPLIED"
            else row.resolved_at
            if row.resolution == "APPROVE"
            else None,
            "resolution": row.resolution,
        }

    def record(self, link, order, body, kind, payload_hash, reasons, changes):
        previous_status = order.status
        decision = "REVIEW_REQUIRED" if reasons else "APPLIED"
        previous = {
            field: str(getattr(order, field)) if getattr(order, field) is not None else None
            for field in changes
        }
        row = BuyerRequest(
            order_id=order.id,
            link_id=link.id,
            request_id=body.request_id,
            payload_hash=payload_hash,
            kind=kind,
            decision=decision,
            reason_codes=reasons,
            previous_values=previous,
            submitted_values=body.model_dump(mode="json"),
        )
        self.session.add(row)
        if decision == "APPLIED":
            sources = deepcopy(order.field_sources)
            for field, value in changes.items():
                setattr(order, field, value)
                sources[field] = {
                    "method": "buyer_confirmation",
                    "status": "missing" if value is None else "extracted",
                    "verified": False,
                    "requires_review": False,
                    "evidence": [],
                    "link_id": str(link.id),
                    "confirmed_at": utcnow().isoformat(),
                    "original_source": deepcopy(
                        sources.get(field, {}).get("original_source", sources.get(field))
                    ),
                }
            order.field_sources = sources
            recalculate(order, self.catalog)
            sync_parcel_schedule(order, changes)
        # Requests never silently become a confirmed dispatch plan.
        if reasons:
            order.status = OrderStatus.NEEDS_REVIEW
            order.manual_review_required = True
        elif kind == "RESPONSE" and body.action == "AVAILABLE" and order.confidence_level != "RED":
            order.status = OrderStatus.CONFIRMED
        metadata = deepcopy(order.parsing_metadata)
        metadata["buyer_confirmation"] = {
            "request_id": str(body.request_id),
            "decision": decision,
            "kind": kind,
        }
        order.parsing_metadata = metadata
        order.updated_at = utcnow()
        self.event(
            order,
            "BUYER_LOCATION" if kind == "LOCATION" else "BUYER_RESPONSE",
            {
                "link_id": str(link.id),
                "request_id": str(body.request_id),
                "decision": decision,
                "reason_codes": reasons,
            },
            previous_status,
        )
        self.session.flush()
        result = self.result(row, order)
        self.session.commit()
        return result

    def location(self, token, credential, body):
        link, order = self.authorize(token, credential)
        payload_hash, previous = self.previous_retry(link, body, "LOCATION")
        if previous:
            return self.result(previous, order)
        reference = self.session.get(LocationReference, order.id)
        reasons = []
        if reference is None:
            if not body.initial_pin_acknowledged:
                raise OrderAPIError(
                    409,
                    "INITIAL_PIN_ACKNOWLEDGEMENT_REQUIRED",
                    "Initial pin submission requires acknowledgement of dispatcher review.",
                )
            reasons.append("INITIAL_PIN_REQUIRES_REVIEW")
        else:
            target = self.boundaries.township_at(body.latitude, body.longitude)
            origin = self.boundaries.township_at(reference.latitude, reference.longitude)
            if (
                origin != reference.township
                or reference.township != order.township
                or target is None
            ):
                reasons.append("TOWNSHIP_BOUNDARY_UNVERIFIED")
            elif target != reference.township:
                reasons.append("CROSS_TOWNSHIP_APPROVAL_REQUIRED")
            elif (
                distance_meters(
                    reference.latitude, reference.longitude, body.latitude, body.longitude
                )
                > 500
            ):
                reasons.append("ZONE_2_RESCHEDULE_REVIEW_REQUIRED")
        return self.record(
            link,
            order,
            body,
            "LOCATION",
            payload_hash,
            reasons,
            {"latitude": body.latitude, "longitude": body.longitude},
        )

    def response(self, token, credential, body):
        link, order = self.authorize(token, credential)
        payload_hash, previous = self.previous_retry(link, body, "RESPONSE")
        if previous:
            return self.result(previous, order)
        reasons, changes = [], {}
        now = utcnow()
        if body.time_window:
            start, end = (
                body.time_window.start.astimezone(UTC),
                body.time_window.end.astimezone(UTC),
            )
            if start < now + timedelta(
                minutes=self.settings.buyer_min_notice_minutes
            ) or end > now + timedelta(days=self.settings.buyer_max_schedule_days):
                raise OrderAPIError(
                    422,
                    "INVALID_DELIVERY_WINDOW",
                    "Time window must satisfy notice and scheduling limits.",
                )
            if start.astimezone(YANGON).date() != end.astimezone(YANGON).date():
                raise OrderAPIError(
                    422,
                    "INVALID_DELIVERY_WINDOW",
                    "Time window must fit within one Yangon calendar day.",
                )
            changes["delivery_time_window"] = f"{start.isoformat()}/{end.isoformat()}"
            if not self.settings.buyer_rescheduling_enabled:
                reasons.append("COURIER_RESCHEDULING_REVIEW_REQUIRED")
            if now.astimezone(YANGON).hour >= self.settings.buyer_cutoff_hour:
                reasons.append("COURIER_CUTOFF_REVIEW_REQUIRED")
        if (
            body.action == "LEAVE_WITH_SECURITY"
            and not self.settings.buyer_leave_with_security_enabled
        ):
            reasons.append("LEAVE_WITH_SECURITY_REVIEW_REQUIRED")
        if body.instructions:
            changes["delivery_instructions"] = body.instructions
        # No action can resolve a pending location change simply by choosing availability.
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
            reasons.append("PENDING_BUYER_REVIEW")
        if body.action == "AVAILABLE" and order.confidence_level == "RED":
            reasons.append("ORDER_VALIDATION_REVIEW_REQUIRED")
        return self.record(link, order, body, "RESPONSE", payload_hash, reasons, changes)

    def set_reference(self, order_id, actor, body):
        order = self.management_order(order_id, actor)
        if actor.role not in {UserRole.DISPATCHER, UserRole.ADMIN}:
            raise OrderAPIError(
                403, "ROLE_FORBIDDEN", "A dispatcher must attest reference locations."
            )
        if order.status not in PRE_DISPATCH or body.township != order.township:
            raise OrderAPIError(
                409,
                "REFERENCE_NOT_ELIGIBLE",
                "Reference needs a matching pre-dispatch order township.",
            )
        reference = self.session.get(LocationReference, order.id)
        if reference is not None:
            raise OrderAPIError(
                409,
                "REFERENCE_ALREADY_SET",
                "Reference anchors are immutable; dispatcher review is required.",
            )
        self.session.add(
            LocationReference(
                order_id=order.id,
                latitude=body.latitude,
                longitude=body.longitude,
                township=body.township,
                source_reference=body.source_reference,
                actor_id=actor.id,
            )
        )
        self.event(
            order,
            "LOCATION_REFERENCE",
            {"actor_id": str(actor.id), "attestation_id": str(body.request_id)},
        )
        self.session.commit()
        return {
            "reference_set": True,
            "independent_township_boundaries_available": self.boundaries.township_at(
                body.latitude, body.longitude
            )
            == body.township,
        }

    def review(self, order_id, request_id, actor, body):
        from app.schemas.buyer import BuyerLocation, BuyerResponse

        order = self.management_order(order_id, actor)
        if actor.role not in {UserRole.DISPATCHER, UserRole.ADMIN}:
            raise OrderAPIError(403, "ROLE_FORBIDDEN", "Dispatcher approval is required.")
        row = self.session.scalar(
            select(BuyerRequest).where(
                BuyerRequest.order_id == order.id, BuyerRequest.id == request_id
            )
        )
        if row is None:
            raise OrderAPIError(404, "BUYER_REQUEST_NOT_FOUND", "Buyer request not found.")
        if row.resolution is not None:
            if row.resolution == body.decision and row.resolution_reason == body.reason:
                return {
                    "request_id": row.request_id,
                    "resolution": row.resolution,
                    "order_version": order.version,
                }
            raise OrderAPIError(
                409, "BUYER_REQUEST_ALREADY_REVIEWED", "Buyer request was already reviewed."
            )
        OrderManagementService.check_version(order, body.expected_version)
        if order.status not in PRE_DISPATCH or row.decision != "REVIEW_REQUIRED":
            raise OrderAPIError(
                409,
                "BUYER_REVIEW_NOT_ELIGIBLE",
                "Only pending pre-dispatch requests can be reviewed.",
            )
        changes = {}
        if body.decision == "APPROVE":
            if row.kind == "LOCATION":
                value = BuyerLocation.model_validate(row.submitted_values)
                changes = {"latitude": value.latitude, "longitude": value.longitude}
                target = self.boundaries.township_at(value.latitude, value.longitude)
                if target is not None:
                    from app.schemas.management import EditableOrderFields

                    changes["township"] = EditableOrderFields.known_township(target)
            else:
                value = BuyerResponse.model_validate(row.submitted_values)
                if value.time_window:
                    if value.time_window.start <= utcnow():
                        raise OrderAPIError(
                            409, "BUYER_REVIEW_WINDOW_PASSED", "Requested time window has passed."
                        )
                    changes["delivery_time_window"] = (
                        f"{value.time_window.start.astimezone(UTC).isoformat()}/{value.time_window.end.astimezone(UTC).isoformat()}"
                    )
                if value.instructions:
                    changes["delivery_instructions"] = value.instructions
            snapshots = deepcopy(row.previous_values)
            snapshots["at_resolution"] = {
                key: str(getattr(order, key)) if getattr(order, key) is not None else None
                for key in changes
            }
            row.previous_values = snapshots
            sources = deepcopy(order.field_sources)
            for field, value in changes.items():
                setattr(order, field, value)
                sources[field] = {
                    "method": "buyer_confirmation",
                    "status": "extracted",
                    "verified": False,
                    "requires_review": False,
                    "evidence": [],
                    "link_id": str(row.link_id),
                    "confirmed_at": utcnow().isoformat(),
                    "approved_by": str(actor.id),
                    "original_source": deepcopy(
                        sources.get(field, {}).get("original_source", sources.get(field))
                    ),
                }
            order.field_sources = sources
            recalculate(order, self.catalog)
            sync_parcel_schedule(order, changes)
        row.resolution, row.resolution_reason = body.decision, body.reason
        row.resolved_at, row.resolved_by = utcnow(), actor.id
        previous = order.status
        order.status = OrderStatus.NEEDS_REVIEW
        order.updated_at = utcnow()
        self.event(
            order,
            "BUYER_REQUEST_REVIEWED",
            {
                "actor_id": str(actor.id),
                "request_id": str(row.request_id),
                "decision": body.decision,
            },
            previous,
        )
        self.session.flush()
        result = {
            "request_id": row.request_id,
            "resolution": row.resolution,
            "order_version": order.version,
        }
        self.session.commit()
        return result

    def history(self, order_id, actor, page, page_size):
        OrderManagementService(self.session, actor, self.catalog).get(order_id)
        from sqlalchemy import func

        query = select(BuyerRequest).where(BuyerRequest.order_id == order_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.session.scalars(
            query.order_by(BuyerRequest.created_at, BuyerRequest.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "request_id": row.request_id,
                    "kind": row.kind,
                    "decision": row.decision,
                    "reason_codes": row.reason_codes,
                    "previous_values": row.previous_values,
                    "submitted_values": row.submitted_values,
                    "resolution": row.resolution,
                    "resolution_reason": row.resolution_reason,
                    "resolved_by": row.resolved_by,
                    "resolved_at": row.resolved_at,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
