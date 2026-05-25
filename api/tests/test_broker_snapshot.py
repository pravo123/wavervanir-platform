"""Tests for the sanitized broker-snapshot validator + risk aggregator."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from wavervanir_api.auth import generate_raw_token, provision_key
from wavervanir_api.config import get_settings
from wavervanir_api.providers.broker_snapshot import (
    SnapshotValidationError,
    risk_summary,
    scrub_check,
    validate_snapshot,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_PATH = FIXTURES / "sample_broker_snapshot.json"


def _sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _make_key() -> str:
    raw = generate_raw_token()
    provision_key(raw, tier="paid", stripe_customer_id="cus_test", settings=get_settings())
    return raw


# ----------------------------------------------------------------------
# unit tests
# ----------------------------------------------------------------------


def test_validate_sanitized_sample_passes():
    snap = validate_snapshot(_sample())
    assert snap.account_alias == "paper-main"
    assert len(snap.positions) == 5


def test_validate_rejects_account_number_field():
    payload = _sample()
    payload["account_number"] = "5WG23475"
    with pytest.raises(SnapshotValidationError) as exc:
        validate_snapshot(payload)
    assert "forbidden" in str(exc.value).lower()


def test_validate_rejects_refresh_token_field():
    payload = _sample()
    payload["positions"][0]["refresh_token"] = "RT_LEAKED_TOKEN"
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(payload)


def test_validate_rejects_jwt_shaped_value():
    payload = _sample()
    payload["account_alias"] = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
        "TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ"
    )
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(payload)


def test_validate_rejects_stripe_secret_value():
    # NOTE: assembled at runtime — never write the literal "sk_live_<keylike>"
    # token in source, because GitHub Push Protection (correctly) flags it as
    # a Stripe API key. The assembled string still trips the validator's
    # forbidden-value regex ^sk_(test|live)_[A-Za-z0-9]{8,}$.
    planted = "sk" + "_live_" + "FAKEFAKEFAKEFAKE"
    payload = _sample()
    payload["positions"][0]["symbol"] = planted
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(payload)


def test_validate_rejects_bare_account_number_value():
    payload = _sample()
    payload["account_alias"] = "987654321"  # bare numeric -> account-number shape
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(payload)


def test_validate_rejects_non_dict_root():
    with pytest.raises(SnapshotValidationError):
        validate_snapshot([_sample()])


def test_scrub_check_returns_empty_on_clean_payload():
    assert scrub_check(_sample()) == []


# ----------------------------------------------------------------------
# risk summary numerics
# ----------------------------------------------------------------------


def test_risk_summary_aggregates_correctly():
    snap = validate_snapshot(_sample())
    summary = risk_summary(snap)
    assert summary.n_positions == 5

    # Fixture totals: |19550| + |16484| + |10200| + |2700| + |3400| = 52334
    assert summary.total_gross_exposure_usd == pytest.approx(52334.0)
    # long = 19550 + 16484 + 2700 + 3400 = 42134
    assert summary.total_long_exposure_usd == pytest.approx(42134.0)
    # short = 10200
    assert summary.total_short_exposure_usd == pytest.approx(10200.0)
    # upnl = 312.5 - 84 + 45 + 120 - 50 = 343.5
    assert summary.total_unrealized_pnl_usd == pytest.approx(343.5)
    # largest = 19550 / 52334 ≈ 0.373582
    assert summary.largest_position_pct_of_gross == pytest.approx(0.373582, rel=1e-3)
    # top5 == 1.0 since there are exactly 5 positions
    assert summary.concentration_top5_pct_of_gross == pytest.approx(1.0)

    # asset-class buckets sorted alphabetically: crypto, equity, etf, option
    classes = [b.asset_class for b in summary.by_asset_class]
    assert classes == ["crypto", "equity", "etf", "option"]


def test_risk_summary_empty_portfolio():
    payload = {
        "schema_version": "1.0",
        "snapshot_ts": "2026-05-24T18:00:00Z",
        "account_alias": "empty-paper",
        "base_currency": "USD",
        "positions": [],
    }
    snap = validate_snapshot(payload)
    summary = risk_summary(snap)
    assert summary.n_positions == 0
    assert summary.total_gross_exposure_usd == 0.0
    assert summary.largest_position_pct_of_gross == 0.0
    assert summary.concentration_top5_pct_of_gross == 0.0
    assert summary.by_asset_class == []


# ----------------------------------------------------------------------
# route tests
# ----------------------------------------------------------------------


def test_validate_route_happy_path(client):
    raw = _make_key()
    r = client.post(
        "/v1/data/broker-snapshot/validate",
        json=_sample(),
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["n_positions"] == 5
    assert body["account_alias"] == "paper-main"


def test_validate_route_rejects_account_number(client):
    raw = _make_key()
    payload = _sample()
    payload["account_number"] = "5WG23475"
    r = client.post(
        "/v1/data/broker-snapshot/validate",
        json=payload,
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "snapshot_validation_failed"
    assert any("account" in v.lower() for v in body["detail"]["scrub_violations"])


def test_risk_summary_route_happy_path(client):
    raw = _make_key()
    r = client.post(
        "/v1/data/broker-snapshot/risk-summary",
        json=_sample(),
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_positions"] == 5
    assert body["total_gross_exposure_usd"] == pytest.approx(52334.0)
    assert body["account_alias"] == "paper-main"
    assert any(b["asset_class"] == "option" for b in body["by_asset_class"])


def test_validate_route_requires_auth(client):
    r = client.post("/v1/data/broker-snapshot/validate", json=_sample())
    assert r.status_code == 401


def test_risk_summary_route_requires_auth(client):
    r = client.post("/v1/data/broker-snapshot/risk-summary", json=_sample())
    assert r.status_code == 401
