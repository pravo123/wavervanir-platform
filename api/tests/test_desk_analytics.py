"""Per-lens BI analytics — stats engine + gated endpoint."""

from __future__ import annotations

from wavervanir_api import desk_analytics
from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


# ── stats engine (pure) ──────────────────────────────────────────────────────


def test_stats_on_known_series():
    s = desk_analytics._stats([10.0, 20.0, 30.0])
    assert s["n"] == 3
    assert s["current"] == 30.0
    assert s["min"] == 10.0 and s["max"] == 30.0
    assert s["mean"] == 20.0
    assert s["percentile"] == 1.0  # current is the max
    assert s["change"] == 10.0
    assert s["z"] > 0


def test_stats_empty_is_none():
    assert desk_analytics._stats([]) is None


def test_demo_series_is_deterministic():
    a = desk_analytics._demo_series("EQUITY-VIX")
    b = desk_analytics._demo_series("EQUITY-VIX")
    assert a == b
    assert len(a) == 24
    assert a[-1]["value"] == 14.2  # ends at the representative current


def test_every_lens_has_metadata():
    # 8 cbsrm lenses + VIX + 4 advanced financialdata lenses.
    assert len(desk_analytics.LENS_META) == 13
    assert "EQUITY-VIX" in desk_analytics.LENS_META
    assert "XBORDER-DY" in desk_analytics.LENS_META
    assert desk_analytics.LENS_META["EQUITY-VIX"]["source"] == "financialdata.net"


# ── endpoint (gated) ─────────────────────────────────────────────────────────


def _entitled_token(client, email="desk@fund.example"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return token


def test_lens_endpoint_requires_auth(client):
    assert client.get("/v1/desk/lens/EQUITY-VIX").status_code == 401


def test_lens_endpoint_denies_free_user(client):
    t = client.post(
        "/auth/register", json={"email": "free@x.com", "password": "strong-pass-123"}
    ).json()["access_token"]
    r = client.get("/v1/desk/lens/EQUITY-VIX?source=demo", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


def test_lens_endpoint_unknown_404(client):
    t = _entitled_token(client)
    r = client.get("/v1/desk/lens/NOPE?source=demo", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 404


def test_lens_demo_returns_series_and_stats(client):
    t = _entitled_token(client)
    r = client.get("/v1/desk/lens/EQUITY-VIX?source=demo", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "EQUITY-VIX"
    assert body["source"] == "financialdata.net"
    assert len(body["series"]) == 24
    assert body["stats"]["n"] == 24
    assert body["bands"]  # VIX has regime bands
    assert len(body["output_sha256"]) == 64


def test_lens_demo_deterministic_hash(client):
    t = _entitled_token(client)
    h = {"Authorization": f"Bearer {t}"}
    a = client.get("/v1/desk/lens/STLFSI4?source=demo", headers=h).json()
    b = client.get("/v1/desk/lens/STLFSI4?source=demo", headers=h).json()
    assert a["output_sha256"] == b["output_sha256"]
