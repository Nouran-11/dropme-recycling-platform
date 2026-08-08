from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # No defaults: a missing value raises at startup instead of booting a
    # half-configured process that fails later on the first request.
    database_url: str
    redis_url: str
    api_key: str

    version: str = "0.0.0-dev"
    git_sha: str = "unknown"
    built_at: str = "unknown"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
