"""Application configuration — env-only.

All secrets come from environment variables. Nothing in this module ever reads
a credential off disk or from a remote service.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Sentinel default for the API-key pepper. Any deployment running with this
# value is unsafe and must be refused by tooling that mints keys at rest.
DEFAULT_PEPPER_SENTINEL = "local-dev-pepper-change-me"

# Minimum required pepper length, in characters. Mirrors the entropy emitted
# by ``secrets.token_urlsafe(24)`` (32+ chars) — a conservative floor.
MIN_PEPPER_LENGTH = 24

# Sentinel default for the user-login JWT signing secret. Any deployment that
# mints user tokens while still on this value is unsafe; security tooling warns.
DEFAULT_JWT_SENTINEL = "local-dev-jwt-secret-change-me"
MIN_JWT_SECRET_LENGTH = 24


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
    # Resilience: the Render dashboard has historically been set with the var
    # named STRIPE_SECRET_KEY. If STRIPE_API_KEY is blank, fall back to it (see
    # the ``_stripe_key_fallback`` validator) so billing can't silently break on
    # the naming mismatch.
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    # The Desk Payment Link URL (set to the LIVE link in production). The terminal
    # appends ``?client_reference_id=<user_id>`` so the webhook can entitle the user.
    stripe_payment_link_desk: str = Field(default="", alias="STRIPE_PAYMENT_LINK_DESK")
    # Plan to grant when a checkout arrives without explicit ``metadata.plan``. This
    # deployment is the Desk terminal, so the safe default is ``desk`` — a paid
    # checkout entitles the terminal even if the Payment Link metadata didn't carry it.
    stripe_default_plan: str = Field(default="desk", alias="STRIPE_DEFAULT_PLAN")

    # ── user sign-in (JWT) — paid CBSRM Desk terminal ──
    # Signs the access/refresh tokens issued at login. MUST be rotated off the
    # sentinel before serving real customers (see ``DEFAULT_JWT_SENTINEL``).
    jwt_secret: str = Field(
        default="local-dev-jwt-secret-change-me", alias="WAVERVANIR_JWT_SECRET"
    )
    access_token_ttl_min: int = Field(default=15, alias="WAVERVANIR_ACCESS_TTL_MIN")
    refresh_token_ttl_days: int = Field(default=7, alias="WAVERVANIR_REFRESH_TTL_DAYS")

    # ── owner/admin accounts ──
    # Comma-separated emails granted full admin (all functions) on sign-up/login.
    # The owner registers this email with a password of their choosing; the code
    # never needs the password value — it grants admin by matching the email.
    admin_emails: str = Field(
        default="prabhawa@wavervanir.com", alias="WAVERVANIR_ADMIN_EMAILS"
    )

    # ── data-provider env (all OPTIONAL — providers self-disable when blank) ──
    bullflow_api_key: str = Field(default="", alias="BULLFLOW_API_KEY")
    bullflow_data_file: str = Field(default="", alias="BULLFLOW_DATA_FILE")
    financialdata_api_key: str = Field(default="", alias="FINANCIALDATA_API_KEY")
    # Passed through to cbsrm's FRED-backed lenses. Captured here (not just
    # os.environ) so /health/ready can report whether the key is configured.
    fred_api_key: str = Field(default="", alias="FRED_API_KEY")

    # ── hardening / observability ──
    # Security-response-headers middleware master switch (see middleware.py).
    security_headers_enabled: bool = Field(
        default=True, alias="WAVERVANIR_SECURITY_HEADERS"
    )
    # HSTS only makes sense over HTTPS; gated so local http dev isn't broken.
    # render.yaml sets this true for the deployed (TLS-fronted) service.
    hsts_enabled: bool = Field(default=False, alias="WAVERVANIR_HSTS_ENABLED")
    # Optional ops alert webhook (Slack/Discord/generic). Blank = disabled.
    alert_webhook_url: str = Field(default="", alias="ALERT_WEBHOOK_URL")
    log_level: str = Field(default="INFO", alias="WAVERVANIR_LOG_LEVEL")

    @model_validator(mode="after")
    def _stripe_key_fallback(self) -> "Settings":
        if not self.stripe_api_key and self.stripe_secret_key:
            self.stripe_api_key = self.stripe_secret_key
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Tests reset via ``get_settings.cache_clear()``."""
    return Settings()


def admin_email_set(settings: Settings) -> set[str]:
    """Normalised set of owner/admin emails from ``settings.admin_emails``."""
    return {
        e.strip().lower()
        for e in (settings.admin_emails or "").split(",")
        if e.strip()
    }


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
