"""Admin role + owner-by-email + admin console (full access)."""

from __future__ import annotations

ADMIN_EMAIL = "prabhawa@wavervanir.com"  # the default configured owner email
ADMIN_PW = "owner-pass-123456"


def _token(client, email, pw="member-pass-123456"):
    return client.post("/auth/register", json={"email": email, "password": pw}).json()["access_token"]


def _admin_headers(client):
    return {"Authorization": f"Bearer {_token(client, ADMIN_EMAIL, ADMIN_PW)}"}


def test_owner_email_is_admin_on_register(client):
    r = client.post("/auth/register", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 201
    u = r.json()["user"]
    assert u["is_admin"] is True
    assert u["has_terminal"] is True  # full access, no subscription needed


def test_non_owner_is_not_admin(client):
    token = _token(client, "analyst@x.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["is_admin"] is False


def test_admin_bypasses_subscription_gate(client):
    h = _admin_headers(client)
    r = client.get("/v1/desk/whoami", headers=h)
    assert r.status_code == 200
    assert r.json()["terminal_access"] is True


def test_non_admin_denied_admin_routes(client):
    token = _token(client, "member@x.com")
    r = client.get("/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "admin_required"


def test_admin_lists_all_users(client):
    _token(client, "a@x.com")
    _token(client, "b@x.com")
    h = _admin_headers(client)
    r = client.get("/v1/admin/users", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 3
    emails = {u["email"] for u in body["users"]}
    assert ADMIN_EMAIL in emails
    # No password material is ever exposed.
    assert all("password" not in k for u in body["users"] for k in u)


def test_admin_grants_and_revokes_entitlement(client):
    _token(client, "client@fund.example")
    h = _admin_headers(client)
    grant = client.post("/v1/admin/entitlement", headers=h,
                        json={"email": "client@fund.example", "plan": "desk", "status": "active"})
    assert grant.status_code == 200
    assert grant.json()["user"]["plan"] == "desk"
    assert grant.json()["user"]["status"] == "active"

    revoke = client.post("/v1/admin/entitlement", headers=h,
                        json={"email": "client@fund.example", "plan": "free", "status": "revoked"})
    assert revoke.status_code == 200
    assert revoke.json()["user"]["status"] == "revoked"


def test_admin_grant_unknown_plan_422(client):
    _token(client, "c2@x.com")
    h = _admin_headers(client)
    r = client.post("/v1/admin/entitlement", headers=h,
                   json={"email": "c2@x.com", "plan": "platinum", "status": "active"})
    assert r.status_code == 422


def test_admin_can_promote_but_not_self_demote(client):
    _token(client, "deputy@x.com")
    h = _admin_headers(client)
    up = client.post("/v1/admin/set-admin", headers=h, json={"email": "deputy@x.com", "is_admin": True})
    assert up.status_code == 200 and up.json()["user"]["is_admin"] is True

    self_demote = client.post("/v1/admin/set-admin", headers=h,
                             json={"email": ADMIN_EMAIL, "is_admin": False})
    assert self_demote.status_code == 400


def test_admin_audit_verify(client):
    h = _admin_headers(client)
    r = client.get("/v1/admin/audit/verify", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["chain_ok"] is True
    assert body["total_events"] >= 1
