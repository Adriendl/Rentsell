"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://justeprix:justeprix@localhost:5432/justeprix"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Object storage (S3-compatible) — leave bucket empty to skip mirroring
    storage_endpoint: str = ""
    storage_bucket: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_public_base_url: str = ""

    # Scraper delays (seconds)
    min_delay: float = 1.5
    max_delay: float = 3.0

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
