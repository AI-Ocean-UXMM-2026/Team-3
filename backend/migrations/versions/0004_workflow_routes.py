"""Add route/cash aggregates without rewriting or deleting existing order tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_workflow_routes"
down_revision = "0003_rider_copilot"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_routes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "rider_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("data", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("workflow_routes")
