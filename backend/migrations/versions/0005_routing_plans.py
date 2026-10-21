"""Add isolated routing previews, immutable planning inputs and actor request budgets."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_routing_plans"
down_revision = "0004_workflow_routes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "routing_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_routing_plan_version"),
    )
    op.create_index("ix_routing_plans_actor_id", "routing_plans", ["actor_id"])
    op.create_table(
        "routing_rate_limits",
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
        ),
        sa.Column("bucket", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("routing_rate_limits")
    op.drop_index("ix_routing_plans_actor_id", table_name="routing_plans")
    op.drop_table("routing_plans")
