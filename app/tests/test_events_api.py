from datetime import UTC, datetime

from dropme.models import Event, EventStatus, MaterialType

NOW = datetime.now(UTC)


def _valid_body(**overrides):
    body = {
        "machine_id": "machine-1",
        "material_type": "PET",
        "item_count": 5,
        "event_timestamp": NOW.isoformat(),
    }
    body.update(overrides)
    return body


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


def test_create_returns_201_with_location(client, clean_db, api_key):
    resp = client.post("/events", headers={"X-API-Key": api_key}, json=_valid_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "received"
    assert body["machine_id"] == "machine-1"
    assert resp.headers["Location"] == f"/events/{body['id']}"


def test_create_without_api_key_returns_401(client, clean_db):
    resp = client.post("/events", json=_valid_body())
    assert resp.status_code == 401


def test_create_with_wrong_api_key_returns_401(client, clean_db):
    resp = client.post("/events", headers={"X-API-Key": "nope"}, json=_valid_body())
    assert resp.status_code == 401


def test_list_pagination(client, clean_db, session):
    for i in range(5):
        _insert(session, machine_id=f"m-{i}")
    first = client.get("/events?limit=2&offset=0").json()
    second = client.get("/events?limit=2&offset=2").json()
    assert len(first) == 2
    assert len(second) == 2
    assert {e["id"] for e in first}.isdisjoint({e["id"] for e in second})


def test_list_filter_by_status_and_machine(client, clean_db, session):
    _insert(session, machine_id="kiosk-a", status=EventStatus.processed)
    _insert(session, machine_id="kiosk-a", status=EventStatus.received)
    _insert(session, machine_id="kiosk-b", status=EventStatus.processed)

    processed = client.get("/events?status=processed").json()
    assert len(processed) == 2
    assert all(e["status"] == "processed" for e in processed)

    kiosk_a = client.get("/events?machine_id=kiosk-a").json()
    assert len(kiosk_a) == 2
    assert all(e["machine_id"] == "kiosk-a" for e in kiosk_a)


def test_limit_over_cap_returns_422(client, clean_db):
    assert client.get("/events?limit=300").status_code == 422


def test_get_by_id_returns_200(client, clean_db, session):
    event = _insert(session)
    resp = client.get(f"/events/{event.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(event.id)


def test_unknown_id_returns_404(client, clean_db):
    resp = client.get("/events/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_malformed_uuid_returns_422(client, clean_db):
    resp = client.get("/events/not-a-uuid")
    assert resp.status_code == 422
