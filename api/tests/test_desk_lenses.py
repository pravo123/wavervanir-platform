"""Advanced financialdata.net lenses — DY math + demo readings + endpoint."""

from __future__ import annotations

import numpy as np

from wavervanir_api import desk_lenses
from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


# ── Diebold-Yilmaz spillover math (pure, deterministic) ──────────────────────


def test_dy_total_independent_is_low():
    rng = np.random.default_rng(0)
    indep = rng.standard_normal((300, 4))
    assert desk_lenses._dy_total(indep) < 20.0


def test_dy_total_correlated_is_high():
    rng = np.random.default_rng(0)
    factor = rng.standard_normal((300, 1))
    corr = 0.9 * factor + 0.1 * rng.standard_normal((300, 4))
    assert desk_lenses._dy_total(corr) > 60.0


def test_dy_total_in_bounds():
    rng = np.random.default_rng(1)
    val = desk_lenses._dy_total(rng.standard_normal((200, 5)))
    assert 0.0 <= val <= 100.0


# ── demo readings + series (deterministic, offline) ──────────────────────────


def test_all_new_lenses_have_demo_readings():
    for lid in desk_lenses.NEW_LENS_IDS:
        r = desk_lenses.demo_reading(lid)
        assert r["status"] == "ok"
        assert isinstance(r["value"], (int, float))
        assert r["source"] == "financialdata.net"
        assert r["state"]  # band classification present


def test_demo_series_is_deterministic():
    labels = [f"2026-{m:02d}-01" for m in range(1, 13)]
    a = desk_lenses.demo_series("XBORDER-DY", labels)
    b = desk_lenses.demo_series("XBORDER-DY", labels)
    assert a == b
    assert len(a) == 12
    assert a[-1]["value"] == 62.4


# ── gated endpoint ───────────────────────────────────────────────────────────


def _entitled_token(client, email="desk@fund.example"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return token


def test_spillover_lens_endpoint_demo(client):
    t = _entitled_token(client)
    r = client.get("/v1/desk/lens/XBORDER-DY?source=demo", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "XBORDER-DY"
    assert body["unit"] == "% connectedness"
    assert len(body["series"]) == 24
    assert body["stats"]["n"] == 24
    assert body["bands"]


def test_all_new_lenses_endpoint_demo(client):
    t = _entitled_token(client)
    h = {"Authorization": f"Bearer {t}"}
    for lid in desk_lenses.NEW_LENS_IDS:
        r = client.get(f"/v1/desk/lens/{lid}?source=demo", headers=h)
        assert r.status_code == 200, (lid, r.text)
        assert r.json()["stats"]["n"] == 24
