"""CBSRM macro-composite route.

Thin pass-through over the public ``cbsrm.reporting.build_macro_composite_report``
builder. Read-only, deterministic, offline (no live data adapters).

Out of MVP scope (added in a later slice):
    /v1/cbsrm/srisk
    /v1/cbsrm/delta-covar
    /v1/cbsrm/mes
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from wavervanir_api.audit import record_audit, timer
from wavervanir_api.auth import AuthContext, require_api_key
from wavervanir_api.config import Settings, get_settings
from wavervanir_api.rate_limit import require_quota

router = APIRouter()


class MacroCompositeRequest(BaseModel):
    window_id: str = Field(..., description="Crisis window: 2008Q4 | 2020Q1 | 2023Q1")


class MacroCompositeResponse(BaseModel):
    window_id: str
    report: dict
    rendered_markdown: str


def _supported_windows() -> list[str]:
    """Defer the cbsrm import so missing dep gives a clean 503, not import error."""
    from cbsrm.reporting import list_macro_composite_windows  # type: ignore

    return list_macro_composite_windows()


@router.get("/macro-composite/windows")
def macro_composite_windows(
    _auth: AuthContext = Depends(require_quota),
) -> dict:
    try:
        windows = _supported_windows()
    except Exception as exc:  # pragma: no cover — env-dependent
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"cbsrm unavailable: {exc!r}",
        )
    return {"windows": windows}


@router.post("/macro-composite", response_model=MacroCompositeResponse)
def macro_composite(
    body: MacroCompositeRequest,
    auth: AuthContext = Depends(require_quota),
    settings: Settings = Depends(get_settings),
) -> MacroCompositeResponse:
    try:
        from cbsrm.reporting import (  # type: ignore
            build_macro_composite_report,
            render_macro_composite_markdown,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"cbsrm unavailable: {exc!r}",
        )

    supported = _supported_windows()
    if body.window_id not in supported:
        record_audit(
            settings=settings,
            key_id=auth.key_id,
            route="/v1/cbsrm/macro-composite",
            request_obj=body.model_dump(),
            response_obj={"error": "unknown window_id"},
            status_code=404,
            latency_ms=0,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "unknown window_id",
                "given": body.window_id,
                "supported": supported,
            },
        )

    with timer() as t:
        report = build_macro_composite_report(body.window_id)
        md = render_macro_composite_markdown(report)
    response = MacroCompositeResponse(
        window_id=body.window_id,
        report=report,
        rendered_markdown=md,
    )
    record_audit(
        settings=settings,
        key_id=auth.key_id,
        route="/v1/cbsrm/macro-composite",
        request_obj=body.model_dump(),
        response_obj=response.model_dump(),
        status_code=200,
        latency_ms=t.ms,
    )
    return response
