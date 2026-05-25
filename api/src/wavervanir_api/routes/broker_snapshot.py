"""Broker-snapshot routes — validate-only + risk-aggregation.

The two endpoints are intentionally separated:

  * ``POST /v1/data/broker-snapshot/validate``     — schema + sanitization
  * ``POST /v1/data/broker-snapshot/risk-summary`` — validate, then aggregate
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from wavervanir_api.auth import AuthContext, require_api_key
from wavervanir_api.providers.broker_snapshot import (
    SnapshotValidationError,
    risk_summary,
    scrub_check,
    validate_snapshot,
)

router = APIRouter()


@router.post("/data/broker-snapshot/validate")
async def validate(
    request: Request,
    _auth: AuthContext = Depends(require_api_key),
) -> dict:
    payload = await _read_json(request)
    try:
        snap = validate_snapshot(payload)
    except SnapshotValidationError as exc:
        # 422 = unprocessable; reveal the *kind* of problem but not the payload.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "snapshot_validation_failed",
                "reason": str(exc),
                "scrub_violations": scrub_check(payload),
            },
        )
    return {
        "ok": True,
        "schema_version": snap.schema_version,
        "account_alias": snap.account_alias,
        "n_positions": len(snap.positions),
    }


@router.post("/data/broker-snapshot/risk-summary")
async def risk_summary_route(
    request: Request,
    _auth: AuthContext = Depends(require_api_key),
) -> dict:
    payload = await _read_json(request)
    try:
        snap = validate_snapshot(payload)
    except SnapshotValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "snapshot_validation_failed",
                "reason": str(exc),
                "scrub_violations": scrub_check(payload),
            },
        )
    summary = risk_summary(snap)
    return summary.model_dump(mode="json")


# ----------------------------------------------------------------------


async def _read_json(request: Request) -> Any:
    try:
        return await request.json()
    except Exception as exc:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid JSON body: {exc!r}",
        )
