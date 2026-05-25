"""Public data-ingestion routes (providers + by-symbol snapshot)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from wavervanir_api.auth import AuthContext, require_api_key
from wavervanir_api.config import Settings, get_settings
from wavervanir_api.providers import (
    ProviderUnavailableError,
    get_provider,
    list_providers,
)

router = APIRouter()


@router.get("/data/providers")
def providers(
    settings: Settings = Depends(get_settings),
    _auth: AuthContext = Depends(require_api_key),
) -> dict:
    statuses = [
        {
            "name": s.name,
            "kind": s.kind,
            "enabled": s.enabled,
            "reason": s.reason,
            "requires": s.requires,
        }
        for s in list_providers(settings)
    ]
    return {"providers": statuses}


@router.get("/data/snapshot/{symbol}")
def snapshot(
    symbol: str,
    provider: str = Query(default="demo", description="demo|fmp|bullflow"),
    kind: str = Query(default="market", description="market|flow"),
    settings: Settings = Depends(get_settings),
    _auth: AuthContext = Depends(require_api_key),
) -> dict:
    sym = (symbol or "").strip()
    if not sym:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="symbol path parameter is empty",
        )

    try:
        prov = get_provider(provider)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    try:
        if kind == "market":
            snap: Any = prov.fetch_market(sym, settings)
        elif kind == "flow":
            snap = prov.fetch_flow(sym, settings)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown kind {kind!r}; expected 'market' or 'flow'",
            )
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provider_unavailable", "provider": provider, "reason": str(exc)},
        )

    return {"provider": provider, "kind": kind, "snapshot": snap.model_dump(mode="json")}
