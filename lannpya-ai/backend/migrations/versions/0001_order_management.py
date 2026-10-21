"""Initial users, orders, and delivery history. No user data is seeded by migrations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_order_management"
down_revision = None
branch_labels = None
depends_on = None

STATUSES = (
    "DRAFT",
    "NEEDS_REVIEW",
    "AWAITING_CONFIRMATION",
    "CONFIRMED",
    "READY_FOR_DISPATCH",
    "ASSIGNED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "FAILED",
    "CANCELLED",
)


def status_type(name):
    return sa.Enum(*STATUSES, name=name, native_enum=False, create_constraint=True)


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def timestamps():
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    ]


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column(
            "role",
            sa.Enum(
                "Merchant",
                "Dispatcher",
                "Rider",
                "Admin",
                name="user_role",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 200", name="ck_users_name_length"),
        sa.CheckConstraint("length(email) BETWEEN 3 AND 254", name="ck_users_email_length"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "merchant_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("customer_name", sa.String(200)),
        sa.Column("customer_phone", sa.String(32)),
        sa.Column("original_message", sa.Text()),
        sa.Column("normalized_message", sa.Text()),
        sa.Column("township", sa.String(128)),
        sa.Column("street", sa.String(1000)),
        sa.Column("landmark", sa.String(1000)),
        sa.Column("building", sa.String(500)),
        sa.Column("floor", sa.String(100)),
        sa.Column("unit", sa.String(100)),
        sa.Column("building_floor_unit", sa.String(2000)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("cod_amount", sa.Numeric(12, 0)),
        sa.Column("delivery_instructions", sa.String(2000)),
        sa.Column("delivery_time_window", sa.String(500)),
        sa.Column(
            "confidence_level",
            sa.Enum(
                "GREEN",
                "AMBER",
                "RED",
                name="confidence_level",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("confidence_reasons", json_type(), nullable=False),
        sa.Column("parsing_mode", sa.String(16), nullable=False),
        sa.Column("ai_availability_status", sa.String(32), nullable=False),
        sa.Column("field_sources", json_type(), nullable=False),
        sa.Column("parsing_metadata", json_type(), nullable=False),
        sa.Column("manual_review_required", sa.Boolean(), nullable=False),
        sa.Column("status", status_type("order_status"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "cod_amount IS NULL OR (cod_amount >= 0 AND cod_amount <= 1000000000 "
            "AND cod_amount = CAST(cod_amount AS BIGINT))",
            name="ck_orders_cod",
        ),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL "
            "AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 "
            "AND longitude BETWEEN -180 AND 180)",
            name="ck_orders_coordinates",
        ),
        sa.CheckConstraint("version >= 1", name="ck_orders_version"),
        sa.CheckConstraint(
            "parsing_mode IN ('rules','hybrid','structured')", name="ck_orders_mode"
        ),
        sa.CheckConstraint(
            "ai_availability_status IN ('not_requested','mock','disabled','available',"
            "'timeout','rate_limited','invalid_response','unavailable','privacy_blocked')",
            name="ck_orders_ai_status",
        ),
        sa.CheckConstraint(
            "original_message IS NULL OR length(original_message) <= 10000",
            name="ck_orders_original_length",
        ),
    )
    op.create_index("ix_orders_merchant_created", "orders", ["merchant_id", "created_at", "id"])
    op.create_index("ix_orders_status_confidence", "orders", ["status", "confidence_level"])
    op.create_table(
        "delivery_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("previous_status", status_type("event_previous_status")),
        sa.Column("new_status", status_type("event_new_status"), nullable=False),
        sa.Column("metadata", json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "event_type IN ('ORDER_CREATED','ORDER_CORRECTED','STATUS_CHANGED')",
            name="ck_events_type",
        ),
    )
    op.create_index("ix_events_order_created", "delivery_events", ["order_id", "created_at", "id"])


def downgrade():
    op.drop_table("delivery_events")
    op.drop_table("orders")
    op.drop_table("users")
