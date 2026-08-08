from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from dropme.config import get_settings

_settings = get_settings()

# pool_pre_ping issues a cheap SELECT 1 on checkout so a connection severed by
# a Postgres restart or idle timeout is discarded and replaced, not handed to a
# request as a dead socket. pool_recycle caps connection age below typical
# server/proxy idle limits.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
