from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.domain.lifecycle import OrderStatus, UserRole
from app.schemas.orders import Confidence


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timestamp must have a timezone")
            return value.astimezone(UTC)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return None


class Base(DeclarativeBase):
    pass


def enum_type(enum, name):
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )


JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 200", name="ck_users_name_length"),
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="ck_users_email_length"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "user_role"))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, server_default=func.current_timestamp()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "cod_amount IS NULL OR (cod_amount >= 0 AND cod_amount <= 1000000000 "
            "AND cod_amount = CAST(cod_amount AS BIGINT))",
            name="ck_orders_cod",
        ),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL "
            "AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 "
            "AND longitude BETWEEN -180 AND 180)",
            name="ck_orders_coordinates",
        ),
        CheckConstraint("version >= 1", name="ck_orders_version"),
        CheckConstraint("parsing_mode IN ('rules','hybrid','structured')", name="ck_orders_mode"),
        CheckConstraint(
            "ai_availability_status IN ('not_requested','mock','disabled','available',"
            "'timeout','rate_limited','invalid_response','unavailable','privacy_blocked')",
            name="ck_orders_ai_status",
        ),
        CheckConstraint(
            "original_message IS NULL OR length(original_message) <= 10000",
            name="ck_orders_original_length",
        ),
        Index("ix_orders_merchant_created", "merchant_id", "created_at", "id"),
        Index("ix_orders_status_confidence", "status", "confidence_level"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    customer_name: Mapped[str | None] = mapped_column(String(200))
    customer_phone: Mapped[str | None] = mapped_column(String(32))
    original_message: Mapped[str | None] = mapped_column(Text)
    normalized_message: Mapped[str | None] = mapped_column(Text)
    township: Mapped[str | None] = mapped_column(String(128))
    street: Mapped[str | None] = mapped_column(String(1000))
    landmark: Mapped[str | None] = mapped_column(String(1000))
    building: Mapped[str | None] = mapped_column(String(500))
    floor: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(100))
    building_floor_unit: Mapped[str | None] = mapped_column(String(2000))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    cod_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 0))
    delivery_instructions: Mapped[str | None] = mapped_column(String(2000))
    delivery_time_window: Mapped[str | None] = mapped_column(String(500))
    confidence_level: Mapped[Confidence] = mapped_column(enum_type(Confidence, "confidence_level"))
    confidence_reasons: Mapped[list] = mapped_column(JSON_VALUE)
    parsing_mode: Mapped[str] = mapped_column(String(16))
    ai_availability_status: Mapped[str] = mapped_column(String(32))
    field_sources: Mapped[dict] = mapped_column(JSON_VALUE)
    parsing_metadata: Mapped[dict] = mapped_column(JSON_VALUE)
    manual_review_required: Mapped[bool] = mapped_column(default=True)
    status: Mapped[OrderStatus] = mapped_column(
        enum_type(OrderStatus, "order_status"), default=OrderStatus.DRAFT
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, server_default=func.current_timestamp()
    )
    __mapper_args__ = {"version_id_col": version}


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('ORDER_CREATED','ORDER_CORRECTED','STATUS_CHANGED',"
            "'BUYER_LINK_CREATED','BUYER_LINK_REVOKED','BUYER_SECURITY',"
            "'BUYER_LOCATION','BUYER_RESPONSE','LOCATION_REFERENCE','BUYER_REQUEST_REVIEWED',"
            "'RIDER_ASSIGNED','RIDER_UNASSIGNED','RIDER_SEQUENCE_CHANGED',"
            "'DELIVERY_STARTED','DELIVERY_COMPLETED','DELIVERY_FAILED')",
            name="ck_events_type",
        ),
        Index("ix_events_order_created", "order_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(32))
    previous_status: Mapped[OrderStatus | None] = mapped_column(
        enum_type(OrderStatus, "event_previous_status")
    )
    new_status: Mapped[OrderStatus] = mapped_column(enum_type(OrderStatus, "event_new_status"))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.current_timestamp()
    )
