import hashlib
import hmac
import json
import re
import secrets
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import (
    BuyerEditPolicy, BuyerOtpChallenge, BuyerRequest, BuyerSession,
    BuyerSubmissionReceipt, ConfirmationLink, LocationReference,
)
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
        if order.status not in PRE_DISPATCH | {OrderStatus.DRAFT} or not valid_phone:
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
            "buyer_handle": token,
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

    def lookup(self, tracking_id: str, phone: str):
        raw_digits = re.sub(r"[၀-၉]", lambda m: str(ord(m.group(0)) - 0x1040), phone or "")
        clean_phone = re.sub(r"\D", "", raw_digits)
        if clean_phone.startswith("9509"):
            clean_phone = "09" + clean_phone[4:]
        elif clean_phone.startswith("959"):
            clean_phone = "09" + clean_phone[3:]
        elif clean_phone.startswith("9") and len(clean_phone) >= 9:
            clean_phone = "0" + clean_phone

        if len(clean_phone) < 7:
            raise OrderAPIError(
                404,
                "ORDER_NOT_FOUND",
                "No delivery found matching this Tracking ID and phone number. Check your details.",
            )

        tid = (tracking_id or "").strip()
        core_id = tid[3:].strip() if tid.upper().startswith("LP-") else tid

        orders = self.session.scalars(select(Order)).all()
        matched_order = None
        for o in orders:
            str_id = str(o.id).replace("-", "").lower()
            norm_core = core_id.replace("-", "").lower()
            id_match = (
                str(o.id).lower().startswith(core_id.lower())
                or str_id.startswith(norm_core)
                or (len(norm_core) >= 4 and norm_core in str_id)
            )
            parcel_ref = ""
            if o.parsing_metadata and isinstance(o.parsing_metadata, dict):
                parcel_ref = str(o.parsing_metadata.get("parcel", {}).get("reference") or "")
            ref_match = bool(
                parcel_ref and (parcel_ref.lower() == tid.lower() or parcel_ref.lower() == core_id.lower())
            )

            if id_match or ref_match:
                o_digits = re.sub(r"[၀-၉]", lambda m: str(ord(m.group(0)) - 0x1040), o.customer_phone or "")
                o_phone = re.sub(r"\D", "", o_digits)
                if o_phone.startswith("9509"):
                    o_phone = "09" + o_phone[4:]
                elif o_phone.startswith("959"):
                    o_phone = "09" + o_phone[3:]
                elif o_phone.startswith("9") and len(o_phone) >= 9:
                    o_phone = "0" + o_phone

                if clean_phone == o_phone or (
                    len(clean_phone) >= 7 and len(o_phone) >= 7 and clean_phone[-7:] == o_phone[-7:]
                ):
                    matched_order = o
                    break

        if matched_order is None:
            raise OrderAPIError(
                404,
                "ORDER_NOT_FOUND",
                "No delivery found matching this Tracking ID and phone number. Check your order reference and phone number.",
            )

        if matched_order.status == OrderStatus.CANCELLED:
            raise OrderAPIError(410, "DELIVERY_CANCELLED", "This delivery was cancelled. Contact the shop.")

        now = utcnow()
        # Only hashes are stored, so an existing link's raw token cannot be
        # recovered. Issue a separate portal link without invalidating shared links.
        token = secrets.token_urlsafe(32)
        token_hash = digest(token)
        link = ConfirmationLink(
            order_id=matched_order.id,
            token_hash=token_hash,
            phone_binding=phone_binding(token_hash, matched_order.customer_phone),
            expires_at=now + timedelta(hours=self.settings.buyer_link_hours),
            verified_at=now,
        )
        self.session.add(link)
        self.session.flush()

        credential = secrets.token_urlsafe(32)
        expires = min(link.expires_at, now + timedelta(minutes=self.settings.buyer_session_minutes))
        self.session.add(
            BuyerSession(
                link_id=link.id,
                token_hash=digest(credential),
                generation=link.generation,
                expires_at=expires,
            )
        )
        self.event(
            matched_order,
            "BUYER_SECURITY",
            {"link_id": str(link.id), "action": "VERIFIED_PORTAL_LOOKUP"},
        )
        self.session.commit()

        shop_name = None
        if matched_order.parsing_metadata and isinstance(matched_order.parsing_metadata, dict):
            shop_name = matched_order.parsing_metadata.get("parcel", {}).get("sender")

        return {
            "token": token,
            "order_reference": matched_order.id,
            "shop_display_name": shop_name,
            "delivery_status": matched_order.status,
            "access_token": credential,
            "token_type": "Bearer",
            "expires_at": expires,
        }

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
        mutable_statuses = PRE_DISPATCH | {
            OrderStatus.DRAFT, OrderStatus.READY_FOR_DISPATCH,
            OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY,
        }
        if order.status not in mutable_statuses:
            raise OrderAPIError(
                409, "BUYER_CHANGES_CLOSED", "Delivery details cannot be changed at this stage."
            )
        policy = self.session.get(BuyerEditPolicy, order.id)
        if order.status in {
            OrderStatus.READY_FOR_DISPATCH, OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY
        } and (
            policy is None or policy.initial_submitted_at is None or policy.cutoff_at is None
        ):
            raise OrderAPIError(409, "CONCRETE_WINDOW_REQUIRED", "A confirmed delivery window is required before assigned-order edits.")
        # The cutoff limits amendments, never the buyer's first address confirmation.
        if policy is not None and policy.initial_submitted_at is not None:
            now = utcnow()
            if policy.closed_at is not None or policy.edit_count >= 3:
                raise OrderAPIError(409, "BUYER_EDITS_EXHAUSTED", "The three allowed edits have been used.")
            if policy.cutoff_at is not None and now >= policy.cutoff_at:
                policy.closed_at = now
                raise OrderAPIError(409, "BUYER_EDIT_CUTOFF_PASSED", "The delivery change cutoff has passed.")

    def verify(self, token, body):
        from app.services.buyer_otp import BuyerOtpService

        return BuyerOtpService(self.session, self.settings).verify(token, body.code)

    def authorize(self, token, credential):
        # A concurrent assignment can change status; never choose lock order
        # from an unlocked status snapshot.
        from app.services.automatic_assignment import lock_allocator

        lock_allocator(self.session)
        link, order, _ = self.link(token, mutate=True)
        if link.locked_at or link.failed_attempts >= 3:
            raise OrderAPIError(423, "CONFIRMATION_LOCKED", "Confirmation is locked; contact the shop.")
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
        if order.status == OrderStatus.DELIVERED:
            raise OrderAPIError(409, "BUYER_DETAILS_CLOSED", "Delivered order details are view-only.")
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
                    **self.editing_policy(order),
                },
            }
        )
        proposal = self.session.scalar(
            select(BuyerRequest)
            .where(
                BuyerRequest.order_id == order.id,
                BuyerRequest.decision == "REVIEW_REQUIRED",
                BuyerRequest.resolution.is_(None),
            )
            .order_by(BuyerRequest.created_at.desc(), BuyerRequest.id.desc())
            .limit(1)
        )
        if proposal and "latitude" in proposal.submitted_values:
            result["proposed_latitude"] = proposal.submitted_values.get("latitude")
            result["proposed_longitude"] = proposal.submitted_values.get("longitude")
        self.session.commit()
        return result

    def editing_policy(self, order):
        policy = self.session.get(BuyerEditPolicy, order.id)
        window = order.delivery_time_window or ""
        start = None
        if "/" in window:
            try:
                start = datetime.fromisoformat(window.split("/", 1)[0])
                if start.tzinfo is None:
                    start = None
            except ValueError:
                start = None
        cutoff = policy.cutoff_at if policy and policy.cutoff_at else (
            start - timedelta(hours=1) if start else None
        )
        used = policy.edit_count if policy else 0
        initial_submitted = bool(policy and policy.initial_submitted_at)
        now = utcnow()
        terminal = order.status in {OrderStatus.DELIVERED, OrderStatus.CANCELLED}
        reason = (
            "ORDER_TERMINAL" if terminal else
            "EDITS_EXHAUSTED" if used >= 3 else
            "NO_CONCRETE_WINDOW" if initial_submitted and cutoff is None else
            "CUTOFF_PASSED" if initial_submitted and (
                (policy and policy.closed_at) or cutoff is not None and now >= cutoff
            ) else None
        )
        return {
            "editable": reason is None,
            "reason": reason,
            "deadline": cutoff,
            "cutoff_at": cutoff,
            "edit_count": used,
            "remaining_edits": max(0, 3 - used),
            "max_edits": 3,
            "delivery_time_window": order.delivery_time_window,
            "delivery_day": (order.parsing_metadata.get("parcel") or {}).get("delivery_day"),
            "initial_submitted": initial_submitted,
            "timezone": "Asia/Yangon",
        }

    def request_submission(self, token, credential, body):
        link, order = self.authorize(token, credential)
        payload = body.model_dump(mode="json")
        payload_hash = digest("REQUEST" + json.dumps(payload, sort_keys=True))
        receipt = self.session.get(BuyerSubmissionReceipt, (order.id, body.request_id))
        if receipt is not None:
            if receipt.payload_hash != payload_hash:
                raise OrderAPIError(409, "BUYER_REQUEST_CONFLICT", "Request ID was already used for different data.")
            self.session.commit()
            return receipt.response_body

        now = utcnow()
        self.mutable(link, order)
        policy = self.session.get(BuyerEditPolicy, order.id)
        initial = policy is None or policy.initial_submitted_at is None
        start, end = body.time_window.start.astimezone(UTC), body.time_window.end.astimezone(UTC)
        window = f"{start.isoformat()}/{end.isoformat()}"
        window_changed = window != order.delivery_time_window
        if (
            not initial and window_changed and start <= now + timedelta(hours=1)
            or start.astimezone(YANGON).date() < now.astimezone(YANGON).date()
            or end > now + timedelta(days=self.settings.buyer_max_schedule_days)
            or start.astimezone(YANGON).date() != end.astimezone(YANGON).date()
        ):
            raise OrderAPIError(422, "INVALID_DELIVERY_WINDOW", "Time window must satisfy notice, scheduling, and Yangon-day limits.")
        if policy is not None and not initial:
            if policy.closed_at or policy.edit_count >= 3:
                raise OrderAPIError(409, "BUYER_EDITS_EXHAUSTED", "The three allowed edits have been used.")
            if policy.cutoff_at is not None and now >= policy.cutoff_at:
                policy.closed_at = now
                self.session.commit()
                raise OrderAPIError(409, "BUYER_EDIT_CUTOFF_PASSED", "The delivery change cutoff has passed.")
            if policy.cutoff_at is None and not order.delivery_time_window:
                raise OrderAPIError(409, "CONCRETE_WINDOW_REQUIRED", "A concrete delivery window must be confirmed before edits can be enabled.")

        reference = self.session.get(LocationReference, order.id)
        reasons = []
        if reference is None:
            if initial and not body.initial_pin_acknowledged:
                raise OrderAPIError(409, "INITIAL_PIN_ACKNOWLEDGEMENT_REQUIRED", "Initial pin submission requires acknowledgement of dispatcher review.")
            reasons.append("INITIAL_PIN_REQUIRES_REVIEW")
        else:
            target = self.boundaries.township_at(body.latitude, body.longitude)
            origin = self.boundaries.township_at(reference.latitude, reference.longitude)
            if origin != reference.township or reference.township != order.township or target is None:
                reasons.append("TOWNSHIP_BOUNDARY_UNVERIFIED")
            elif target != reference.township:
                reasons.append("CROSS_TOWNSHIP_APPROVAL_REQUIRED")
            elif distance_meters(reference.latitude, reference.longitude, body.latitude, body.longitude) > 500:
                reasons.append("ZONE_2_RESCHEDULE_REVIEW_REQUIRED")
        assigned = order.status in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}
        if assigned and window != order.delivery_time_window:
            raise OrderAPIError(409, "ASSIGNED_WINDOW_LOCKED", "The delivery date and window cannot change after assignment.")
        if assigned:
            reasons.append("ASSIGNED_CHANGE_REVIEW_REQUIRED")
        if body.action == "RESCHEDULE" and not self.settings.buyer_rescheduling_enabled:
            reasons.append("COURIER_RESCHEDULING_REVIEW_REQUIRED")
        if body.action == "LEAVE_WITH_SECURITY" and not self.settings.buyer_leave_with_security_enabled:
            reasons.append("LEAVE_WITH_SECURITY_REVIEW_REQUIRED")
        if body.action == "AVAILABLE" and order.confidence_level == "RED":
            reasons.append("ORDER_VALIDATION_REVIEW_REQUIRED")
        location_reasons = [r for r in reasons if r not in {
            "COURIER_RESCHEDULING_REVIEW_REQUIRED", "LEAVE_WITH_SECURITY_REVIEW_REQUIRED",
            "ORDER_VALIDATION_REVIEW_REQUIRED",
        }]
        pending = self.session.scalar(select(BuyerRequest.id).where(
            BuyerRequest.order_id == order.id,
            BuyerRequest.decision == "REVIEW_REQUIRED",
            BuyerRequest.resolution.is_(None),
        ).limit(1))
        if pending:
            reasons.append("PENDING_BUYER_REVIEW")

        old_values = {
            "latitude": str(order.latitude) if order.latitude is not None else None,
            "longitude": str(order.longitude) if order.longitude is not None else None,
            "delivery_time_window": order.delivery_time_window,
            "delivery_instructions": order.delivery_instructions,
        }
        changes = {
            "latitude": body.latitude, "longitude": body.longitude,
            "delivery_time_window": window,
        }
        changes["delivery_instructions"] = body.instructions
        latest = self.session.scalar(select(BuyerRequest).where(
            BuyerRequest.order_id == order.id, BuyerRequest.kind == "RESPONSE",
        ).order_by(BuyerRequest.created_at.desc(), BuyerRequest.id.desc()).limit(1))
        def normalized(values):
            from decimal import Decimal

            return {
                "latitude": Decimal(str(values["latitude"])),
                "longitude": Decimal(str(values["longitude"])),
                "time_window": values["time_window"], "action": values["action"],
                "instructions": values.get("instructions") or None,
            }
        previous_submission = latest.submitted_values if latest and latest.submitted_values.get("atomic_request") else None
        changed = normalized(payload) != normalized(previous_submission) if previous_submission else any(
            getattr(order, k) != v for k, v in changes.items()
        )
        if not initial and not changed and latest:
            response = self.result(latest, order)
            response["request_id"] = body.request_id
            response["editing_policy"] = self.editing_policy(order)
            from app.schemas.buyer import BuyerActionResult

            response = BuyerActionResult.model_validate(response).model_dump(mode="json")
            self.session.add(BuyerSubmissionReceipt(order_id=order.id, request_id=body.request_id,
                link_id=link.id, payload_hash=payload_hash, response_body=response, created_at=now))
            self.session.commit()
            return response
        if not initial and changed and policy.edit_count >= 3:
            raise OrderAPIError(409, "BUYER_EDITS_EXHAUSTED", "The three allowed edits have been used.")
        if policy is None:
            policy = BuyerEditPolicy(order_id=order.id, edit_count=0)
            self.session.add(policy)
        if initial:
            policy.initial_submitted_at = now
            policy.cutoff_at = start - timedelta(hours=1)
        elif changed:
            policy.edit_count += 1
            policy.cutoff_at = start - timedelta(hours=1)
        policy.updated_at = now

        previous_status = order.status
        from uuid import uuid5

        # A later complete submission replaces older pending submissions. Keep
        # their audit rows, but do not let out-of-order approvals restore an old pin.
        old_submissions = self.session.scalars(select(BuyerRequest).where(
            BuyerRequest.order_id == order.id, BuyerRequest.kind == "RESPONSE",
            BuyerRequest.decision == "REVIEW_REQUIRED", BuyerRequest.resolution.is_(None),
        )).all()
        superseded = {r.request_id for r in old_submissions if r.submitted_values.get("atomic_request")}
        superseded |= {uuid5(key, "location") for key in tuple(superseded)}
        if superseded:
            for prior in self.session.scalars(select(BuyerRequest).where(
                BuyerRequest.order_id == order.id, BuyerRequest.request_id.in_(superseded),
                BuyerRequest.resolution.is_(None),
            )):
                prior.resolution, prior.resolution_reason, prior.resolved_at = (
                    "REJECT", "Superseded by a newer buyer submission", now,
                )

        location_row = BuyerRequest(
            order_id=order.id, link_id=link.id, request_id=uuid5(body.request_id, "location"),
            payload_hash=digest("LOCATION" + payload_hash), kind="LOCATION",
            decision="REVIEW_REQUIRED" if location_reasons else "APPLIED",
            reason_codes=location_reasons,
            previous_values={k: old_values[k] for k in ("latitude", "longitude")},
            submitted_values={"request_id": str(uuid5(body.request_id, "location")),
                "latitude": payload["latitude"], "longitude": payload["longitude"],
                "initial_pin_acknowledged": body.initial_pin_acknowledged},
        )
        self.session.add(location_row)
        if location_reasons and "PENDING_BUYER_REVIEW" not in reasons:
            reasons.append("PENDING_BUYER_REVIEW")
        decision = "REVIEW_REQUIRED" if reasons else "APPLIED"
        row = BuyerRequest(
            order_id=order.id, link_id=link.id, request_id=body.request_id,
            payload_hash=payload_hash, kind="RESPONSE", decision=decision,
            reason_codes=list(dict.fromkeys(reasons)), previous_values=old_values,
            submitted_values={**payload, "atomic_request": True},
        )
        self.session.add(row)
        # Keep the buyer's selected ETA and instructions even while a new pin
        # awaits review; assigned orders retain all active material unchanged.
        if not assigned:
            order.delivery_time_window = window
            order.delivery_instructions = body.instructions
            if reference is not None and not reasons:
                order.latitude, order.longitude = body.latitude, body.longitude
            sync_parcel_schedule(order, {"delivery_time_window": window})
            order.updated_at = now
            if initial and order.status not in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}:
                order.status = OrderStatus.NEEDS_REVIEW if reasons else OrderStatus.CONFIRMED
        if reasons:
            order.manual_review_required = True
        metadata = deepcopy(order.parsing_metadata)
        metadata["buyer_confirmation"] = {"request_id": str(body.request_id), "decision": decision, "kind": "REQUEST"}
        order.parsing_metadata = metadata
        self.event(order, "BUYER_LOCATION", {"link_id": str(link.id), "request_id": str(body.request_id), "decision": decision, "reason_codes": row.reason_codes}, previous_status)
        self.event(order, "BUYER_RESPONSE", {"link_id": str(link.id), "request_id": str(body.request_id), "decision": decision, "reason_codes": row.reason_codes}, previous_status)
        self.session.flush()
        response = self.result(row, order)
        response["editing_policy"] = self.editing_policy(order)
        from app.schemas.buyer import BuyerActionResult

        response = BuyerActionResult.model_validate(response).model_dump(mode="json")
        self.session.add(BuyerSubmissionReceipt(
            order_id=order.id, request_id=body.request_id, link_id=link.id,
            payload_hash=payload_hash, response_body=response, created_at=now,
        ))
        self.session.commit()
        return response

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
        policy = self.session.get(BuyerEditPolicy, order.id)
        now = utcnow()
        if policy is None:
            window = changes.get("delivery_time_window", order.delivery_time_window)
            start = datetime.fromisoformat(window.split("/", 1)[0]) if window and "/" in window else None
            policy = BuyerEditPolicy(
                order_id=order.id, edit_count=0, initial_submitted_at=now,
                cutoff_at=start - timedelta(hours=1) if start else None,
            )
            self.session.add(policy)
        else:
            material = any(getattr(order, key) != value for key, value in changes.items())
            split_initial_response = (
                kind == "RESPONSE"
                and policy.cutoff_at is None
                and self.session.scalar(select(BuyerRequest.id).where(
                    BuyerRequest.order_id == order.id,
                    BuyerRequest.kind == "RESPONSE",
                ).limit(1)) is None
                and self.session.scalar(select(BuyerRequest.id).where(
                    BuyerRequest.order_id == order.id,
                    BuyerRequest.kind == "LOCATION",
                ).limit(1)) is not None
            )
            if material and not split_initial_response:
                window = changes.get("delivery_time_window", order.delivery_time_window)
                start = None
                if window and "/" in window:
                    start = datetime.fromisoformat(window.split("/", 1)[0])
                if start is None:
                    raise OrderAPIError(409, "CONCRETE_WINDOW_REQUIRED", "Choose a specific delivery window before editing.")
                if policy.cutoff_at is not None and now >= policy.cutoff_at:
                    raise OrderAPIError(409, "BUYER_EDIT_CUTOFF_PASSED", "The delivery change cutoff has passed.")
                if policy.edit_count >= 3:
                    raise OrderAPIError(409, "BUYER_EDITS_EXHAUSTED", "The three allowed edits have been used.")
                policy.edit_count += 1
                policy.cutoff_at = start - timedelta(hours=1)
                policy.updated_at = now
            elif split_initial_response:
                window = changes.get("delivery_time_window")
                if window and "/" in window:
                    policy.cutoff_at = datetime.fromisoformat(window.split("/", 1)[0]) - timedelta(hours=1)
                policy.updated_at = now
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
        if reasons and order.status not in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}:
            order.status = OrderStatus.NEEDS_REVIEW
            order.manual_review_required = True
        elif kind == "RESPONSE" and body.action == "AVAILABLE" and order.confidence_level != "RED" and order.status in PRE_DISPATCH:
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
        self.mutable(link, order)
        reference = self.session.get(LocationReference, order.id)
        reasons = []
        if order.status in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}:
            reasons.append("ASSIGNED_CHANGE_REVIEW_REQUIRED")
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
        self.mutable(link, order)
        reasons, changes = [], {}
        now = utcnow()
        if body.time_window:
            start, end = (
                body.time_window.start.astimezone(UTC),
                body.time_window.end.astimezone(UTC),
            )
            if f"{start.isoformat()}/{end.isoformat()}" != order.delivery_time_window and start < now + timedelta(
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
            if order.status in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY} and changes["delivery_time_window"] != order.delivery_time_window:
                raise OrderAPIError(409, "ASSIGNED_WINDOW_LOCKED", "The delivery date and window cannot change after assignment.")
            if not self.settings.buyer_rescheduling_enabled:
                reasons.append("COURIER_RESCHEDULING_REVIEW_REQUIRED")
            if now.astimezone(YANGON).hour >= self.settings.buyer_cutoff_hour:
                reasons.append("COURIER_CUTOFF_REVIEW_REQUIRED")
        if (
            body.action == "LEAVE_WITH_SECURITY"
            and not self.settings.buyer_leave_with_security_enabled
        ):
            reasons.append("LEAVE_WITH_SECURITY_REVIEW_REQUIRED")
        if order.status in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}:
            reasons.append("ASSIGNED_CHANGE_REVIEW_REQUIRED")
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

        from app.services.automatic_assignment import lock_allocator

        lock_allocator(self.session)
        order = self.management_order(order_id, actor)
        assigned = order.status in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}
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
        if (order.status not in PRE_DISPATCH and order.status not in {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}) or row.decision != "REVIEW_REQUIRED":
            raise OrderAPIError(
                409,
                "BUYER_REVIEW_NOT_ELIGIBLE",
                "Only pending pre-dispatch requests can be reviewed.",
            )
        changes = {}
        if body.decision == "APPROVE":
            if row.submitted_values.get("atomic_request"):
                from app.schemas.buyer import BuyerRequestSubmission

                values = {k: v for k, v in row.submitted_values.items() if k != "atomic_request"}
                value = BuyerRequestSubmission.model_validate(values)
                # Location has its own request and requires its own approval.
                changes = {
                    "delivery_time_window": f"{value.time_window.start.astimezone(UTC).isoformat()}/{value.time_window.end.astimezone(UTC).isoformat()}",
                    "delivery_instructions": value.instructions,
                }
            elif row.kind == "LOCATION":
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
        if not assigned:
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
        if assigned:
            remaining = self.session.scalar(
                select(BuyerRequest.id).where(
                    BuyerRequest.order_id == order.id,
                    BuyerRequest.decision == "REVIEW_REQUIRED",
                    BuyerRequest.resolution.is_(None),
                ).limit(1)
            )
            if remaining is None:
                from app.db.rider_models import AutomaticAllocation, DeliveryAssignment
                from app.services.automatic_assignment import material_hash, customer_response
                from app.services.riders import bump_queue

                allocation = self.session.get(AutomaticAllocation, order.id)
                if allocation is not None:
                    allocation.material_hash = material_hash(order)
                    effective_response, issue = customer_response(self.session, order)
                    if effective_response is not None and issue is None:
                        allocation.buyer_response_id = effective_response.id
                    allocation.reason = "Dispatcher reconfirmed reviewed buyer changes for the current rider."
                assignment = self.session.scalar(select(DeliveryAssignment).where(
                    DeliveryAssignment.order_id == order.id,
                    DeliveryAssignment.status == "ACTIVE",
                ))
                if assignment is not None:
                    bump_queue(self.session, assignment.rider_id)
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
