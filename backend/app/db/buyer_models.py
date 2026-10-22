"""Buyer capabilities and private request audit, separate from dispatcher credentials."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import JSON_VALUE, Base, UTCDateTime, utcnow


class ConfirmationLink(Base):
    __tablename__ = "confirmation_links"
    __table_args__ = (
        CheckConstraint("failed_attempts BETWEEN 0 AND 3", name="ck_link_attempts"),
        CheckConstraint("generation >= 0 AND nonce >= 0", name="ck_link_counters"),
        Index("ix_confirmation_order", "order_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    phone_binding: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    delivered_view_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    nonce: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class BuyerSession(Base):
    __tablename__ = "buyer_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    link_id: Mapped[UUID] = mapped_column(
        ForeignKey("confirmation_links.id", ondelete="RESTRICT"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    generation: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class BuyerOtpChallenge(Base):
    __tablename__ = "buyer_otp_challenges"
    __table_args__ = (
        CheckConstraint("attempts BETWEEN 0 AND 3", name="ck_buyer_otp_attempts"),
        CheckConstraint("generation >= 0", name="ck_buyer_otp_generation"),
        Index("ix_buyer_otp_link_status", "link_id", "status"),
        Index("ix_buyer_otp_phone_status", "phone_binding", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    link_id: Mapped[UUID] = mapped_column(ForeignKey("confirmation_links.id", ondelete="RESTRICT"))
    phone_binding: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int] = mapped_column(Integer)
    code_digest: Mapped[str] = mapped_column(String(64))
    # Only local/test challenges retain a retrievable code for the loopback demo boundary.
    demo_code: Mapped[str | None] = mapped_column(String(6))
    provider: Mapped[str] = mapped_column(String(16))
    verification_sid: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    resend_after: Mapped[datetime] = mapped_column(UTCDateTime())
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class LocationReference(Base):
    """Dispatcher-attested anchor. Buyer-submitted coordinates never become anchors."""

    __tablename__ = "location_references"
    __table_args__ = (
        CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
            name="ck_reference_coordinates",
        ),
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    township: Mapped[str] = mapped_column(String(128))
    source_reference: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class BuyerRequest(Base):
    __tablename__ = "buyer_requests"
    __table_args__ = (
        CheckConstraint("kind IN ('LOCATION','RESPONSE')", name="ck_buyer_request_kind"),
        CheckConstraint("decision IN ('APPLIED','REVIEW_REQUIRED')", name="ck_buyer_decision"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('APPROVE','REJECT')", name="ck_buyer_resolution"
        ),
        Index("ix_buyer_request_order", "order_id", "created_at", "id"),
        Index("ux_buyer_request_retry", "link_id", "request_id", unique=True),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    link_id: Mapped[UUID] = mapped_column(ForeignKey("confirmation_links.id", ondelete="RESTRICT"))
    request_id: Mapped[UUID] = mapped_column(Uuid)
    payload_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    decision: Mapped[str] = mapped_column(String(24))
    reason_codes: Mapped[list] = mapped_column(JSON_VALUE)
    previous_values: Mapped[dict] = mapped_column(JSON_VALUE)
    submitted_values: Mapped[dict] = mapped_column(JSON_VALUE)
    resolution: Mapped[str | None] = mapped_column(String(16))
    resolution_reason: Mapped[str | None] = mapped_column(String(500))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class BuyerRateLimit(Base):
    __tablename__ = "buyer_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
