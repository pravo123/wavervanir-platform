"""Public unauthenticated health endpoints.

``/health``       — cheap liveness (Render's healthCheckPath). MUST NOT depend on
                    upstream feeds, or a FRED/financialdata outage would take the
                    service down.
``/health/ready`` — deeper readiness: DB connectivity + conditions-cache freshness
                    + whether the data keys are configured. 200 ready / 503 degraded.
"""

from __future__ import annotations

import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from wavervanir_api import __version__

router = APIRouter()


# ``/health/ready`` is public, so it reports a fixed vocabulary of causes rather
# than the driver's own message, which embeds the database host, its IP and the
# role name. Anything unrecognised degrades to the exception type alone.
_DB_FAILURE_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("too many connections", "too many connections"),
    ("too many clients already", "too many connections"),
    ("remaining connection slots", "too many connections"),
    ("password authentication failed", "authentication failed"),
    ("role .* does not exist", "authentication failed"),
    ("database .* does not exist", "database missing"),
    ("system is starting up", "database starting up"),
    ("system is shutting down", "database shutting down"),
    ("server closed the connection unexpectedly", "connection dropped"),
    ("ssl connection has been closed", "connection dropped"),
    ("could not translate host name", "host unresolvable"),
    ("connection refused", "connection refused"),
    ("timeout expired", "connect timeout"),
    ("could not connect to server", "unreachable"),
)


def _failure_reason(exc: BaseException) -> str:
    """A safe, fixed-vocabulary description of a database failure."""
    haystack = f"{exc} {getattr(exc, 'orig', '')}".lower()
    for pattern, reason in _DB_FAILURE_SIGNATURES:
        if re.search(pattern, haystack):
            return f"error: {type(exc).__name__} ({reason})"
    return f"error: {type(exc).__name__}"


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "wavervanir-api", "version": __version__}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    from wavervanir_api import desk_conditions
    from wavervanir_api.config import get_settings
    from wavervanir_api.db import get_engine

    settings = get_settings()
    checks: dict = {}
    ok = True

    # DB connectivity — a real round-trip, not just "engine exists".
    try:
        engine = get_engine(settings.db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["db"] = _failure_reason(exc)
        ok = False

    # Conditions cache — informational (a cold cache is not "not ready"; the first
    # request or the cron warmer fills it). Report age + live-lens count.
    try:
        peek = desk_conditions.cache_peek(settings, "live")
        checks["conditions_cache"] = peek if peek else "cold"
    except Exception as exc:  # noqa: BLE001
        checks["conditions_cache"] = _failure_reason(exc)

    # Data-feed key presence (not reachability — that stays out of the hot path).
    checks["fred_key"] = "set" if settings.fred_api_key else "unset"
    checks["financialdata_key"] = "set" if settings.financialdata_api_key else "unset"

    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "degraded",
                 "service": "wavervanir-api", "version": __version__, "checks": checks},
    )
