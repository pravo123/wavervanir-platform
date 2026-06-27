"""Desk portfolio risk analyzer — gated reuse of the broker-snapshot engine."""

from __future__ import annotations

from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


def _free_token(client, email="free@x.com"):
    return client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]


def _entitled_token(client, email="desk@fund.example"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return token


def test_portfolio_requires_auth(client):
    assert client.post("/v1/desk/portfolio", json={}).status_code == 401
    assert client.get("/v1/desk/portfolio/sample").status_code == 401


def test_portfolio_denies_free_user(client):
    h = {"Authorization": f"Bearer {_free_token(client)}"}
    assert client.get("/v1/desk/portfolio/sample", headers=h).status_code == 403
    assert client.post("/v1/desk/portfolio", json={}, headers=h).status_code == 403


def test_portfolio_sample_then_risk_summary(client):
    h = {"Authorization": f"Bearer {_entitled_token(client)}"}
    sample = client.get("/v1/desk/portfolio/sample", headers=h)
    assert sample.status_code == 200
    snap = sample.json()
    assert snap["account_alias"] == "desk-demo"

    r = client.post("/v1/desk/portfolio", json=snap, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["n_positions"] == 6
    assert j["total_unrealized_pnl_usd"] == 48600.0
    assert j["total_gross_exposure_usd"] > 0
    assert 0.0 <= j["largest_position_pct_of_gross"] <= 1.0
    assert {a["asset_class"] for a in j["by_asset_class"]} == {
        "equity", "etf", "option", "crypto", "fx"
    }


def test_portfolio_rejects_account_number(client):
    h = {"Authorization": f"Bearer {_entitled_token(client)}"}
    bad = {
        "schema_version": "1.0",
        "snapshot_ts": "2026-06-26T20:00:00Z",
        "account_alias": "x",
        "positions": [{
            "symbol": "AAPL", "asset_class": "equity", "quantity": 1, "mark_price": 1.0,
            "market_value": 1.0, "unrealized_pnl": 0.0, "account_number": "123456789",
        }],
    }
    r = client.post("/v1/desk/portfolio", json=bad, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "snapshot_validation_failed"
