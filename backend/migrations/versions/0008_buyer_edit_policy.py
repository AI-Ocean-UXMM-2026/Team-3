"""Durable buyer edit cutoff and atomic submission receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0008_buyer_edit_policy"
down_revision = "0007_buyer_otp"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "buyer_edit_policies",
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("initial_submitted_at", sa.DateTime(timezone=True)),
        sa.Column("cutoff_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("edit_count BETWEEN 0 AND 3", name="ck_buyer_edit_count"),
    )
    op.create_table(
        "buyer_submission_receipts",
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("request_id", sa.Uuid(), primary_key=True),
        sa.Column("link_id", sa.Uuid(), sa.ForeignKey("confirmation_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_id", "request_id", name="ux_buyer_receipt_order_request"),
    )
    op.create_table(
        "buyer_reminder_outbox",
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("provider_sid", sa.String(64)),
        sa.Column("message_body", sa.String(1000)),
        sa.Column("outcome_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','SENDING','ACCEPTED','UNKNOWN','SIMULATION','SKIPPED','DISABLED')", name="ck_buyer_reminder_status"),
    )


def downgrade():
    op.drop_table("buyer_reminder_outbox")
    op.drop_table("buyer_submission_receipts")
    op.drop_table("buyer_edit_policies")
