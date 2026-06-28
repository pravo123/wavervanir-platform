"""User sign-in for the CBSRM Desk terminal — the "sign in class".

:class:`AuthService` is the single object that registers, authenticates, and
re-issues tokens for interactive (email + password) accounts, using stdlib
scrypt hashing (:mod:`wavervanir_api.security`) and stdlib HS256 JWTs. Every
register, sign-in (success *and* failure), refresh, and premium access is
appended to the tamper-evident access ledger (:mod:`wavervanir_api.access_audit`).

Entitlement is **default-deny**: a signed-in user reaches Desk routes only when
their ``plan`` grants the terminal *and* ``status == "active"`` — kept in sync
by the Stripe webhook. :func:`require_user` and :func:`require_desk` are the
FastAPI dependencies that protect routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlmodel import Session, select

from wavervanir_api.access_audit import AccessKind, append_access_event
from wavervanir_api.config import Settings, admin_email_set, get_settings
from wavervanir_api.db import User, get_engine
from wavervanir_api.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# Plans that grant the interactive Desk terminal. ``desk`` is the $48k/yr tier;
# the bespoke institutional / regulator tiers inherit terminal access.
TERMINAL_PLANS = {"desk", "institutional", "regulator"}
# Subscription statuses that still grant the terminal ("grace" = the dunning
# window after a failed payment, during which access is retained). "trialing" is
# entitled too, but only while the trial has not expired (checked separately).
ENTITLED_STATUSES = {"active", "grace"}

MIN_PASSWORD_LEN = 8
TRIAL_DAYS = 7  # self-serve free-trial length for the Desk terminal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Treat a naive datetime (SQLite round-trips lose tz) as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ── domain errors (routes map these to HTTP status codes) ───────────────────


class AuthError(Exception):
    """Base class for sign-in domain errors."""


class EmailExistsError(AuthError):
    """Registration attempted with an email that already exists."""


class InvalidCredentials(AuthError):
    """Email not found or password mismatch (deliberately indistinguishable)."""


class AccountDisabled(AuthError):
    """The account exists but ``is_active`` is False."""


class WeakPassword(AuthError):
    """Password failed the minimum-strength policy."""


class TrialNotAllowed(AuthError):
    """A free trial can't be started (already subscribed, or trial already used)."""


