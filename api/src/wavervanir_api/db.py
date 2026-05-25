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
    """

    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    tier: str = Field(default="free")  # "free" | "paid"
    status: str = Field(default="active")  # "active" | "revoked"
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
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


class WaitlistEntry(SQLModel, table=True):
    """One row per public waitlist submission."""

    __tablename__ = "waitlist"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    tier_interest: str = Field(default="researcher")
    source: str = Field(default="landing")
    created_at: datetime = Field(default_factory=_utcnow)


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
