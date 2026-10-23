"""Last reported delivery GPS, separate from operational order versions."""

import sqlalchemy as sa
from alembic import op

revision = "0009_delivery_positions"
down_revision = "0008_buyer_edit_policy"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "delivery_positions",
        sa.Column(
            "assignment_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_assignments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.delivery_positions ENABLE ROW LEVEL SECURITY")
        # Supabase defaults may grant new public tables to browser roles.
        op.execute("REVOKE ALL ON public.delivery_positions FROM PUBLIC")
        op.execute("""DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN
            REVOKE ALL ON public.delivery_positions FROM anon;
          END IF;
          IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN
            REVOKE ALL ON public.delivery_positions FROM authenticated;
          END IF;
        END $$""")


def downgrade():
    op.drop_table("delivery_positions")
