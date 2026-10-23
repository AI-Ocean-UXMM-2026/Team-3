"""Link-bound buyer OTP lifecycle and the optional Twilio Verify adapter."""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

import httpx2 as httpx
import phonenumbers
from phonenumbers import PhoneNumberFormat
from sqlalchemy import select

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerOtpChallenge, ConfirmationLink
from app.db.models import DeliveryEvent, Order, utcnow
from app.domain.lifecycle import OrderStatus
from app.services.buyer_confirmation import digest, lock_order

TWILIO_ORIGIN = "https://verify.twilio.com/v2"


def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("9509"):
        digits = "959" + digits[4:]
    if digits.startswith("95"):
        number_text = "+" + digits
    elif digits.startswith("09"):
        number_text = digits
    elif digits.startswith("9") and len(digits) == 10:
        number_text = "+95" + digits
    else:
        number_text = ""
    try:
        number = phonenumbers.parse(number_text, "MM") if number_text else None
        if (
            number is not None
            and phonenumbers.is_valid_number_for_region(number, "MM")
            and phonenumbers.number_type(number) == phonenumbers.PhoneNumberType.MOBILE
        ):
            return phonenumbers.format_number(number, PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    raise OrderAPIError(409, "BUYER_PHONE_UNAVAILABLE", "A valid Myanmar mobile number is required.")


def _twilio(settings, operation, *, sid=None, data=None):
    account = settings.buyer_twilio_account_sid
    service = settings.buyer_twilio_verify_service_sid
    token = settings.buyer_twilio_auth_token.get_secret_value() if settings.buyer_twilio_auth_token else ""
    if not (account and service and token and settings.buyer_otp_external_sends_enabled):
        raise OrderAPIError(503, "BUYER_OTP_UNAVAILABLE", "Phone verification is temporarily unavailable.")
    path = f"/Services/{quote(service, safe='')}/Verifications"
    if operation == "check":
        path = f"/Services/{quote(service, safe='')}/VerificationCheck"
    elif operation == "cancel":
        path += "/" + quote(sid or "", safe="")
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                TWILIO_ORIGIN + path,
                data=data or ({"Status": "canceled"} if operation == "cancel" else {}),
                auth=(account, token),
            )
        if response.status_code >= 400:
            if operation == "cancel" and response.status_code == 404:
                try:
                    provider_error = response.json()
                except Exception:
                    provider_error = None
                if (
                    isinstance(provider_error, dict)
                    and type(provider_error.get("code")) is int
                    and provider_error["code"] == 20404
                ):
                    return {"status": "canceled"}
            raise ValueError("provider rejected request")
        return response.json()
    except Exception as exc:
        raise OrderAPIError(503, "BUYER_OTP_UNAVAILABLE", "Phone verification is temporarily unavailable.") from exc


