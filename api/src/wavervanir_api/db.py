"""Database layer — SQLite (dev) / Postgres (prod) via SQLModel.

Schema is intentionally minimal for the MVP slice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlmodel import Field, Session, SQLModel, create_engine


# ── models ──────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiKey(SQLModel, table=True):
    """A bearer token issued to a customer.

    We never store the raw token. Only its hash (HMAC-SHA256 with the server
    pepper) is persisted.

    ``plan`` is the canonical billing/quota dimension (see ``plans.py``).
    ``tier`` is retained for backwards compatibility with earlier rows / tests
    and mirrors a coarse paid/free classification.
    """

    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    tier: str = Field(default="free")  # "free" | "paid" — legacy coarse axis
    plan: str = Field(default="free", index=True)  # "free"|"researcher"|"pro"|"institutional"|"regulator"
    status: str = Field(default="active")  # "active" | "revoked"
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
    custom_daily_cap: Optional[int] = Field(default=None)  # manual override for institutional / regulator
    created_at: datetime = Field(default_factory=_utcnow)
    disclosed_at: Optional[datetime] = Field(default=None)  # set when raw key is shown via /onboard
    grace_until: Optional[datetime] = Field(default=None)  # set on invoice.payment_failed
    revoked_at: Optional[datetime] = Field(default=None)


class AuditLog(SQLModel, table=True):
    """One row per authenticated request. Stores hashes, never raw payloads."""

    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_id: Optional[int] = Field(default=None, index=True)
    route: str = Field(index=True)
    request_sha256: str = Field(default="")
    response_sha256: str = Field(default="")
    status_code: int = Field(default=0)
    latency_ms: int = Field(default=0)
    ts: datetime = Field(default_factory=_utcnow, index=True)


class OnboardSession(SQLModel, table=True):
    """Maps Stripe checkout session id → freshly-minted raw API key.

    The raw token is stored here transiently so it can be retrieved exactly
    once via ``GET /onboard?session_id=…``. On disclosure the row's
    ``disclosed_at`` is set and subsequent fetches are refused (410 Gone).

    This is the ONLY place the raw token ever lives at rest — and only
    until the customer's first onboard hit.
    """

    __tablename__ = "onboard_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    stripe_session_id: str = Field(index=True, unique=True)
    api_key_id: int = Field(index=True)
    raw_token: Optional[str] = Field(default=None)  # cleared after disclosure
    plan: str = Field(default="free")
    created_at: datetime = Field(default_factory=_utcnow)
    disclosed_at: Optional[datetime] = Field(default=None)


class WaitlistEntry(SQLModel, table=True):
    """One row per public waitlist submission."""

    __tablename__ = "waitlist"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    tier_interest: str = Field(default="researcher")
    source: str = Field(default="landing")
    created_at: datetime = Field(default_factory=_utcnow)


class User(SQLModel, table=True):
    """A paying-customer login for the CBSRM Desk terminal.

    Distinct from :class:`ApiKey` (which is a programmatic bearer token minted at
    Stripe checkout). A ``User`` is an interactive account: email + a hashed
    password, plus an *entitlement* (``plan`` + ``status``) that the Stripe
    webhook keeps in sync with the customer's subscription.

    We never store the raw password — only a self-describing, salted hash (see
    ``security.hash_password``). ``is_active`` gates the account itself; ``plan``
    + ``status`` gate access to premium Desk routes (default-deny).
    """

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    name: str = Field(default="")
    # Entitlement (kept in sync by the Stripe webhook). ``desk`` == paid terminal.
    plan: str = Field(default="free", index=True)
    status: str = Field(default="inactive", index=True)  # "active"|"inactive"|"revoked"|"grace"
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
    grace_until: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)  # account enabled (independent of subscription)
    created_at: datetime = Field(default_factory=_utcnow)
    last_login_at: Optional[datetime] = Field(default=None)


class AccessEvent(SQLModel, table=True):
    """Tamper-evident, hash-linked ledger of sign-ins and premium accesses.

    Each row chains to the previous one: ``entry_hash`` = SHA-256 over
    (prev_hash || ts || subject || kind || route || payload_sha256). Re-hashing
    the chain top-to-bottom must reproduce every stored hash, otherwise a row
    was altered, deleted, or inserted out of band. Payloads are hashed, never
    stored raw, so the ledger holds no PII.

    Unlike ``cbsrm.audit.chain`` (SQLite-only), this lives on the SQLModel engine
    so it is identical on SQLite (dev) and Postgres (prod). This is the
    "every access is auditable" property the Desk sells to institutions.
    """

    __tablename__ = "access_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=_utcnow, index=True)
    subject: str = Field(index=True)  # e.g. "user:42" or "user:anon"
    kind: str = Field(index=True)     # REGISTERED|SIGNIN|SIGNIN_FAILED|TOKEN_REFRESH|ACCESS_GRANTED|ACCESS_DENIED
    route: str = Field(default="")
    payload_sha256: str = Field(default="")
    prev_hash: Optional[str] = Field(default=None)
    entry_hash: str = Field(default="", index=True)


# ── engine / session ────────────────────────────────────────────────────────

_engine = None


def get_engine(db_url: str):
    """Get (and lazily build) the process-wide engine.

    Re-called with a different URL (e.g. by tests) rebuilds.
    """
    global _engine
    if _engine is None or str(_engine.url) != db_url:
        connect_args = (
            {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        )
        _engine = create_engine(db_url, connect_args=connect_args, echo=False)
        SQLModel.metadata.create_all(_engine)
    return _engine


def get_session(db_url: str) -> Iterator[Session]:
    engine = get_engine(db_url)
    with Session(engine) as session:
        yield session


def reset_engine() -> None:
    """Test helper — drop the cached engine so the next call rebuilds."""
    global _engine
    _engine = None
