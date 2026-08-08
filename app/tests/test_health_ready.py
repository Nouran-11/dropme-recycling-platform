import dropme.main as main


def _boom(*args, **kwargs):
    raise RuntimeError("dependency down")


def test_health_200_even_with_db_down(client, monkeypatch):
    # /health must never touch the database.
    monkeypatch.setattr(main.engine, "connect", _boom)
    assert client.get("/health").status_code == 200


def test_ready_503_with_redis_down(client, monkeypatch):
    monkeypatch.setattr(main.redis_conn, "ping", _boom)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["failed"] == ["redis"]


def test_ready_503_with_db_down_names_postgres(client, monkeypatch):
    monkeypatch.setattr(main.engine, "connect", _boom)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert "postgres" in resp.json()["failed"]
