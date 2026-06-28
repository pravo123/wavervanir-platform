"""Sign-in endpoints for the CBSRM Desk terminal.

``POST /auth/register`` · ``POST /auth/login`` · ``POST /auth/refresh`` ·
``GET /auth/me``. All logic lives in :class:`wavervanir_api.users.AuthService`;
this module is the thin HTTP shell that validates input and maps domain errors
to status codes.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from wavervanir_api.config import Settings, get_settings
from wavervanir_api.users import (
    AccountDisabled,
    AuthError,
    AuthService,
    EmailExistsError,
    InvalidCredentials,
    TrialNotAllowed,
    UserContext,
    WeakPassword,
    require_user,
)

router = APIRouter()


# ── schemas ─────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    plan: str
    status: str
    has_terminal: bool
    is_admin: bool = False
    trial_days_left: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


def _user_out(ctx: UserContext) -> UserOut:
    return UserOut(
        id=ctx.user_id,
        email=ctx.email,
        name=ctx.name,
        plan=ctx.plan,
        status=ctx.status,
        has_terminal=ctx.has_terminal,
        is_admin=ctx.is_admin,
        trial_days_left=ctx.trial_days_left,
    )


# ── endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    svc = AuthService(settings)
    try:
        user = svc.register(email=body.email, password=body.password, name=body.name)
    except EmailExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="email already registered")
    except WeakPassword as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    access, refresh = svc.issue_tokens(user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=_user_out(UserContext.from_user(user)),
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    svc = AuthService(settings)
    try:
        bundle = svc.login(email=body.email, password=body.password)
    except (InvalidCredentials, AccountDisabled):
        # Single generic message — never reveal whether the email exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    return TokenResponse(
        access_token=bundle.access_token,
        refresh_token=bundle.refresh_token,
        user=_user_out(UserContext.from_user(bundle.user)),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    svc = AuthService(settings)
    try:
        bundle = svc.refresh(body.refresh_token)
    except (InvalidCredentials, AccountDisabled):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="invalid or expired refresh token"
        )
    return TokenResponse(
        access_token=bundle.access_token,
        refresh_token=bundle.refresh_token,
        user=_user_out(UserContext.from_user(bundle.user)),
    )


@router.get("/auth/me", response_model=UserOut)
def me(ctx: UserContext = Depends(require_user)) -> UserOut:
    # ``require_user`` reloads the user from the DB, so ``ctx`` already reflects
    # the current entitlement even if the token predates a plan change.
    return _user_out(ctx)


@router.post("/auth/start-trial", response_model=UserOut)
def start_trial(
    ctx: UserContext = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    """Start a self-serve 7-day free trial of the Desk terminal.

    One trial per account. Access is granted immediately (no card) and expires
    automatically after 7 days. The grant is written to the access ledger.
    """
    svc = AuthService(settings)
    try:
        user = svc.start_trial(user_id=ctx.user_id)
    except TrialNotAllowed as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"error": "trial_not_allowed", "reason": str(exc)},
        )
    except InvalidCredentials:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return _user_out(UserContext.from_user(user))
