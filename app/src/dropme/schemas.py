from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dropme.models import EventStatus, MaterialType

MAX_FUTURE_SKEW = timedelta(hours=24)


class EventCreate(BaseModel):
    machine_id: str
    material_type: MaterialType
    item_count: int = Field(ge=1, le=10000)
    event_timestamp: datetime

    @field_validator("machine_id")
    @classmethod
    def _machine_id_trimmed_length(cls, v: str) -> str:
        # Mirror the DB CHECK on length(trim(...)) BETWEEN 1 AND 64 so a blank
        # or oversized id is a clean 422 at the edge, not a 500 from the backstop.
        v = v.strip()
        if not (1 <= len(v) <= 64):
            raise ValueError("machine_id length after trimming must be between 1 and 64")
        return v

    @field_validator("event_timestamp")
    @classmethod
    def _tz_aware_not_far_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("event_timestamp must be timezone-aware (ISO-8601 with offset)")
        if v > datetime.now(UTC) + MAX_FUTURE_SKEW:
            raise ValueError("event_timestamp must not be more than 24h in the future")
        return v


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    machine_id: str
    material_type: MaterialType
    item_count: int
    event_timestamp: datetime
    status: EventStatus
    estimated_weight_g: Decimal | None
    processed_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
