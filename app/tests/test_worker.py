from datetime import UTC, datetime
from decimal import Decimal

import pytest

import dropme.worker as worker
from dropme.models import Event, EventStatus, MaterialType

NOW = datetime.now(UTC)


def _insert(session, **kwargs):
    defaults = dict(
        machine_id="m",
        material_type=MaterialType.PET,
        item_count=1,
        event_timestamp=NOW,
        status=EventStatus.received,
    )
    defaults.update(kwargs)
    event = Event(**defaults)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@pytest.mark.parametrize(
    ("material", "per_item"),
    [
        (MaterialType.PET, Decimal("18")),
        (MaterialType.ALU, Decimal("15")),
        (MaterialType.GLASS, Decimal("300")),
        (MaterialType.HDPE, Decimal("40")),
        (MaterialType.OTHER, Decimal("25")),
    ],
)
def test_weight_per_material(clean_db, session, material, per_item):
    event = _insert(session, material_type=material, item_count=3)
    worker.process_event(str(event.id))
    session.refresh(event)
    assert event.status == EventStatus.processed
    assert event.estimated_weight_g == per_item * 3
    assert event.processed_at is not None


def test_idempotent_rerun(clean_db, session):
    event = _insert(session)
    worker.process_event(str(event.id))
    session.refresh(event)
    first_processed_at = event.processed_at

    worker.process_event(str(event.id))
    session.refresh(event)
    assert event.status == EventStatus.processed
    assert event.processed_at == first_processed_at


def test_failure_sets_failed_and_reraises(clean_db, session, monkeypatch):
    event = _insert(session)
    monkeypatch.setattr(worker, "GRAMS_PER_ITEM", {})  # force KeyError inside try
    with pytest.raises(KeyError):
        worker.process_event(str(event.id))
    session.refresh(event)
    assert event.status == EventStatus.failed
    assert event.failure_reason
