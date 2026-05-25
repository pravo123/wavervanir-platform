"""Bearer-token authentication.

Tokens issued at Stripe-checkout time. We never store the raw token — only
its peppered HMAC-SHA256 hash. The server-side pepper is loaded from env.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from wavervanir_api.config import Settings, get_settings
from wavervanir_api.db import ApiKey, get_engine


# ── token helpers ───────────────────────────────────────────────────────────


def generate_raw_token() -> str:
    """Return a fresh URL-safe random token (the only time it exists in plaintext)."""
    return "wvk_" + secrets.token_urlsafe(32)


def hash_token(raw_token: str, pepper: str) -> str:
    """Peppered HMAC-SHA256 over the raw token. Deterministic for lookup."""
    if not raw_token:
        raise ValueError("raw_token is empty")
    return hmac.new(
        pepper.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── auth context dataclass ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AuthContext:
    """Resolved caller identity attached to authenticated requests."""

    key_id: int
    tier: str   # "free" | "paid" — legacy coarse axis
    plan: str   # "free"|"researcher"|"pro"|"institutional"|"regulator"
    stripe_customer_id: Optional[str]
    custom_daily_cap: Optional[int] = None


# ── FastAPI dependency ──────────────────────────────────────────────────────


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """FastAPI dependency: resolve the bearer token to an active API key row."""
    raw = _extract_bearer(authorization)
    digest = hash_token(raw, settings.api_key_pepper)

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(select(ApiKey).where(ApiKey.key_hash == digest)).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unknown api key",
            )
        if row.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"api key {row.status}",
            )
        return AuthContext(
            key_id=row.id or 0,
            tier=row.tier,
            plan=row.plan,
            stripe_customer_id=row.stripe_customer_id,
            custom_daily_cap=row.custom_daily_cap,
        )


# ── provisioning helpers (used by Stripe webhook + tests) ──────────────────


def provision_key(
    raw_token: str,
    tier: str,
    stripe_customer_id: Optional[str],
    settings: Settings,
    *,
    plan: str = "free",
    stripe_subscription_id: Optional[str] = None,
    custom_daily_cap: Optional[int] = None,
) -> ApiKey:
    """Insert (or re-activate) an API key row keyed by the token hash.

    ``plan`` is the canonical billing-quota dimension (see ``plans.py``).
    ``tier`` is preserved for backwards compatibility with earlier callers.
    """
    digest = hash_token(raw_token, settings.api_key_pepper)
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        existing = session.exec(select(ApiKey).where(ApiKey.key_hash == digest)).first()
        if existing:
            existing.tier = tier
            existing.plan = plan
            existing.status = "active"
            existing.stripe_customer_id = stripe_customer_id or existing.stripe_customer_id
            if stripe_subscription_id:
                existing.stripe_subscription_id = stripe_subscription_id
            if custom_daily_cap is not None:
                existing.custom_daily_cap = custom_daily_cap
            existing.revoked_at = None
            existing.grace_until = None
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        row = ApiKey(
            key_hash=digest,
            tier=tier,
            plan=plan,
            status="active",
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            custom_daily_cap=custom_daily_cap,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def update_key_plan_by_subscription(
    *,
    stripe_subscription_id: str,
    plan: str,
    settings: Settings,
) -> int:
    """For ``customer.subscription.updated`` plan-change events. Returns row count."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(
            select(ApiKey).where(
                ApiKey.stripe_subscription_id == stripe_subscription_id,
            )
        ).all()
        for r in rows:
            r.plan = plan
            session.add(r)
        session.commit()
        return len(rows)


def mark_grace_by_subscription(
    *,
    stripe_subscription_id: str,
    grace_until: datetime,
    settings: Settings,
) -> int:
    """For ``invoice.payment_failed``. Sets a grace deadline; key stays active."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(
            select(ApiKey).where(
                ApiKey.stripe_subscription_id == stripe_subscription_id,
                ApiKey.status == "active",
            )
        ).all()
        for r in rows:
            r.grace_until = grace_until
            session.add(r)
        session.commit()
        return len(rows)


def revoke_key_by_stripe_customer(stripe_customer_id: str, settings: Settings) -> int:
    """Revoke every active key tied to the given Stripe customer. Returns count."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(
            select(ApiKey).where(
                ApiKey.stripe_customer_id == stripe_customer_id,
                ApiKey.status == "active",
            )
        ).all()
        count = 0
        for r in rows:
            r.status = "revoked"
            r.revoked_at = datetime.now(timezone.utc)
            session.add(r)
            count += 1
        session.commit()
        return count