# ── value objects ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class UserContext:
    """Resolved caller identity attached to authenticated requests."""

    user_id: int
    email: str
    name: str
    plan: str
    status: str
    is_admin: bool = False
    trial_end: Optional[datetime] = None  # set when status == "trialing"

    @classmethod
    def from_user(cls, user: User) -> "UserContext":
        return cls(
            user_id=user.id or 0,
            email=user.email,
            name=user.name,
            plan=user.plan,
            status=user.status,
            is_admin=bool(user.is_admin),
            trial_end=_aware(user.grace_until) if user.status == "trialing" else None,
        )

    @property
    def has_terminal(self) -> bool:
        # Admins have full access to every desk function regardless of subscription.
        if self.is_admin:
            return True
        if self.plan not in TERMINAL_PLANS:
            return False
        # A trial grants access only until it expires.
        if self.status == "trialing":
            return self.trial_end is not None and self.trial_end > _utcnow()
        return self.status in ENTITLED_STATUSES

    @property
    def trial_days_left(self) -> Optional[int]:
        if self.status != "trialing" or self.trial_end is None:
            return None
        secs = (self.trial_end - _utcnow()).total_seconds()
        return max(0, int(-(-secs // 86400)))  # ceil to whole days


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    user: User


# ── the sign-in class ───────────────────────────────────────────────────────


def _normalise_email(email: str) -> str:
    return (email or "").strip().lower()


class AuthService:
    """Register / authenticate / re-issue tokens against the ``users`` table."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engine = get_engine(settings.db_url)

    # -- persistence helpers --------------------------------------------------

    def _by_email(self, session: Session, email: str) -> Optional[User]:
        return session.exec(select(User).where(User.email == email)).first()

    def _by_id(self, session: Session, user_id: int) -> Optional[User]:
        return session.get(User, user_id)

    # -- registration ---------------------------------------------------------

    def register(self, *, email: str, password: str, name: str = "") -> User:
        email = _normalise_email(email)
        if not email or "@" not in email:
            raise AuthError("a valid email is required")
        if not password or len(password) < MIN_PASSWORD_LEN:
            raise WeakPassword(f"password must be at least {MIN_PASSWORD_LEN} characters")

        with Session(self._engine) as session:
            if self._by_email(session, email) is not None:
                raise EmailExistsError(email)
            user = User(
                email=email,
                password_hash=hash_password(password),
                name=(name or "").strip(),
                plan="free",
                status="inactive",
                is_active=True,
                # The configured owner email(s) get admin (full access) on sign-up.
                is_admin=email in admin_email_set(self.settings),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        append_access_event(
            settings=self.settings,
            subject=f"user:{user.id}",
            kind=AccessKind.REGISTERED,
            route="/auth/register",
            payload={"plan": user.plan},
        )
        return user

    # -- authentication -------------------------------------------------------

    def authenticate(self, *, email: str, password: str) -> User:
        """Return the user on valid credentials, else raise. Audited either way."""
        email = _normalise_email(email)
        with Session(self._engine) as session:
            user = self._by_email(session, email)
            ok = user is not None and verify_password(password, user.password_hash)
            if not ok or user is None:
                append_access_event(
                    settings=self.settings,
                    subject=f"user:{user.id}" if user else "user:unknown",
                    kind=AccessKind.SIGNIN_FAILED,
                    route="/auth/login",
                    payload={"reason": "bad_credentials"},
                )
                raise InvalidCredentials("invalid email or password")
            if not user.is_active:
                append_access_event(
                    settings=self.settings,
                    subject=f"user:{user.id}",
                    kind=AccessKind.SIGNIN_FAILED,
                    route="/auth/login",
                    payload={"reason": "account_disabled"},
                )
                raise AccountDisabled("account is disabled")

            # Self-heal: promote a pre-existing account to admin if its email is
            # now in the configured owner list (idempotent).
            if user.email in admin_email_set(self.settings) and not user.is_admin:
                user.is_admin = True
            user.last_login_at = datetime.now(timezone.utc)
            session.add(user)
            session.commit()
            session.refresh(user)

        append_access_event(
            settings=self.settings,
            subject=f"user:{user.id}",
            kind=AccessKind.SIGNIN,
            route="/auth/login",
            payload={"plan": user.plan, "status": user.status},
        )
        return user

    def login(self, *, email: str, password: str) -> TokenBundle:
        user = self.authenticate(email=email, password=password)
        access, refresh = self.issue_tokens(user)
        return TokenBundle(access_token=access, refresh_token=refresh, user=user)

    # -- tokens ---------------------------------------------------------------

    def issue_tokens(self, user: User) -> tuple[str, str]:
        secret = self.settings.jwt_secret
        extra = {"email": user.email, "plan": user.plan}
        access = create_access_token(
            user.id, secret, ttl_minutes=self.settings.access_token_ttl_min, extra=extra
        )
        refresh = create_refresh_token(
            user.id, secret, ttl_days=self.settings.refresh_token_ttl_days
        )
        return access, refresh

    def refresh(self, refresh_token: str) -> TokenBundle:
        try:
            claims = decode_token(
                refresh_token, self.settings.jwt_secret, expected_type="refresh"
            )
        except TokenError as exc:
            raise InvalidCredentials(str(exc))
        user = self._require_active_user(int(claims["sub"]))
        access, refresh = self.issue_tokens(user)
        append_access_event(
            settings=self.settings,
            subject=f"user:{user.id}",
            kind=AccessKind.TOKEN_REFRESH,
            route="/auth/refresh",
            payload={"plan": user.plan},
        )
        return TokenBundle(access_token=access, refresh_token=refresh, user=user)

    def user_from_access_token(self, token: str) -> User:
        claims = decode_token(token, self.settings.jwt_secret, expected_type="access")
        return self._require_active_user(int(claims["sub"]))

    def _require_active_user(self, user_id: int) -> User:
        with Session(self._engine) as session:
            user = self._by_id(session, user_id)
            if user is None:
                raise InvalidCredentials("user not found")
            if not user.is_active:
                raise AccountDisabled("account is disabled")
            return user

    # -- entitlement (kept in sync by the Stripe webhook / ops tooling) -------

    def set_entitlement(
        self,
        *,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
        plan: str,
        status_: str,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        grace_until: Optional[datetime] = None,
    ) -> User:
        """Set a user's plan/status entitlement. Returns the updated user."""
        with Session(self._engine) as session:
            user: Optional[User] = None
            if user_id is not None:
                user = self._by_id(session, user_id)
            elif email is not None:
                user = self._by_email(session, _normalise_email(email))
            if user is None:
                raise InvalidCredentials("user not found for entitlement update")
            user.plan = plan
            user.status = status_
            if stripe_customer_id is not None:
                user.stripe_customer_id = stripe_customer_id
            if stripe_subscription_id is not None:
                user.stripe_subscription_id = stripe_subscription_id
            user.grace_until = grace_until
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def start_trial(self, *, user_id: int, days: int = TRIAL_DAYS) -> User:
        """Grant a self-serve free trial of the Desk terminal.

        One trial per account: only an ``inactive`` (never-subscribed) account may
        start one. An already-trialing user is returned unchanged (idempotent — no
        extension); a paying customer or a used-up trial is refused. Access ends
        automatically at ``grace_until`` (enforced in ``UserContext.has_terminal``),
        so no card and no sweep job are required. The grant is written to the
        tamper-evident access ledger.
        """
        with Session(self._engine) as session:
            user = self._by_id(session, user_id)
            if user is None:
                raise InvalidCredentials("user not found for trial")
            if user.is_admin or (user.plan in TERMINAL_PLANS and user.status in {"active", "grace"}):
                raise TrialNotAllowed("already_subscribed")
            if user.status == "trialing":
                return user  # idempotent — never extend
            if user.status != "inactive":
                raise TrialNotAllowed("trial_used")
            user.plan = "desk"
            user.status = "trialing"
            user.grace_until = _utcnow() + timedelta(days=days)
            session.add(user)
            session.commit()
            session.refresh(user)

        append_access_event(
            settings=self.settings,
            subject=f"user:{user.id}",
            kind=AccessKind.ACCESS_GRANTED,
            route="/auth/start-trial",
            payload={"status": "trialing",
                     "trial_until": _aware(user.grace_until).isoformat()},
        )
        return user

    # -- admin provisioning (operator tooling) --------------------------------

    def set_admin(
        self, *, email: Optional[str] = None, user_id: Optional[int] = None, is_admin: bool = True
    ) -> User:
        """Promote/demote a user's admin flag. Returns the updated user."""
        with Session(self._engine) as session:
            user: Optional[User] = None
            if user_id is not None:
                user = self._by_id(session, user_id)
            elif email is not None:
                user = self._by_email(session, _normalise_email(email))
            if user is None:
                raise InvalidCredentials("user not found for admin update")
            user.is_admin = bool(is_admin)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def set_password(self, *, email: str, password: str) -> User:
        """Reset a user's password. Returns the updated user."""
        if not password or len(password) < MIN_PASSWORD_LEN:
            raise WeakPassword(f"password must be at least {MIN_PASSWORD_LEN} characters")
        with Session(self._engine) as session:
            user = self._by_email(session, _normalise_email(email))
            if user is None:
                raise InvalidCredentials("user not found for password reset")
            user.password_hash = hash_password(password)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def provision_admin(
        self, *, email: str, password: str, name: str = "", reset_password: bool = False
    ) -> User:
        """Create-or-promote an admin (operator bootstrap).

        New user → register with ``password`` then flag admin. Existing user →
        promote to admin; the password is only changed when ``reset_password``
        is set (never silently overwritten).
        """
        email = _normalise_email(email)
        with Session(self._engine) as session:
            exists = self._by_email(session, email) is not None
        if not exists:
            self.register(email=email, password=password, name=name)
        elif reset_password:
            self.set_password(email=email, password=password)
        return self.set_admin(email=email, is_admin=True)

    # -- Stripe webhook sync (increment 2) ------------------------------------

    @staticmethod
    def _parse_client_ref(ref: Optional[str]) -> tuple[Optional[int], Optional[str]]:
        """Parse a Stripe ``client_reference_id`` into (user_id, email).

        Accepts a bare id ("42"), a prefixed id ("user:42"), or an email.
        """
        ref = (ref or "").strip()
        if ref.startswith("user:"):
            ref = ref[len("user:"):]
        if ref.isdigit():
            return int(ref), None
        if "@" in ref:
            return None, _normalise_email(ref)
        return None, None

    def entitle_from_checkout(
        self,
        *,
        client_reference_id: Optional[str],
        plan: str,
        stripe_customer_id: Optional[str],
        stripe_subscription_id: Optional[str],
    ) -> Optional[User]:
        """``checkout.session.completed`` → activate the referenced user. Idempotent."""
        user_id, email = self._parse_client_ref(client_reference_id)
        if user_id is None and email is None:
            return None
        try:
            return self.set_entitlement(
                user_id=user_id,
                email=email,
                plan=plan,
                status_="active",
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
            )
        except InvalidCredentials:
            return None  # ref didn't resolve to a known user — leave untouched

    def update_entitlement_by_subscription(
        self, *, stripe_subscription_id: str, plan: str, status_: str = "active"
    ) -> int:
        """``customer.subscription.updated`` → sync plan/status. Returns row count."""
        with Session(self._engine) as session:
            users = session.exec(
                select(User).where(User.stripe_subscription_id == stripe_subscription_id)
            ).all()
            for u in users:
                u.plan = plan
                u.status = status_
                u.grace_until = None
                session.add(u)
            session.commit()
            return len(users)

    def revoke_by_customer(self, *, stripe_customer_id: str) -> int:
        """``customer.subscription.deleted`` → revoke terminal access. Returns count."""
        with Session(self._engine) as session:
            users = session.exec(
                select(User).where(User.stripe_customer_id == stripe_customer_id)
            ).all()
            for u in users:
                u.status = "revoked"
                u.grace_until = None
                session.add(u)
            session.commit()
            return len(users)

    def grace_by_subscription(
        self, *, stripe_subscription_id: str, grace_until: datetime
    ) -> int:
        """``invoice.payment_failed`` → dunning grace; access retained. Returns count."""
        with Session(self._engine) as session:
            users = session.exec(
                select(User).where(
                    User.stripe_subscription_id == stripe_subscription_id,
                    User.status == "active",
                )
            ).all()
            for u in users:
                u.status = "grace"
                u.grace_until = grace_until
                session.add(u)
            session.commit()
            return len(users)


# ── FastAPI dependencies ────────────────────────────────────────────────────


def _bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1].strip()


def require_user(
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """Resolve a valid *access* JWT to the active user. 401 otherwise."""
    token = _bearer(authorization)
    try:
        user = AuthService(settings).user_from_access_token(token)
    except (TokenError, AuthError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserContext.from_user(user)


def require_desk(
    request: Request,
    ctx: UserContext = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """Default-deny Desk gate. Logs every grant/deny to the access ledger."""
    route = request.url.path
    if not ctx.has_terminal:
        append_access_event(
            settings=settings,
            subject=f"user:{ctx.user_id}",
            kind=AccessKind.ACCESS_DENIED,
            route=route,
            payload={"plan": ctx.plan, "status": ctx.status},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "desk_subscription_required",
                "plan": ctx.plan,
                "status": ctx.status,
            },
        )
    append_access_event(
        settings=settings,
        subject=f"user:{ctx.user_id}",
        kind=AccessKind.ACCESS_GRANTED,
        route=route,
        payload={"plan": ctx.plan},
    )
    return ctx


def require_admin(
    request: Request,
    ctx: UserContext = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """Default-deny admin gate (full-access owner). Logs to the access ledger."""
    route = request.url.path
    if not ctx.is_admin:
        append_access_event(
            settings=settings,
            subject=f"user:{ctx.user_id}",
            kind=AccessKind.ACCESS_DENIED,
            route=route,
            payload={"reason": "not_admin"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "admin_required"},
        )
    append_access_event(
        settings=settings,
        subject=f"user:{ctx.user_id}",
        kind=AccessKind.ADMIN_ACTION,
        route=route,
        payload={"admin": ctx.email},
    )
    return ctx
