"""End-to-end contract for the CBSRM Desk sign-in + entitlement gate."""

from __future__ import annotations

from sqlmodel import Session, select

from wavervanir_api.config import get_settings
from wavervanir_api.db import User, get_engine
from wavervanir_api.users import AuthService

EMAIL = "analyst@centralbank.example"
PASSWORD = "a-strong-passphrase-1"


def _register(client, email=EMAIL, password=PASSWORD, name="Analyst"):
    return client.post(
        "/auth/register", json={"email": email, "password": password, "name": name}
    )


def _grant_desk(email=EMAIL):
    AuthService(get_settings()).set_entitlement(
        email=email,
        plan="desk",
        status_="active",
        stripe_customer_id="cus_test",
        stripe_subscription_id="sub_test",
    )


# ── registration ─────────────────────────────────────────────────────────────


def test_register_returns_tokens_and_user(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == EMAIL
    assert body["user"]["plan"] == "free"
    assert body["user"]["status"] == "inactive"
    assert body["user"]["has_terminal"] is False


def test_password_is_not_stored_in_plaintext(client):
    _register(client)
    engine = get_engine(get_settings().db_url)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == EMAIL)).first()
    assert user is not None
    assert PASSWORD not in user.password_hash
    assert user.password_hash.split("$")[0] in ("scrypt", "pbkdf2")


def test_duplicate_email_conflicts(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_weak_password_rejected(client):
    r = client.post("/auth/register", json={"email": "x@y.com", "password": "short"})
    assert r.status_code == 422  # pydantic min_length


# ── login ────────────────────────────────────────────────────────────────────


def test_login_success(client):
    _register(client)
    r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_login_wrong_password_401(client):
    _register(client)
    r = client.post("/auth/login", json={"email": EMAIL, "password": "nope-nope-nope"})
    assert r.status_code == 401


def test_login_unknown_email_401(client):
    r = client.post("/auth/login", json={"email": "ghost@nowhere.io", "password": PASSWORD})
    assert r.status_code == 401


# ── /auth/me + refresh ───────────────────────────────────────────────────────


def test_me_requires_access_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client):
    token = _register(client).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_refresh_token_cannot_be_used_as_access(client):
    refresh = _register(client).json()["refresh_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401


def test_refresh_issues_new_pair(client):
    refresh = _register(client).json()["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    # The new access token works against a protected route.
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_refresh_rejects_access_token(client):
    access = _register(client).json()["access_token"]
    r = client.post("/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


# ── the entitlement gate (default-deny) ──────────────────────────────────────


def test_desk_requires_auth(client):
    assert client.get("/v1/desk/whoami").status_code == 401


def test_desk_denied_for_free_user_then_granted(client):
    token = _register(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    denied = client.get("/v1/desk/whoami", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "desk_subscription_required"

    _grant_desk()  # Stripe webhook would do this on checkout.session.completed

    # Same token now passes — require_user reloads the user's live entitlement.
    granted = client.get("/v1/desk/whoami", headers=headers)
    assert granted.status_code == 200, granted.text
    body = granted.json()
    assert body["terminal_access"] is True
    assert body["plan"] == "desk"


def test_me_reflects_entitlement_change_without_relogin(client):
    token = _register(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    _grant_desk()
    me = client.get("/auth/me", headers=headers).json()
    assert me["plan"] == "desk"
    assert me["has_terminal"] is True


# ── tamper-evident audit trail ───────────────────────────────────────────────


def test_audit_export_is_chain_verified(client):
    token = _register(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/v1/desk/whoami", headers=headers)  # one ACCESS_DENIED
    _grant_desk()
    client.get("/v1/desk/whoami", headers=headers)  # one ACCESS_GRANTED

    r = client.get("/v1/desk/audit/export", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chain_ok"] is True
    assert body["broken_ids"] == []
    kinds = {e["kind"] for e in body["events"]}
    assert "REGISTERED" in kinds
    assert "ACCESS_GRANTED" in kinds
    assert "ACCESS_DENIED" in kinds
