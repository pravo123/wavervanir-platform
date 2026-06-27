"""Admin (owner) routes — full-access operator console.

All routes are gated by :func:`wavervanir_api.users.require_admin` (default-deny;
every call is written to the tamper-evident access ledger as an ADMIN_ACTION).
The owner email is granted admin automatically (see ``config.admin_emails``);
these routes let that owner manage every account, entitlement, and the ledger.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from wavervanir_api.access_audit import export_subject, verify_access_chain
from wavervanir_api.config import Settings, get_settings
from wavervanir_api.db import User, get_engine
from wavervanir_api.plans import is_known_plan
from wavervanir_api.users import AuthService, InvalidCredentials, UserContext, require_admin

router = APIRouter()

_VALID_STATUS = {"active", "inactive", "revoked", "grace"}


def _user_summary(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "plan": u.plan,
        "status": u.status,
        "is_admin": bool(u.is_admin),
        "is_active": bool(u.is_active),
        "stripe_customer_id": u.stripe_customer_id,
        "created_at": u.created_at.isoformat() if isinstance(u.created_at, datetime) else None,
        "last_login_at": u.last_login_at.isoformat() if isinstance(u.last_login_at, datetime) else None,
    }


class EntitlementRequest(BaseModel):
    email: EmailStr
    plan: str = Field(description="free|researcher|pro|institutional|regulator|desk")
    status: str = Field(default="active", description="active|inactive|revoked|grace")


class SetAdminRequest(BaseModel):
    email: EmailStr
    is_admin: bool = True


@router.get("/admin/users")
def list_users(
    admin: UserContext = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Every account (no password hashes)."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        users = session.exec(select(User).order_by(User.id.asc())).all()  # type: ignore[attr-defined]
    return {"count": len(users), "users": [_user_summary(u) for u in users]}


@router.post("/admin/entitlement")
def set_entitlement(
    body: EntitlementRequest,
    admin: UserContext = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Grant or revoke a user's plan/status entitlement."""
    if not is_known_plan(body.plan):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown plan")
    if body.status not in _VALID_STATUS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown status")
    try:
        user = AuthService(settings).set_entitlement(
            email=str(body.email), plan=body.plan, status_=body.status
        )
    except InvalidCredentials:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return {"ok": True, "user": _user_summary(user)}


@router.post("/admin/set-admin")
def set_admin(
    body: SetAdminRequest,
    admin: UserContext = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Promote or demote another account's admin flag.

    An admin may not demote themselves (prevents accidental lock-out).
    """
    target = str(body.email).strip().lower()
    if not body.is_admin and target == admin.email.strip().lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="cannot demote yourself")
    try:
        user = AuthService(settings).set_admin(email=target, is_admin=body.is_admin)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return {"ok": True, "user": _user_summary(user)}


@router.get("/admin/audit/verify")
def audit_verify(
    admin: UserContext = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Re-hash the entire access ledger and report integrity."""
    ok, broken = verify_access_chain(settings)
    engine = get_engine(settings.db_url)
    from wavervanir_api.db import AccessEvent

    with Session(engine) as session:
        total = len(session.exec(select(AccessEvent)).all())
    return {"chain_ok": ok, "broken_ids": broken, "total_events": total}


@router.get("/admin/audit")
def audit_subject(
    subject: str = Query(..., min_length=1, max_length=128),
    admin: UserContext = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """The full access trail for any subject (e.g. ``user:42``)."""
    events = export_subject(settings, subject)
    return {"subject": subject, "count": len(events), "events": events}
