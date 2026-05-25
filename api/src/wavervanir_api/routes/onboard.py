"""One-shot API-key disclosure after a Stripe checkout success redirect.

Customer lands on the landing page's ``/onboard?session_id=cs_test_…``
URL → calls ``GET /onboard?session_id=…`` here exactly once.

  * First hit (session_id known, not yet disclosed) → returns the raw key,
    sets ``disclosed_at``, clears the stored raw token from the row.
  * Second hit on same session_id → ``410 Gone``.
  * Unknown session_id → ``404 Not Found``.

The raw token never leaves this endpoint and is wiped from the row on
disclosure. Only the peppered hash remains in ``api_keys``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from wavervanir_api.config import Settings, get_settings
from wavervanir_api.db import OnboardSession, get_engine

router = APIRouter()


@router.get("/onboard")
def onboard(
    session_id: str = Query(..., min_length=4, max_length=200, alias="session_id"),
    settings: Settings = Depends(get_settings),
) -> dict:
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(
            select(OnboardSession).where(OnboardSession.stripe_session_id == session_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "unknown session_id"},
            )
        if row.disclosed_at is not None or not row.raw_token:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"error": "api key already disclosed for this session"},
            )

        raw = row.raw_token
        row.disclosed_at = datetime.now(timezone.utc)
        row.raw_token = None  # wipe at-rest plaintext immediately on disclosure
        session.add(row)
        session.commit()
        session.refresh(row)

    return {
        "api_key": raw,
        "plan": row.plan,
        "disclosed_at": row.disclosed_at.isoformat() if row.disclosed_at else None,
        "warning": (
            "This is the only time the key will be shown. Store it securely. "
            "If you lose it, contact support to rotate."
        ),
    }
