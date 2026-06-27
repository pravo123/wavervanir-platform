"""Gated premium Desk data routes (increment 3)."""

from __future__ import annotations

from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


def _free_token(client, email="free@example.com"):
    return client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]


def _entitled_token(client, email="desk@fund.example"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return token


def test_methodology_gated(client):
    assert client.get("/v1/desk/methodology").status_code == 401
    free = _free_token(client)
    r = client.get("/v1/desk/methodology", headers={"Authorization": f"Bearer {free}"})
    assert r.status_code == 403


def test_methodology_lists_lenses(client):
    token = _entitled_token(client)
    r = client.get("/v1/desk/methodology", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["product"] == "CBSRM"
    assert len(body["lenses"]) == 13  # 8 ECB/FRED + VIX + 4 advanced financialdata lenses
    assert {l["id"] for l in body["lenses"]} >= {
        "ECB-CISS-US", "STLFSI4", "SAHM", "EQUITY-VIX",
        "XBORDER-DY", "OPTIONS-TAIL", "FUND-FRAGILITY", "ESG-TRANSITION",
    }


def test_conditions_requires_auth(client):
    assert client.get("/v1/desk/conditions").status_code == 401


def test_conditions_demo_is_wellformed_and_deterministic(client):
    token = _entitled_token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/v1/desk/conditions?source=demo", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema"] == "cbsrm-desk-conditions/1.0.0"
    assert body["source"] == "demo"
    assert body["summary"] == {"total": 13, "live": 13, "unavailable": 0}
    assert len(body["output_sha256"]) == 64
    assert all(rd["status"] == "ok" for rd in body["readings"])
    ids = {rd["id"] for rd in body["readings"]}
    assert {"EQUITY-VIX", "XBORDER-DY", "FUND-FRAGILITY", "ESG-TRANSITION"} <= ids
    # Content hash is over the readings only → stable across calls.
    again = client.get("/v1/desk/conditions?source=demo", headers=h)
    assert again.json()["output_sha256"] == body["output_sha256"]


def test_conditions_rejects_unknown_source(client):
    token = _entitled_token(client)
    r = client.get(
        "/v1/desk/conditions?source=bogus", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 422  # Query pattern validation
