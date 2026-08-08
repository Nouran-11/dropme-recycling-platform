"""initial events table

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

material_type = postgresql.ENUM(
    "PET", "ALU", "GLASS", "HDPE", "OTHER", name="material_type", create_type=False
)
event_status = postgresql.ENUM(
    "received", "processing", "processed", "failed", name="event_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    material_type.create(bind, checkfirst=False)
    event_status.create(bind, checkfirst=False)

    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("machine_id", sa.Text(), nullable=False),
        sa.Column("material_type", material_type, nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", event_status, server_default=sa.text("'received'"), nullable=False),
        sa.Column("estimated_weight_g", sa.Numeric(10, 2), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(trim(machine_id)) BETWEEN 1 AND 64", name="ck_events_machine_id_len"
        ),
        sa.CheckConstraint(
            "item_count > 0 AND item_count <= 10000", name="ck_events_item_count_range"
        ),
    )
    op.create_index("idx_events_status_created", "events", ["status", "created_at"])
    op.execute("CREATE INDEX idx_events_machine_time ON events (machine_id, event_timestamp DESC)")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_events_updated_at
        BEFORE UPDATE ON events
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_events_updated_at ON events")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.drop_index("idx_events_machine_time", table_name="events")
    op.drop_index("idx_events_status_created", table_name="events")
    op.drop_table("events")
    event_status.drop(op.get_bind(), checkfirst=False)
    material_type.drop(op.get_bind(), checkfirst=False)
