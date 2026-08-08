import os

# Must run before any dropme import: config.py and db.py read settings and build
# the engine at import time.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/dropme_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("VERSION", "0.0.0-test")
os.environ.setdefault("GIT_SHA", "testsha")
os.environ.setdefault("BUILT_AT", "2026-01-01T00:00:00Z")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from dropme.db import SessionLocal, engine  # noqa: E402
from dropme.main import app  # noqa: E402

APP_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(APP_DIR / "migrations"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _schema():
    command.upgrade(alembic_config(), "head")
    yield


@pytest.fixture
def alembic_cfg():
    return alembic_config()


@pytest.fixture
def api_key():
    return os.environ["API_KEY"]


@pytest.fixture
def clean_db():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE events"))
    yield


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
