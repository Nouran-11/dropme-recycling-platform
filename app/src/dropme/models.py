import enum
import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MaterialType(str, enum.Enum):
    PET = "PET"
    ALU = "ALU"
    GLASS = "GLASS"
    HDPE = "HDPE"
    OTHER = "OTHER"


class EventStatus(str, enum.Enum):
    received = "received"
    processing = "processing"
    processed = "processed"
    failed = "failed"


# create_type=False: the migration owns type creation/teardown so upgrade and
# downgrade are symmetric; metadata operations must not race it.
material_type_enum = sa.Enum(
    MaterialType,
    name="material_type",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)
event_status_enum = sa.Enum(
    EventStatus,
    name="event_status",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    machine_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    material_type: Mapped[MaterialType] = mapped_column(material_type_enum, nullable=False)
    item_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        event_status_enum,
        nullable=False,
        server_default=sa.text("'received'"),
    )
    estimated_weight_g: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2))
    processed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        sa.CheckConstraint(
            "length(trim(machine_id)) BETWEEN 1 AND 64",
            name="ck_events_machine_id_len",
        ),
        sa.CheckConstraint(
            "item_count > 0 AND item_count <= 10000",
            name="ck_events_item_count_range",
        ),
        sa.Index("idx_events_status_created", "status", "created_at"),
        sa.Index("idx_events_machine_time", "machine_id", sa.text("event_timestamp DESC")),
    )
