"""Per-API-key calendar-day rate limit.

MVP implementation: in-process counters keyed by (key_id, utc_date).
Production swap-in: Redis INCR + EXPIRE on the same key, identical Protocol.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from threading import Lock
from typing import Dict, Tuple

from fastapi import Depends, HTTPException, status

from wavervanir_api.auth import AuthContext, require_api_key
from wavervanir_api.config import Settings, get_settings
from wavervanir_api.plans import daily_cap_for, is_known_plan


_LOCK = Lock()
_COUNTERS: Dict[Tuple[int, date], int] = defaultdict(int)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _limit_for(auth: AuthContext, settings: Settings) -> int:
    """Resolve the daily cap from the plan catalog, with env overrides for free/paid.

    Resolution order:
      1. Unknown plan → degrade to ``settings.rate_limit_free``.
      2. Legacy callers (``plan='free'`` but ``tier='paid'``) → ``settings.rate_limit_paid``.
      3. ``plan='free'`` → ``settings.rate_limit_free``.
      4. Paid plans → per-plan catalog cap, *clamped down* by env override if
         the env value is lower (so tests can squeeze caps without ever
         silently raising prod caps).
    """
    if not is_known_plan(auth.plan):
        return settings.rate_limit_free

    if auth.plan == "free" and auth.tier == "paid":
        # Backwards-compat path for callers that set tier without plan.
        return settings.rate_limit_paid

    if auth.plan == "free":
        return settings.rate_limit_free

    catalog_cap = daily_cap_for(auth.plan, custom_daily_cap=auth.custom_daily_cap)
    if settings.rate_limit_paid and settings.rate_limit_paid < catalog_cap:
        return settings.rate_limit_paid
    return catalog_cap


def reset_counters() -> None:
    """Test helper — clear all in-process counters."""
    with _LOCK:
        _COUNTERS.clear()


def consume(auth: AuthContext, settings: Settings) -> Tuple[int, int]:
    """Increment caller's counter for today. Raises 429 if the cap is hit.

    Returns (current_count, daily_limit).
    """
    today = _today_utc()
    limit = _limit_for(auth, settings)
    with _LOCK:
        cur = _COUNTERS[(auth.key_id, today)]
        if cur >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "plan": auth.plan,
                    "tier": auth.tier,
                    "limit_per_day": limit,
                },
                headers={"Retry-After": "3600"},
            )
        _COUNTERS[(auth.key_id, today)] = cur + 1
        return cur + 1, limit


def require_quota(
    auth: AuthContext = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """FastAPI dependency: auth + quota check in one shot."""
    consume(auth, settings)
    return auth
