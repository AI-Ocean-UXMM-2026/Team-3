"""Link-bound buyer phone OTP challenges."""

import sqlalchemy as sa
from alembic import op

revision = "0007_buyer_otp"
down_revision = "0006_automatic_assignment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "buyer_otp_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("link_id", sa.Uuid(), sa.ForeignKey("confirmation_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("phone_binding", sa.String(64), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("code_digest", sa.String(64), nullable=False),
        sa.Column("demo_code", sa.String(6), nullable=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("verification_sid", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resend_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name="ck_buyer_otp_attempts"),
        sa.CheckConstraint("generation >= 0", name="ck_buyer_otp_generation"),
    )
    op.create_index("ix_buyer_otp_link_status", "buyer_otp_challenges", ["link_id", "status"])
    op.create_index("ix_buyer_otp_phone_status", "buyer_otp_challenges", ["phone_binding", "status"])


def downgrade():
    op.drop_table("buyer_otp_challenges")
