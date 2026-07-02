"""Public unauthenticated health endpoints.

``/health``       — cheap liveness (Render's healthCheckPath). MUST NOT depend on
                    upstream feeds, or a FRED/financialdata outage would take the
                    service down.
``/health/ready`` — deeper readiness: DB connectivity + conditions-cache freshness
                    + whether the data keys are configured. 200 ready / 503 degraded.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from wavervanir_api import __version__

router = APIRouter()


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
        checks["db"] = f"error: {type(exc).__name__}"
        ok = False

    # Conditions cache — informational (a cold cache is not "not ready"; the first
    # request or the cron warmer fills it). Report age + live-lens count.
    try:
        peek = desk_conditions.cache_peek(settings, "live")
        checks["conditions_cache"] = peek if peek else "cold"
    except Exception as exc:  # noqa: BLE001
        checks["conditions_cache"] = f"error: {type(exc).__name__}"

    # Data-feed key presence (not reachability — that stays out of the hot path).
    checks["fred_key"] = "set" if settings.fred_api_key else "unset"
    checks["financialdata_key"] = "set" if settings.financialdata_api_key else "unset"

    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "degraded",
                 "service": "wavervanir-api", "version": __version__, "checks": checks},
    )
