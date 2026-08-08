from datetime import UTC, datetime, timedelta

import pytest

NOW = datetime.now(UTC)


def _payload(**overrides):
    base = {
        "machine_id": "machine-1",
        "material_type": "PET",
        "item_count": 5,
        "event_timestamp": NOW.isoformat(),
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "override",
    [
        {"material_type": "WOOD"},
        {"item_count": 0},
        {"item_count": -3},
        {"item_count": 10001},
        {"machine_id": "   "},
        {"event_timestamp": "2026-08-08T10:00:00"},  # naive
        {"event_timestamp": (NOW + timedelta(hours=25)).isoformat()},  # >24h future
    ],
    ids=[
        "bad-enum",
        "zero-count",
        "negative-count",
        "over-count",
        "blank-machine",
        "naive-ts",
        "future-ts",
    ],
)
def test_invalid_payload_returns_422(client, clean_db, api_key, override):
    resp = client.post("/events", headers={"X-API-Key": api_key}, json=_payload(**override))
    assert resp.status_code == 422


def test_missing_field_returns_422(client, clean_db, api_key):
    body = _payload()
    del body["item_count"]
    resp = client.post("/events", headers={"X-API-Key": api_key}, json=body)
    assert resp.status_code == 422
