"""Public waitlist endpoint — no auth, simple validation."""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from wavervanir_api.config import Settings, get_settings
from wavervanir_api.db import WaitlistEntry, get_engine

router = APIRouter()


_TIERS = ("researcher", "pro", "institutional", "exec_risk", "regulator")


class WaitlistRequest(BaseModel):
    email: EmailStr
    tier_interest: str = Field(default="researcher")
    source: str = Field(default="landing", max_length=64)


class WaitlistResponse(BaseModel):
    ok: bool
    id: int
    deduplicated: bool


@router.post("/waitlist", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
def add_to_waitlist(
    body: WaitlistRequest,
    settings: Settings = Depends(get_settings),
) -> WaitlistResponse:
    if body.tier_interest not in _TIERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "unknown tier_interest", "allowed": list(_TIERS)},
        )
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        existing = session.exec(
            select(WaitlistEntry).where(WaitlistEntry.email == body.email)
        ).first()
        if existing:
            return WaitlistResponse(ok=True, id=existing.id or 0, deduplicated=True)

        row = WaitlistEntry(
            email=body.email,
            tier_interest=body.tier_interest,
            source=body.source,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return WaitlistResponse(ok=True, id=row.id or 0, deduplicated=False)
