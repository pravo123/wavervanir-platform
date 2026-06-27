"""Governed PipelineRecord — the 'Governed PipelineRecord + audit-chain access' promise.

Covers the module (catalog / build / verify / determinism) and the gated routes
(default-deny, reproducibility, audit-chain linkage, unknown-window 404).
"""

from __future__ import annotations

from wavervanir_api import desk_pipeline
from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


def _free_token(client, email="free-pl@example.com"):
    return client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]


def _entitled_token(client, email="desk-pl@fund.example"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return token


# ── module ──────────────────────────────────────────────────────────────────

def test_catalog_lists_governed_windows():
    cat = desk_pipeline.catalog()
    ids = {w["window_id"] for w in cat["windows"]}
    assert {"2008Q4", "2020Q1", "2023Q1"} <= ids
    assert cat["versions"]["cbsrm"]  # version stamped
    assert all(w["label"] for w in cat["windows"])  # human context present


def test_build_record_is_well_formed():
    rec = desk_pipeline.build_record("2008Q4")
    assert rec["window_id"] == "2008Q4"
    assert rec["phase"]  # phase classification present
    h = rec["manifest"]["hashes"]
    assert len(h["output_sha256"]) == 64 and len(h["payload_sha256"]) == 64
    assert rec["markdown"].startswith("#")  # rendered governed report


def test_record_is_reproducible():
    a = desk_pipeline.build_record("2020Q1")["manifest"]["hashes"]
    b = desk_pipeline.build_record("2020Q1")["manifest"]["hashes"]
    assert a["output_sha256"] == b["output_sha256"]
    assert a["payload_sha256"] == b["payload_sha256"]


def test_distinct_windows_have_distinct_hashes():
    h08 = desk_pipeline.build_record("2008Q4")["manifest"]["hashes"]["output_sha256"]
    h23 = desk_pipeline.build_record("2023Q1")["manifest"]["hashes"]["output_sha256"]
    assert h08 != h23


def test_verify_matches_expected_and_rejects_wrong():
    rec = desk_pipeline.build_record("2008Q4")
    good = rec["manifest"]["hashes"]["output_sha256"]
    assert desk_pipeline.verify_record("2008Q4", good)["reproduced"] is True
    assert desk_pipeline.verify_record("2008Q4", "deadbeef")["reproduced"] is False


def test_unknown_window_raises():
    try:
        desk_pipeline.build_record("1999Q9")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown window")


# ── routes (default-deny gate) ──────────────────────────────────────────────

def test_pipeline_routes_require_auth(client):
    assert client.get("/v1/desk/pipeline/catalog").status_code == 401
    assert client.get("/v1/desk/pipeline/2008Q4").status_code == 401
    assert client.post("/v1/desk/pipeline/verify", json={"window_id": "2008Q4"}).status_code == 401


def test_pipeline_denies_free_user(client):
    free = _free_token(client)
    h = {"Authorization": f"Bearer {free}"}
    assert client.get("/v1/desk/pipeline/catalog", headers=h).status_code == 403


def test_pipeline_catalog_and_record_for_entitled(client):
    token = _entitled_token(client)
    h = {"Authorization": f"Bearer {token}"}
    cat = client.get("/v1/desk/pipeline/catalog", headers=h)
    assert cat.status_code == 200
    assert {w["window_id"] for w in cat.json()["windows"]} >= {"2008Q4", "2020Q1", "2023Q1"}

    rec = client.get("/v1/desk/pipeline/2008Q4", headers=h)
    assert rec.status_code == 200, rec.text
    assert len(rec.json()["manifest"]["hashes"]["output_sha256"]) == 64


def test_pipeline_verify_reproduces_and_logs_to_chain(client):
    token = _entitled_token(client, email="desk-verify@fund.example")
    h = {"Authorization": f"Bearer {token}"}
    built = client.get("/v1/desk/pipeline/2008Q4", headers=h).json()
    sha = built["manifest"]["hashes"]["output_sha256"]

    v = client.post("/v1/desk/pipeline/verify",
                    json={"window_id": "2008Q4", "expected_output_sha256": sha}, headers=h)
    assert v.status_code == 200, v.text
    assert v.json()["reproduced"] is True and v.json()["deterministic"] is True

    # the verification is written to the caller's tamper-evident ledger
    audit = client.get("/v1/desk/audit/export", headers=h).json()
    assert audit["chain_ok"] is True
    assert any("desk/pipeline/verify" in e.get("route", "") for e in audit["events"])


def test_pipeline_unknown_window_404(client):
    token = _entitled_token(client, email="desk-404@fund.example")
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/v1/desk/pipeline/1999Q9", headers=h)
    assert r.status_code == 404
    assert "2008Q4" in r.json()["detail"]["supported"]
