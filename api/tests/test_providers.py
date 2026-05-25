"""Tests for the data-provider abstraction (demo / fmp / bullflow)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wavervanir_api.auth import generate_raw_token, provision_key
from wavervanir_api.config import get_settings
from wavervanir_api.providers import (
    BullflowProvider,
    DemoProvider,
    FmpProvider,
    ProviderUnavailableError,
    get_provider,
    list_providers,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _make_key() -> str:
    raw = generate_raw_token()
    provision_key(raw, tier="paid", stripe_customer_id="cus_test", settings=get_settings())
    return raw


# ----------------------------------------------------------------------
# /v1/data/providers
# ----------------------------------------------------------------------


def test_providers_endpoint_with_no_keys(client):
    raw = _make_key()
    r = client.get("/v1/data/providers", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200, r.text
    body = r.json()
    names = {p["name"]: p for p in body["providers"]}
    assert {"demo", "fmp", "bullflow", "broker_snapshot"} <= set(names)
    # demo + broker_snapshot are always enabled; fmp + bullflow are not (no keys).
    assert names["demo"]["enabled"] is True
    assert names["broker_snapshot"]["enabled"] is True
    assert names["fmp"]["enabled"] is False
    assert names["bullflow"]["enabled"] is False


def test_providers_endpoint_requires_auth(client):
    r = client.get("/v1/data/providers")
    assert r.status_code == 401


# ----------------------------------------------------------------------
# Demo provider determinism
# ----------------------------------------------------------------------


def test_demo_provider_is_deterministic():
    s = get_settings()
    p = DemoProvider()
    one = p.fetch_market("aapl", s)
    two = p.fetch_market("AAPL", s)
    assert one == two
    flow_one = p.fetch_flow("AAPL", s)
    flow_two = p.fetch_flow("AAPL", s)
    assert flow_one == flow_two
    assert one.source == "demo"
    assert flow_one.source == "demo"


def test_demo_snapshot_route(client):
    raw = _make_key()
    r = client.get(
        "/v1/data/snapshot/AAPL?provider=demo&kind=market",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "demo"
    assert body["snapshot"]["symbol"] == "AAPL"
    assert body["snapshot"]["source"] == "demo"


def test_unknown_provider_422(client):
    raw = _make_key()
    r = client.get(
        "/v1/data/snapshot/AAPL?provider=nope&kind=market",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 422


# ----------------------------------------------------------------------
# FMP provider — env-gated, mock client for happy path
# ----------------------------------------------------------------------


def test_fmp_provider_disabled_without_key():
    s = get_settings()
    assert s.fmp_api_key == ""
    status = FmpProvider().status(s)
    assert status.enabled is False
    with pytest.raises(ProviderUnavailableError):
        FmpProvider().fetch_market("AAPL", s)


def test_fmp_route_returns_503_without_key(client):
    raw = _make_key()
    r = client.get(
        "/v1/data/snapshot/AAPL?provider=fmp&kind=market",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["detail"]["error"] == "provider_unavailable"
    assert body["detail"]["provider"] == "fmp"


def test_fmp_provider_mocked_happy_path(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "fmp_test_key_DO_NOT_USE_LIVE")
    get_settings.cache_clear()

    class StubResp:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    class StubClient:
        def __init__(self, payload):
            self.payload = payload
            self.calls: list[tuple] = []

        def get(self, url, params):
            self.calls.append((url, params))
            return StubResp(self.payload)

    stub = StubClient(
        payload=[
            {
                "symbol": "AAPL",
                "price": 195.0,
                "volume": 5_000_000,
                "changesPercentage": 1.25,
                "timestamp": 1_733_961_600,
            }
        ]
    )

    s = get_settings()
    snap = FmpProvider().fetch_market("AAPL", s, client=stub)
    assert snap.symbol == "AAPL"
    assert snap.price == 195.0
    assert snap.volume == 5_000_000
    assert snap.day_change_pct == pytest.approx(0.0125)
    assert snap.source == "fmp"
    assert len(stub.calls) == 1
    assert "/quote/AAPL" in stub.calls[0][0]
    assert stub.calls[0][1]["apikey"] == "fmp_test_key_DO_NOT_USE_LIVE"


def test_fmp_provider_does_not_supply_flow():
    monkeypatch_key = "fmp_test_key_for_flow_attempt"
    import os

    os.environ["FMP_API_KEY"] = monkeypatch_key
    try:
        get_settings.cache_clear()
        with pytest.raises(ProviderUnavailableError):
            FmpProvider().fetch_flow("AAPL", get_settings())
    finally:
        os.environ.pop("FMP_API_KEY", None)
        get_settings.cache_clear()


# ----------------------------------------------------------------------
# Bullflow provider — env OR file
# ----------------------------------------------------------------------


def test_bullflow_disabled_when_no_key_or_file():
    s = get_settings()
    assert s.bullflow_api_key == ""
    assert s.bullflow_data_file == ""
    status = BullflowProvider().status(s)
    assert status.enabled is False


def test_bullflow_file_import_happy_path(monkeypatch):
    monkeypatch.setenv("BULLFLOW_DATA_FILE", str(FIXTURES / "sample_bullflow.json"))
    get_settings.cache_clear()

    status = BullflowProvider().status(get_settings())
    assert status.enabled is True

    snap = BullflowProvider().fetch_flow("AAPL", get_settings())
    assert snap.symbol == "AAPL"
    assert snap.call_premium_usd == 12_500_000.0
    assert snap.put_premium_usd == 4_800_000.0
    assert snap.smart_money_ratio == pytest.approx(0.62)
    assert snap.n_trades == 412
    assert snap.source == "bullflow_file"


def test_bullflow_file_missing_symbol_raises(monkeypatch):
    monkeypatch.setenv("BULLFLOW_DATA_FILE", str(FIXTURES / "sample_bullflow.json"))
    get_settings.cache_clear()
    with pytest.raises(ProviderUnavailableError):
        BullflowProvider().fetch_flow("ZZZZ_NOT_IN_FILE", get_settings())


def test_bullflow_route_via_file(client, monkeypatch):
    monkeypatch.setenv("BULLFLOW_DATA_FILE", str(FIXTURES / "sample_bullflow.json"))
    get_settings.cache_clear()
    raw = _make_key()
    r = client.get(
        "/v1/data/snapshot/SPY?provider=bullflow&kind=flow",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["snapshot"]["symbol"] == "SPY"
    assert body["snapshot"]["source"] == "bullflow_file"


def test_bullflow_api_mocked_happy_path(monkeypatch):
    monkeypatch.setenv("BULLFLOW_API_KEY", "bullflow_test_DO_NOT_USE_LIVE")
    monkeypatch.delenv("BULLFLOW_DATA_FILE", raising=False)
    get_settings.cache_clear()

    captured = {}

    def stub(url, params):
        captured["url"] = url
        captured["params"] = params
        return {
            "symbol": "AAPL",
            "snapshot_ts": "2026-05-24T18:00:00+00:00",
            "call_premium_usd": 99.0,
            "put_premium_usd": 11.0,
            "smart_money_ratio": 0.5,
            "n_trades": 7,
        }

    snap = BullflowProvider().fetch_flow("AAPL", get_settings(), client=stub)
    assert snap.symbol == "AAPL"
    assert snap.call_premium_usd == 99.0
    assert snap.source == "bullflow_file"  # _row_to_flow stamps file source
    assert "/flow/AAPL" in captured["url"]
    assert captured["params"]["apikey"] == "bullflow_test_DO_NOT_USE_LIVE"


def test_get_provider_dispatch():
    assert isinstance(get_provider("demo"), DemoProvider)
    assert isinstance(get_provider("fmp"), FmpProvider)
    assert isinstance(get_provider("bullflow"), BullflowProvider)
    with pytest.raises(KeyError):
        get_provider("totally_made_up")


def test_list_providers_count():
    s = get_settings()
    statuses = list_providers(s)
    assert len(statuses) == 4
    assert {st.name for st in statuses} == {"demo", "fmp", "bullflow", "broker_snapshot"}
