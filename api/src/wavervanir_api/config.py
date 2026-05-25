"""Application configuration — env-only.

All secrets come from environment variables. Nothing in this module ever reads
a credential off disk or from a remote service.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings, populated from env (and optionally from .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="dev", alias="WAVERVANIR_ENV")
    db_url: str = Field(
        default="sqlite:///./wavervanir_api.sqlite", alias="WAVERVANIR_DB_URL"
    )
    api_key_pepper: str = Field(
        default="local-dev-pepper-change-me", alias="WAVERVANIR_API_KEY_PEPPER"
    )

    rate_limit_free: int = Field(default=100, alias="WAVERVANIR_RATE_LIMIT_FREE")
    rate_limit_paid: int = Field(default=5000, alias="WAVERVANIR_RATE_LIMIT_PAID")

    stripe_api_key: str = Field(default="", alias="STRIPE_API_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Tests reset via ``get_settings.cache_clear()``."""
    return Settings()
