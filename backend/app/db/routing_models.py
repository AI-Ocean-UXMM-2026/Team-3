from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import JSON_VALUE, Base, UTCDateTime, utcnow


class RoutingPlan(Base):
    __tablename__ = "routing_plans"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_routing_plan_version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(20), default="PREVIEW")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    data: Mapped[dict] = mapped_column(JSON_VALUE)
    __mapper_args__ = {"version_id_col": version}


class RoutingRateLimit(Base):
    __tablename__ = "routing_rate_limits"
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    bucket: Mapped[int] = mapped_column(Integer, default=0)
    count: Mapped[int] = mapped_column(Integer, default=0)
