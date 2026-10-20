"""Buyer confirmation capabilities, request audit and persistent rate limits."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_buyer_confirmation"
down_revision = "0001_order_management"
branch_labels = None
depends_on = None

EVENTS = (
    "'ORDER_CREATED','ORDER_CORRECTED','STATUS_CHANGED','BUYER_LINK_CREATED',"
    "'BUYER_LINK_REVOKED','BUYER_SECURITY','BUYER_LOCATION','BUYER_RESPONSE','LOCATION_REFERENCE',"
    "'BUYER_REQUEST_REVIEWED'"
)


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def timestamp(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def fk(name, target, primary_key=False):
    return sa.Column(
        name,
        sa.Uuid(),
        sa.ForeignKey(target, ondelete="RESTRICT"),
        primary_key=primary_key,
        nullable=False,
    )


def upgrade():
    # SQLite cannot ALTER CHECK constraints. Offline PostgreSQL uses regular ALTER.
    with op.batch_alter_table("delivery_events") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint("ck_events_type", f"event_type IN ({EVENTS})")
    op.create_table(
        "confirmation_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        fk("order_id", "orders.id"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("phone_binding", sa.String(64), nullable=False),
        timestamp("expires_at", False),
        timestamp("delivered_view_until"),
        timestamp("revoked_at"),
        timestamp("locked_at"),
        timestamp("verified_at"),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.Integer(), nullable=False),
        timestamp("created_at", False),
        sa.CheckConstraint("failed_attempts BETWEEN 0 AND 3", name="ck_link_attempts"),
        sa.CheckConstraint("generation >= 0 AND nonce >= 0", name="ck_link_counters"),
    )
    op.create_index("ix_confirmation_order", "confirmation_links", ["order_id"])
    op.create_table(
        "buyer_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        fk("link_id", "confirmation_links.id"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        timestamp("expires_at", False),
        timestamp("created_at", False),
    )
    op.create_index("ix_buyer_sessions_link_id", "buyer_sessions", ["link_id"])
    op.create_table(
        "location_references",
        fk("order_id", "orders.id", True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("township", sa.String(128), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        fk("actor_id", "users.id"),
        timestamp("created_at", False),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
            name="ck_reference_coordinates",
        ),
    )
    op.create_table(
        "buyer_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        fk("order_id", "orders.id"),
        fk("link_id", "confirmation_links.id"),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("reason_codes", json_type(), nullable=False),
        sa.Column("previous_values", json_type(), nullable=False),
        sa.Column("submitted_values", json_type(), nullable=False),
        sa.Column("resolution", sa.String(16)),
        sa.Column("resolution_reason", sa.String(500)),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        timestamp("resolved_at"),
        timestamp("created_at", False),
        sa.CheckConstraint("kind IN ('LOCATION','RESPONSE')", name="ck_buyer_request_kind"),
        sa.CheckConstraint("decision IN ('APPLIED','REVIEW_REQUIRED')", name="ck_buyer_decision"),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('APPROVE','REJECT')", name="ck_buyer_resolution"
        ),
    )
    op.create_index("ix_buyer_request_order", "buyer_requests", ["order_id", "created_at", "id"])
    op.create_index(
        "ux_buyer_request_retry", "buyer_requests", ["link_id", "request_id"], unique=True
    )
    op.create_table(
        "buyer_rate_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        timestamp("expires_at", False),
    )
    op.create_index("ix_buyer_rate_limits_expires_at", "buyer_rate_limits", ["expires_at"])


def downgrade():
    for table in (
        "buyer_rate_limits",
        "buyer_requests",
        "location_references",
        "buyer_sessions",
        "confirmation_links",
    ):
        op.drop_table(table)
    with op.batch_alter_table("delivery_events") as batch:
        batch.drop_constraint("ck_events_type", type_="check")
        batch.create_check_constraint(
            "ck_events_type", "event_type IN ('ORDER_CREATED','ORDER_CORRECTED','STATUS_CHANGED')"
        )
