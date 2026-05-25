"""Application configuration — env-only.

All secrets come from environment variables. Nothing in this module ever reads
a credential off disk or from a remote service.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Sentinel default for the API-key pepper. Any deployment running with this
# value is unsafe and must be refused by tooling that mints keys at rest.
DEFAULT_PEPPER_SENTINEL = "local-dev-pepper-change-me"

# Minimum required pepper length, in characters. Mirrors the entropy emitted
# by ``secrets.token_urlsafe(24)`` (32+ chars) — a conservative floor.
MIN_PEPPER_LENGTH = 24


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

    # ── data-provider env (all OPTIONAL — providers self-disable when blank) ──
    fmp_api_key: str = Field(default="", alias="FMP_API_KEY")
    bullflow_api_key: str = Field(default="", alias="BULLFLOW_API_KEY")
    bullflow_data_file: str = Field(default="", alias="BULLFLOW_DATA_FILE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Tests reset via ``get_settings.cache_clear()``."""
    return Settings()


@dataclass(frozen=True)
class StagingGuardResult:
    ok: bool
    reason: str | None = None


def staging_guard(settings: Settings) -> StagingGuardResult:
    """Sanity checks for ops tooling that mints credentials at rest.

    Returns ``StagingGuardResult(ok=True, reason=None)`` when it is safe to mint
    a bearer token against this Settings instance. Otherwise returns
    ``ok=False`` with a short human reason.

    This is intentionally NOT called from the request hot path — it is a check
    for ops tooling (e.g. ``wavervanir_api.tools.bootstrap_key``) that
    short-circuits common foot-guns: a default pepper, a missing pepper, or
    a run against ``WAVERVANIR_ENV=prod``.
    """
    env = (settings.env or "").strip().lower()
    if env == "prod":
        return StagingGuardResult(
            ok=False,
            reason="refusing to mint credentials with WAVERVANIR_ENV=prod",
        )

    pepper = settings.api_key_pepper or ""
    if not pepper:
        return StagingGuardResult(
            ok=False,
            reason="WAVERVANIR_API_KEY_PEPPER is empty",
        )
    if pepper == DEFAULT_PEPPER_SENTINEL:
        return StagingGuardResult(
            ok=False,
            reason=(
                "WAVERVANIR_API_KEY_PEPPER is the default sentinel value; "
                "rotate before minting keys at rest"
            ),
        )
    if len(pepper) < MIN_PEPPER_LENGTH:
        return StagingGuardResult(
            ok=False,
            reason=(
                f"WAVERVANIR_API_KEY_PEPPER is too short "
                f"(have {len(pepper)} chars, need ≥ {MIN_PEPPER_LENGTH})"
            ),
        )
    return StagingGuardResult(ok=True, reason=None)
