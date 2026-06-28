"""Quant Cockpit (Risk Desk) — global watchlist grid + any-symbol institutional profile."""

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


# ── module: watchlist groups (demo is deterministic / offline) ──────────────

def test_groups_cover_global_assets():
    ids = {g["id"] for g in desk_riskdesk.available_groups()}
    assert {"us-benchmarks", "global-indices", "fx-majors", "commodities",
            "us-megacaps", "crypto"} <= ids


def test_global_indices_group_has_world_benchmarks():
    snap = desk_riskdesk.build(group="global-indices", source="demo")
    tickers = {r["ticker"] for r in snap["rows"]}
    assert {"FTSE", "DAX", "NIKKEI", "STI", "SENSEX"} <= tickers  # incl. Singapore + India
    assert all("var_95_1d" in r and "beta" in r for r in snap["rows"])


def test_build_is_deterministic_in_demo():
    a = desk_riskdesk.build(group="commodities", source="demo")
    b = desk_riskdesk.build(group="commodities", source="demo")
    assert a["output_sha256"] == b["output_sha256"]
    assert a["group"] == "commodities" and a["group_equity"] is False


def test_unknown_group_falls_back_to_default():
    snap = desk_riskdesk.build(group="does-not-exist", source="demo")
    assert snap["group"] == "us-benchmarks"


def test_resolver_picks_endpoints():
    assert desk_riskdesk._resolve_kinds("^GSPC") == ["index"]
    assert desk_riskdesk._resolve_kinds("EURUSD")[0] == "forex"
    assert desk_riskdesk._resolve_kinds("GC")[0] == "commodity"
    assert desk_riskdesk._resolve_kinds("BTCUSD")[0] == "crypto"
    assert desk_riskdesk._resolve_kinds("AAPL")[0] == "stock"


# ── routes (default-deny gate) ──────────────────────────────────────────────

def test_cockpit_requires_auth(client):
    assert client.get("/v1/desk/riskdesk").status_code == 401
    assert client.get("/v1/desk/riskdesk/symbol/SPY").status_code == 401


def test_cockpit_denies_free_user(client):
    free = _free_token(client)
    h = {"Authorization": f"Bearer {free}"}
    assert client.get("/v1/desk/riskdesk?source=demo", headers=h).status_code == 403


def test_cockpit_grid_for_entitled(client):
    token = _entitled_token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/v1/desk/riskdesk?group=fx-majors&source=demo", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["group"] == "fx-majors"
    assert {x["ticker"] for x in body["rows"]} >= {"EURUSD", "USDSGD"}
    assert len(body["output_sha256"]) == 64


def test_cockpit_symbol_route_gated(client):
    free = _free_token(client, email="free-sym@example.com")
    assert client.get(
        "/v1/desk/riskdesk/symbol/SPY", headers={"Authorization": f"Bearer {free}"}
    ).status_code == 403


# ── institutional profile math (offline, synthetic series) ──────────────────

def test_profile_stats_on_synthetic_series():
    import math

    # 300 newest-first (date, close) points with a gentle trend + wiggle
    pairs = [(f"d{i}", 100.0 + (300 - i) * 0.1 + 2 * math.sin(i * 0.3)) for i in range(300)]
    st = desk_riskdesk._ret_stats(pairs, None, None)  # no market -> beta None
    assert st["points"] == 300
    assert st["ann_vol_pct"] >= 0 and st["ewma_vol_pct"] >= 0
    assert st["beta_sp"] is None
    # full VaR/CVaR table: {1D,5D,10D} x {95%,99%}
    assert len(st["var_table"]) == 6
    horizons = {(r["horizon"], r["confidence"]) for r in st["var_table"]}
    assert ("5D", "95%") in horizons and ("1D", "99%") in horizons
    # VaR/CVaR are non-negative losses and CVaR >= VaR at the same cut
    for r in st["var_table"]:
        assert r["var_pct"] >= 0 and r["cvar_pct"] >= r["var_pct"] - 1e-6


def test_stress_is_beta_scaled():
    stress = desk_riskdesk._stress(spot=100.0, beta_m=1.5, vix_beta=None)
    by = {s["scenario"]: s for s in stress}
    risk_off = next(s for k, s in by.items() if "S&P −5%" in k)
    assert abs(risk_off["move_pct"] - (1.5 * -5.0)) < 1e-6
    assert abs(risk_off["implied_price"] - 100.0 * (1 + (1.5 * -5.0) / 100)) < 0.01
