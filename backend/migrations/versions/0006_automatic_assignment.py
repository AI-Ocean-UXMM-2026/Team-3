"""Durable automatic allocation and explicit rider offer consent.

Existing/manual assignments keep their historical accepted behavior. Automatic
offers always explicitly write PENDING and carry a non-null allocation cycle.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_automatic_assignment"
down_revision = "0005_routing_plans"
branch_labels = None
depends_on = None


def upgrade():
    response_check = (
        "response_status IN ('PENDING','ACCEPTED','DECLINED') "
        "AND NOT (status = 'ACTIVE' AND response_status = 'DECLINED')"
    )
    timestamp_check = (
        "(response_status = 'PENDING' AND responded_at IS NULL) OR "
        "(response_status = 'DECLINED' AND responded_at IS NOT NULL) OR "
        "(response_status = 'ACCEPTED' AND "
        "(allocation_cycle IS NULL OR responded_at IS NOT NULL))"
    )
    if op.get_bind().dialect.name == "sqlite":
        # ADD COLUMN avoids rebuilding a parent table referenced by historical
        # action receipts, with foreign-key enforcement kept ON throughout.
        op.execute(
            "ALTER TABLE delivery_assignments ADD COLUMN response_status VARCHAR(16) "
            "NOT NULL DEFAULT 'ACCEPTED' CONSTRAINT ck_assignment_response CHECK ("
            + response_check
            + ")"
        )
        op.execute(
            "ALTER TABLE delivery_assignments ADD COLUMN offer_version INTEGER NOT NULL "
            "DEFAULT 1 CONSTRAINT ck_offer_version CHECK (offer_version >= 1)"
        )
        op.add_column(
            "delivery_assignments", sa.Column("allocation_cycle", sa.Integer(), nullable=True)
        )
        op.execute(
            "ALTER TABLE delivery_assignments ADD COLUMN responded_at DATETIME "
            "CONSTRAINT ck_offer_timestamp CHECK ("
            + timestamp_check
            + ")"
        )
    else:
        op.add_column(
            "delivery_assignments",
            sa.Column("response_status", sa.String(16), nullable=False, server_default="ACCEPTED"),
        )
        op.add_column(
            "delivery_assignments",
            sa.Column("offer_version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.add_column(
            "delivery_assignments", sa.Column("allocation_cycle", sa.Integer(), nullable=True)
        )
        op.add_column(
            "delivery_assignments",
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_check_constraint("ck_assignment_response", "delivery_assignments", response_check)
        op.create_check_constraint("ck_offer_version", "delivery_assignments", "offer_version >= 1")
        op.create_check_constraint("ck_offer_timestamp", "delivery_assignments", timestamp_check)
    op.create_table("allocation_coordinator", sa.Column("id", sa.Integer(), primary_key=True))
    op.execute("INSERT INTO allocation_coordinator (id) VALUES (1)")
    op.create_table(
        "automatic_allocations",
        sa.Column(
            "order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True
        ),
        sa.Column(
            "dispatcher_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "buyer_response_id",
            sa.Uuid(),
            sa.ForeignKey("buyer_requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("material_hash", sa.String(64), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ASSIGNED','WAITING_FOR_RIDER','WAITING_FOR_READINESS','CANCELLED')",
            name="ck_allocation_status",
        ),
        sa.CheckConstraint("cycle >= 1", name="ck_allocation_cycle"),
    )
    op.create_index(
        "ix_allocation_wait", "automatic_allocations", ["status", "created_at", "order_id"]
    )
    op.create_table(
        "allocation_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "result", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ux_allocation_actor_request",
        "allocation_receipts",
        ["actor_id", "request_id"],
        unique=True,
    )


def downgrade():
    op.drop_table("allocation_receipts")
    op.drop_table("automatic_allocations")
    op.drop_table("allocation_coordinator")
    if op.get_bind().dialect.name != "sqlite":
        for name in ("ck_assignment_response", "ck_offer_version", "ck_offer_timestamp"):
            op.drop_constraint(name, "delivery_assignments", type_="check")
    for name in ("responded_at", "allocation_cycle", "offer_version", "response_status"):
        op.drop_column("delivery_assignments", name)
