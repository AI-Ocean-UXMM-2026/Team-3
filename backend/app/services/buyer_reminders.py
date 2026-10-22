"""Durable delivery-day reminder scheduler with an at-most-once provider claim."""

import asyncio
import logging
from datetime import timedelta

import httpx2 as httpx

from sqlalchemy import select, or_

from app.db.buyer_models import BuyerEditPolicy, BuyerReminderOutbox, ConfirmationLink
from app.db.models import Order, utcnow
from app.domain.lifecycle import OrderStatus
from app.services.buyer_confirmation import YANGON, phone_binding


TERMINAL = {OrderStatus.DELIVERED, OrderStatus.CANCELLED}
logger = logging.getLogger(__name__)


class TwilioMessagingProvider:
    def __init__(self, settings):
        self.settings = settings

    def send(self, phone, message):
        sid = self.settings.buyer_twilio_account_sid
        secret = self.settings.buyer_twilio_auth_token.get_secret_value()
        sender = self.settings.buyer_twilio_messaging_service_sid or self.settings.buyer_twilio_message_from
        payload = {"To": phone, "Body": message}
        payload["MessagingServiceSid" if self.settings.buyer_twilio_messaging_service_sid else "From"] = sender
        with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
            response = client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data=payload, auth=(sid, secret),
            )
            response.raise_for_status()
            return response.json().get("sid")


def _display_window(order):
    value = order.delivery_time_window or ""
    if "/" not in value:
        return ""
    start, end = [__import__("datetime").datetime.fromisoformat(part).astimezone(YANGON) for part in value.split("/", 1)]
    return f"{start:%H:%M}–{end:%H:%M}"


def _message(order, policy):
    day = (order.parsing_metadata.get("parcel") or {}).get("delivery_day") or policy.cutoff_at.astimezone(YANGON).date().isoformat()
    cutoff = policy.cutoff_at.astimezone(YANGON).strftime("%Y-%m-%d %H:%M Yangon time")
    return (
        f"LannPya delivery reminder for {day}, {_display_window(order)}. "
        f"You can make up to 3 delivery detail edits; {max(0, 3 - policy.edit_count)} remain. "
        f"Edits close at {cutoff} (1 hour before delivery starts). Use the buyer link already shared by the shop."
    )


def _eligible(session, order, policy, now):
    if order.status in TERMINAL or not policy.initial_submitted_at or policy.cutoff_at is None:
        return False
    if policy.closed_at or policy.edit_count >= 3 or now >= policy.cutoff_at:
        return False
    parcel = order.parsing_metadata.get("parcel") or {}
    if parcel.get("delivery_day") != now.astimezone(YANGON).date().isoformat():
        return False
    links = session.scalars(select(ConfirmationLink).where(
        ConfirmationLink.order_id == order.id,
        ConfirmationLink.revoked_at.is_(None),
    )).all()
    if not links:
        return False
    return any(
        link.expires_at > now
        and link.locked_at is None
        and link.failed_attempts < 3
        and link.phone_binding == phone_binding(link.token_hash, order.customer_phone)
        for link in links
    )


def run_reminder_pass(database, settings, provider=None, now=None):
    fixed_clock = now is not None
    now = now or utcnow()
    provider = provider or TwilioMessagingProvider(settings)
    lead = timedelta(minutes=settings.buyer_reminder_lead_minutes)
    sent, skipped, simulated = 0, 0, 0
    with database.sessions.begin() as session:
        candidates = session.scalars(select(BuyerEditPolicy.order_id).outerjoin(
            BuyerReminderOutbox, BuyerReminderOutbox.order_id == BuyerEditPolicy.order_id,
        ).where(
            BuyerEditPolicy.cutoff_at <= now + lead,
            or_(BuyerReminderOutbox.order_id.is_(None), BuyerReminderOutbox.status == "SENDING"),
        ).order_by(BuyerEditPolicy.cutoff_at, BuyerEditPolicy.order_id).limit(100)).all()
    for order_id in candidates:
        if not fixed_clock:
            now = utcnow()
        with database.sessions.begin() as session:
            from app.services.automatic_assignment import lock_allocator
            from app.services.buyer_confirmation import lock_order

            lock_allocator(session)
            lock_order(session, order_id)
            policy = session.get(BuyerEditPolicy, order_id)
            order = session.get(Order, order_id)
            if policy is None or order is None:
                continue
            row = session.get(BuyerReminderOutbox, order_id)
            if row is not None:
                if row.status == "SENDING" and row.created_at + timedelta(minutes=2) <= now:
                    row.status = "UNKNOWN"
                    row.outcome_at = now
                continue
            scheduled_at = policy.cutoff_at - lead
            delivery_day = (order.parsing_metadata.get("parcel") or {}).get("delivery_day")
            if delivery_day and delivery_day > now.astimezone(YANGON).date().isoformat():
                continue
            if now >= policy.cutoff_at and policy.closed_at is None:
                policy.closed_at = now
            if not _eligible(session, order, policy, now):
                if now >= scheduled_at:
                    session.add(BuyerReminderOutbox(order_id=order_id, scheduled_at=scheduled_at, cutoff_at=policy.cutoff_at, status="SKIPPED", outcome_at=now))
                    skipped += 1
                continue
            day = (order.parsing_metadata.get("parcel") or {}).get("delivery_day")
            if day != now.astimezone(YANGON).date().isoformat() or now >= policy.cutoff_at:
                session.add(BuyerReminderOutbox(order_id=order_id, scheduled_at=scheduled_at, cutoff_at=policy.cutoff_at, status="SKIPPED", outcome_at=now))
                skipped += 1
                continue
            outbox = BuyerReminderOutbox(
                order_id=order_id, scheduled_at=scheduled_at, cutoff_at=policy.cutoff_at,
                status="SENDING" if settings.buyer_reminder_external_sends_enabled and settings.environment == "production" else (
                    "SIMULATION" if settings.environment in {"local", "test"} else "DISABLED"
                ),
                created_at=now,
                message_body=_message(order, policy),
            )
            session.add(outbox)
            session.flush()
            if outbox.status != "SENDING":
                if outbox.status == "SIMULATION":
                    simulated += 1
                continue
            from app.services.buyer_otp import normalize_phone

            phone = normalize_phone(order.customer_phone)
            message = _message(order, policy)
        # The claim is committed before the network request. Any uncertain
        # provider outcome is final UNKNOWN and is never automatically retried.
        try:
            provider_sid = provider.send(phone, message)
        except Exception:
            status, provider_sid = "UNKNOWN", None
        else:
            status = "ACCEPTED" if provider_sid else "UNKNOWN"
        with database.sessions.begin() as session:
            outbox = session.get(BuyerReminderOutbox, order_id)
            if outbox and outbox.status == "SENDING":
                outbox.status = status
                outbox.provider_sid = provider_sid
                outbox.outcome_at = now
        sent += int(status == "ACCEPTED")
        skipped += int(status == "UNKNOWN")
    return {"accepted": sent, "skipped": skipped, "simulation": simulated}


async def reminder_worker(database, settings, stop_event):
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(run_reminder_pass, database, settings)
        except Exception as exc:
            logger.warning("Buyer reminder recovery deferred: %s", type(exc).__name__)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except TimeoutError:
            pass
