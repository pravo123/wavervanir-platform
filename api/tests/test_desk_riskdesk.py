"""US-index risk desk — SPY/DJI/IWM/QQQ benchmark risk metrics + gate."""

from __future__ import annotations

from wavervanir_api import desk_riskdesk
from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


def _free_token(client, email="free-rd@example.com"):
    return client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]


def _entitled_token(client, email="desk-rd@fund.example"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return token


# ── module (demo is deterministic / offline) ────────────────────────────────

def test_demo_covers_four_benchmarks():
    snap = desk_riskdesk.build(source="demo")
    tickers = [i["ticker"] for i in snap["indices"]]
    assert tickers == ["SPY", "DJI", "IWM", "QQQ"]
    assert snap["summary"] == {"total": 4, "live": 4, "unavailable": 0}
    assert all(i["status"] == "ok" for i in snap["indices"])


def test_demo_is_deterministic():
    a = desk_riskdesk.build(source="demo")
    b = desk_riskdesk.build(source="demo")
    assert a["output_sha256"] == b["output_sha256"]


def test_each_row_has_risk_metrics():
    snap = desk_riskdesk.build(source="demo")
    for i in snap["indices"]:
        for k in ("spot", "chg_1d", "ret_21d", "vol_20d", "vs_sma50", "drawdown", "state"):
            assert k in i, f"{i['ticker']} missing {k}"
    assert snap["posture"]["label"] in {"RISK-ON", "NEUTRAL", "RISK-OFF"}


def test_metrics_math():
    # newest-first synthetic series with a known shape
    closes = [100.0] + [100.0 - i * 0.1 for i in range(1, 300)]
    m = desk_riskdesk._metrics(closes)
    assert m is not None
    assert m["spot"] == 100.0
    assert m["state"] in {"risk-on", "caution", "risk-off"}


def test_metrics_needs_enough_history():
    assert desk_riskdesk._metrics([100.0, 99.0]) is None  # <51 points


# ── route (default-deny gate) ───────────────────────────────────────────────

def test_riskdesk_requires_auth(client):
    assert client.get("/v1/desk/riskdesk").status_code == 401


def test_riskdesk_denies_free_user(client):
    free = _free_token(client)
    r = client.get("/v1/desk/riskdesk?source=demo", headers={"Authorization": f"Bearer {free}"})
    assert r.status_code == 403


def test_riskdesk_serves_entitled_user(client):
    token = _entitled_token(client)
    r = client.get("/v1/desk/riskdesk?source=demo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert {i["ticker"] for i in body["indices"]} == {"SPY", "DJI", "IWM", "QQQ"}
    assert body["posture"]["label"] in {"RISK-ON", "NEUTRAL", "RISK-OFF"}
    assert len(body["output_sha256"]) == 64
