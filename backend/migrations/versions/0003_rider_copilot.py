"""Rider operational profiles, assignment history and idempotent action receipts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_rider_copilot"
down_revision = "0002_buyer_confirmation"
branch_labels = None
depends_on = None

PREVIOUS_EVENTS = (
    "'ORDER_CREATED','ORDER_CORRECTED','STATUS_CHANGED','BUYER_LINK_CREATED',"
    "'BUYER_LINK_REVOKED','BUYER_SECURITY','BUYER_LOCATION','BUYER_RESPONSE','LOCATION_REFERENCE',"
    "'BUYER_REQUEST_REVIEWED'"
)
EVENTS = (
    PREVIOUS_EVENTS + ", 'RIDER_ASSIGNED','RIDER_UNASSIGNED','RIDER_SEQUENCE_CHANGED',"
    "'DELIVERY_STARTED','DELIVERY_COMPLETED','DELIVERY_FAILED'"
)


def fk(name, target, primary_key=False):
    return sa.Column(
        name,
        sa.Uuid(),
        sa.ForeignKey(target, ondelete="RESTRICT"),
        primary_key=primary_key,
        nullable=False,
    )


def timestamp(name, nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade():
    with op.batch_alter_table("delivery_events") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"event_type IN ({EVENTS})")
    op.create_table(
        "rider_profiles",
        fk("id", "users.id", True),
        sa.Column("operational_status", sa.String(16), nullable=False),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("queue_version", sa.Integer(), nullable=False),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint(
            "operational_status IN ('AVAILABLE','ON_BREAK','OFFLINE')", name="ck_rider_status"
        ),
        sa.CheckConstraint("version >= 1 AND queue_version >= 0", name="ck_rider_versions"),
    )
    op.execute(
        sa.text(
            "INSERT INTO rider_profiles (id, operational_status, contact_phone, version, "
            "queue_version, created_at, updated_at) SELECT id, 'OFFLINE', NULL, 1, 0, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users WHERE role = 'Rider'"
        )
    )
    op.create_table(
        "delivery_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        fk("order_id", "orders.id"),
        fk("rider_id", "rider_profiles.id"),
        fk("dispatcher_id", "users.id"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stop_sequence", sa.Integer()),
        sa.Column("failure_reason", sa.String(32)),
        sa.Column("failure_note", sa.String(500)),
        sa.Column("cod_collected", sa.Boolean()),
        timestamp("assigned_at"),
        timestamp("updated_at"),
        timestamp("ended_at", True),
        sa.CheckConstraint(
            "status IN ('ACTIVE','UNASSIGNED','COMPLETED','FAILED','CANCELLED')",
            name="ck_assignment_status",
        ),
        sa.CheckConstraint(
            "stop_sequence IS NULL OR stop_sequence BETWEEN 1 AND 10000",
            name="ck_assignment_sequence",
        ),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND ended_at IS NULL) OR "
            "(status != 'ACTIVE' AND ended_at IS NOT NULL)",
            name="ck_assignment_ended",
        ),
    )
    op.create_index(
        "ux_assignment_active_order",
        "delivery_assignments",
        ["order_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index("ix_assignment_rider_status", "delivery_assignments", ["rider_id", "status"])
    op.create_table(
        "rider_action_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        fk("actor_id", "users.id"),
        fk("rider_id", "rider_profiles.id"),
        fk("order_id", "orders.id"),
        fk("assignment_id", "delivery_assignments.id"),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "result", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        timestamp("created_at"),
    )
    op.create_index(
        "ux_rider_action_actor_request",
        "rider_action_receipts",
        ["actor_id", "request_id"],
        unique=True,
    )


def downgrade():
    for table in ("rider_action_receipts", "delivery_assignments", "rider_profiles"):
        op.drop_table(table)
    with op.batch_alter_table("delivery_events") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"event_type IN ({PREVIOUS_EVENTS})")