class BuyerOtpService:
    def __init__(self, session, settings):
        self.session, self.settings = session, settings

    def _link(self, token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise OrderAPIError(404, "CONFIRMATION_UNAVAILABLE", "Confirmation link is unavailable.")
        token_hash = digest(token)
        order_id = self.session.scalar(
            select(ConfirmationLink.order_id).where(ConfirmationLink.token_hash == token_hash)
        )
        if order_id is not None:
            from app.services.automatic_assignment import lock_allocator

            lock_allocator(self.session)
            lock_order(self.session, order_id)
        link = self.session.scalar(select(ConfirmationLink).where(ConfirmationLink.token_hash == token_hash))
        if link is None:
            raise OrderAPIError(404, "CONFIRMATION_UNAVAILABLE", "Confirmation link is unavailable.")
        order = self.session.get(Order, link.order_id)
        if (link.revoked_at or order.status == OrderStatus.CANCELLED or
            not hmac.compare_digest(link.phone_binding, hmac.new(link.token_hash.encode(), (order.customer_phone or "").encode(), hashlib.sha256).hexdigest())):
            raise OrderAPIError(404, "CONFIRMATION_UNAVAILABLE", "Confirmation link is unavailable.")
        expiry = link.delivered_view_until if order.status == OrderStatus.DELIVERED else link.expires_at
        if expiry is None or expiry <= utcnow():
            raise OrderAPIError(410, "CONFIRMATION_EXPIRED", "Confirmation link has expired.")
        if link.locked_at or link.failed_attempts >= 3:
            raise OrderAPIError(423, "CONFIRMATION_LOCKED", "Confirmation is locked; contact the shop.")
        if order.status not in {
            OrderStatus.DRAFT,
            OrderStatus.NEEDS_REVIEW, OrderStatus.AWAITING_CONFIRMATION, OrderStatus.CONFIRMED,
            OrderStatus.READY_FOR_DISPATCH, OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED,
        }:
            raise OrderAPIError(409, "BUYER_CHANGES_CLOSED", "Delivery details cannot be changed at this stage.")
        return link, order

    def _event(self, order, link, action):
        self.session.add(DeliveryEvent(
            order_id=order.id,
            event_type="BUYER_SECURITY",
            previous_status=order.status,
            new_status=order.status,
            event_metadata={"link_id": str(link.id), "action": action},
        ))

    def start(self, token):
        # Allocation and OTP start share this coordinator; always acquire it
        # before the order lock taken by _link().
        link, order = self._link(token)
        phone = normalize_phone(order.customer_phone)
        phone_binding = hashlib.sha256(phone.encode()).hexdigest()
        now = utcnow()
        # Local expiry, revocation, and lockout do not necessarily expire a
        # Twilio verification. Keep its SID in the replacement set so Twilio
        # cannot reuse the old code for a different link.
        active = self.session.scalars(select(BuyerOtpChallenge).where(
            BuyerOtpChallenge.phone_binding == phone_binding,
            BuyerOtpChallenge.status.in_({"PENDING", "CANCEL_FAILED", "EXPIRED", "REVOKED", "LOCKED"}),
        ).with_for_update()).all()
        latest = self.session.scalar(
            select(BuyerOtpChallenge)
            .where(BuyerOtpChallenge.phone_binding == phone_binding)
            .order_by(BuyerOtpChallenge.created_at.desc())
            .limit(1)
        )
        if (
            latest is not None
            and latest.status in {"PENDING", "CANCEL_FAILED", "REPLACEMENT_FAILED"}
            and latest.resend_after > now
        ):
            raise OrderAPIError(429, "BUYER_OTP_COOLDOWN", "Please wait before requesting another code.")
        # Record cooldown before provider I/O so retries after a timeout cannot churn sends.
        for challenge in active:
            challenge.resend_after = now + timedelta(seconds=60)
        for challenge in active:
            if challenge.provider == "TWILIO" and challenge.verification_sid:
                try:
                    _twilio(self.settings, "cancel", sid=challenge.verification_sid)
                except OrderAPIError:
                    for previous in active:
                        previous.status, previous.demo_code = "CANCEL_FAILED", None
                    self.session.commit()
                    raise
        for challenge in active:
            challenge.status, challenge.demo_code = "REPLACED", None

        code = f"{secrets.randbelow(1_000_000):06d}"
        provider, sid, demo_code = "DEMO", None, code
        if self.settings.buyer_otp_mode == "twilio":
            try:
                result = _twilio(self.settings, "send", data={"To": phone, "Channel": "sms"})
            except OrderAPIError:
                for previous in active:
                    previous.status, previous.demo_code = "REPLACEMENT_FAILED", None
                if active:
                    self.session.commit()
                raise
            provider, sid, demo_code = "TWILIO", result.get("sid"), None
            if not sid:
                raise OrderAPIError(503, "BUYER_OTP_UNAVAILABLE", "Phone verification is temporarily unavailable.")
        challenge = BuyerOtpChallenge(
            link_id=link.id,
            phone_binding=phone_binding,
            generation=link.generation,
            code_digest=digest(code),
            demo_code=demo_code,
            provider=provider,
            verification_sid=sid,
            status="PENDING",
            attempts=0,
            expires_at=min(now + timedelta(minutes=5), link.expires_at),
            resend_after=now + timedelta(seconds=60),
        )
        self.session.add(challenge)
        self.session.commit()
        return {
            "challenge_id": challenge.id,
            "destination_masked": "••••" + phone[-4:],
            "expires_at": challenge.expires_at,
            "resend_after": challenge.resend_after,
            "mode": "DEMO" if provider == "DEMO" else "SMS",
            **({"demo_code": demo_code} if provider == "DEMO" and self.settings.environment != "production" else {}),
        }

    def verify(self, token, code):
        link, order = self._link(token)
        phone = normalize_phone(order.customer_phone)
        phone_binding = hashlib.sha256(phone.encode()).hexdigest()
        challenge = self.session.scalar(select(BuyerOtpChallenge).where(
            BuyerOtpChallenge.link_id == link.id,
            BuyerOtpChallenge.phone_binding == phone_binding,
            BuyerOtpChallenge.status == "PENDING",
        ).order_by(BuyerOtpChallenge.created_at.desc()).with_for_update())
        now = utcnow()
        if challenge is None:
            raise OrderAPIError(403, "BUYER_VERIFICATION_FAILED", "Verification failed; contact the shop if needed.")
        if challenge.generation != link.generation:
            challenge.status, challenge.demo_code = "REVOKED", None
            self.session.commit()
            raise OrderAPIError(403, "BUYER_VERIFICATION_FAILED", "Verification failed; contact the shop if needed.")
        if challenge.expires_at <= now:
            if challenge:
                challenge.status, challenge.demo_code = "EXPIRED", None
                self.session.commit()
            raise OrderAPIError(403, "BUYER_VERIFICATION_FAILED", "Verification failed; contact the shop if needed.")
        valid = False
        if challenge.provider == "DEMO":
            valid = bool(re.fullmatch(r"[0-9]{6}", code or "")) and (
                hmac.compare_digest(challenge.code_digest, digest(code))
                or (self.settings.environment != "production" and hmac.compare_digest(code, "123456"))
            )
        elif challenge.verification_sid and re.fullmatch(r"[0-9]{6}", code or ""):
            response = _twilio(self.settings, "check", data={"VerificationSid": challenge.verification_sid, "Code": code})
            valid = response.get("status") == "approved"
        if not valid:
            challenge.attempts += 1
            link.failed_attempts += 1
            if challenge.attempts >= 3 or link.failed_attempts >= 3:
                challenge.status = "LOCKED"
                challenge.demo_code = None
                link.locked_at = now
                link.generation += 1
            self._event(order, link, "LOCKED" if link.locked_at else "VERIFICATION_FAILED")
            self.session.commit()
            raise OrderAPIError(403, "BUYER_VERIFICATION_FAILED", "Verification failed; contact the shop if needed.")
        challenge.status, challenge.consumed_at, challenge.demo_code = "CONSUMED", now, None
        link.generation += 1
        link.verified_at = now
        from app.db.buyer_models import BuyerSession
        from app.services.buyer_confirmation import digest as token_digest
        import secrets as secret_module
        credential = secret_module.token_urlsafe(32)
        expires = min(link.expires_at, now + timedelta(minutes=self.settings.buyer_session_minutes))
        self.session.add(BuyerSession(link_id=link.id, token_hash=token_digest(credential), generation=link.generation, expires_at=expires))
        self._event(order, link, "VERIFIED")
        self.session.commit()
        return {"access_token": credential, "token_type": "Bearer", "expires_at": expires}
