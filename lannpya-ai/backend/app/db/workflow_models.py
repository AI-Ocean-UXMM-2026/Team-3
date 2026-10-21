"""Route/cash aggregates, separate from legacy merchant accounts."""

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, JSON_VALUE


class WorkflowRoute(Base):
    __tablename__ = "workflow_routes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rider_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    data: Mapped[dict] = mapped_column(JSON_VALUE)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
