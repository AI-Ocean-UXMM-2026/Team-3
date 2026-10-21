from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import JSON_VALUE, Base, UTCDateTime, utcnow


class RiderProfile(Base):
    __tablename__ = "rider_profiles"
    __table_args__ = (
        CheckConstraint(
            "operational_status IN ('AVAILABLE','ON_BREAK','OFFLINE')", name="ck_rider_status"
        ),
        CheckConstraint("version >= 1 AND queue_version >= 0", name="ck_rider_versions"),
    )
    id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    operational_status: Mapped[str] = mapped_column(String(16), default="OFFLINE")
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    queue_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    __mapper_args__ = {"version_id_col": version}


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','UNASSIGNED','COMPLETED','FAILED','CANCELLED')",
            name="ck_assignment_status",
        ),
        CheckConstraint(
            "stop_sequence IS NULL OR stop_sequence BETWEEN 1 AND 10000",
            name="ck_assignment_sequence",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND ended_at IS NULL) OR "
            "(status != 'ACTIVE' AND ended_at IS NOT NULL)",
            name="ck_assignment_ended",
        ),
        Index(
            "ux_assignment_active_order",
            "order_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_assignment_rider_status", "rider_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    rider_id: Mapped[UUID] = mapped_column(ForeignKey("rider_profiles.id", ondelete="RESTRICT"))
    dispatcher_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    stop_sequence: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(String(32))
    failure_note: Mapped[str | None] = mapped_column(String(500))
    cod_collected: Mapped[bool | None]
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class RiderActionReceipt(Base):
    __tablename__ = "rider_action_receipts"
    __table_args__ = (
        Index("ux_rider_action_actor_request", "actor_id", "request_id", unique=True),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rider_id: Mapped[UUID] = mapped_column(ForeignKey("rider_profiles.id", ondelete="RESTRICT"))
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_assignments.id", ondelete="RESTRICT")
    )
    request_id: Mapped[UUID] = mapped_column(Uuid)
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
