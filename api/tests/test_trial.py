"""Self-serve 7-day free trial of the Desk terminal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


def _register(client, email="trial@fund.example"):
    r = client.post("/auth/register", json={"email": email, "password": "strong-pass-123"}).json()
    return r["access_token"], r["user"]["id"]


def test_trial_unlocks_terminal_then_expires(client):
    token, uid = _register(client)
    h = {"Authorization": f"Bearer {token}"}

    # before trial: free / inactive, terminal gated
    me = client.get("/auth/me", headers=h).json()
    assert me["status"] == "inactive" and me["has_terminal"] is False
    assert client.get("/v1/desk/conditions?source=demo", headers=h).status_code == 403

    # start the trial → entitled, ~7 days left, terminal opens
    r = client.post("/auth/start-trial", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "trialing" and body["plan"] == "desk"
    assert body["has_terminal"] is True
    assert body["trial_days_left"] in (6, 7)
    assert client.get("/v1/desk/conditions?source=demo", headers=h).status_code == 200

    # backdate the trial end → access ends automatically (lazy expiry)
    AuthService(get_settings()).set_entitlement(
        user_id=uid, plan="desk", status_="trialing",
        grace_until=datetime.now(timezone.utc) - timedelta(days=1),
    )
    me2 = client.get("/auth/me", headers=h).json()
    assert me2["has_terminal"] is False and me2["trial_days_left"] == 0
    assert client.get("/v1/desk/conditions?source=demo", headers=h).status_code == 403


def test_trial_is_one_per_account(client):
    token, uid = _register(client, email="once@fund.example")
    h = {"Authorization": f"Bearer {token}"}
    client.post("/auth/start-trial", headers=h)
    # expire it
    AuthService(get_settings()).set_entitlement(
        user_id=uid, plan="desk", status_="trialing",
        grace_until=datetime.now(timezone.utc) - timedelta(days=1),
    )
    # a second start is idempotent — it does NOT re-grant access
    again = client.post("/auth/start-trial", headers=h)
    assert again.status_code == 200
    assert again.json()["has_terminal"] is False  # still expired, no new trial


def test_subscribed_user_cannot_trial(client):
    token, _ = _register(client, email="paid@fund.example")
    h = {"Authorization": f"Bearer {token}"}
    AuthService(get_settings()).set_entitlement(
        email="paid@fund.example", plan="desk", status_="active"
    )
    r = client.post("/auth/start-trial", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "already_subscribed"


def test_start_trial_requires_auth(client):
    assert client.post("/auth/start-trial").status_code == 401
