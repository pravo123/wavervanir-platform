"""financialdata.net provider — status + parsing, fully offline (stub client)."""

from __future__ import annotations

import pytest

from wavervanir_api.config import get_settings
from wavervanir_api.providers import FinancialDataProvider, get_provider, list_providers
from wavervanir_api.providers.base import ProviderUnavailableError
from wavervanir_api.providers.financialdata import index_prices, index_quotes


def _settings_with_key(monkeypatch, key="testkey123"):
    monkeypatch.setenv("FINANCIALDATA_API_KEY", key)
    get_settings.cache_clear()
    return get_settings()


def test_status_disabled_without_key(isolated_settings):
    st = FinancialDataProvider().status(get_settings())
    assert st.enabled is False
    assert "FINANCIALDATA_API_KEY" in st.reason


def test_status_enabled_with_key(isolated_settings, monkeypatch):
    st = FinancialDataProvider().status(_settings_with_key(monkeypatch))
    assert st.enabled is True


def test_factory_and_listing_include_provider(isolated_settings):
    assert isinstance(get_provider("financialdata"), FinancialDataProvider)
    names = {s.name for s in list_providers(get_settings())}
    assert "financialdata" in names


def test_fetch_market_parses_quote(isolated_settings, monkeypatch):
    settings = _settings_with_key(monkeypatch)

    captured = {}

    def stub(url, params=None):
        captured["url"] = url
        captured["params"] = params
        return [{
            "trading_symbol": "AAPL",
            "registrant_name": "Apple Inc.",
            "time": "2025-09-02 15:56:00",
            "price": 238.08,
            "change": 8.36,
            "percentage_change": 3.64,
        }]

    snap = FinancialDataProvider().fetch_market("aapl", settings, client=stub)
    assert snap.symbol == "AAPL"
    assert snap.price == pytest.approx(238.08)
    assert snap.day_change_pct == pytest.approx(0.0364)
    assert snap.source == "financialdata"
    # Key is appended, never in code; request hit the right endpoint.
    assert captured["url"].endswith("/stock-quotes")
    assert captured["params"]["key"] == "testkey123"
    assert captured["params"]["identifiers"] == "AAPL"


def test_fetch_market_without_key_raises(isolated_settings):
    with pytest.raises(ProviderUnavailableError):
        FinancialDataProvider().fetch_market("AAPL", get_settings())


def test_index_quotes_helper_filters_records(isolated_settings, monkeypatch):
    settings = _settings_with_key(monkeypatch)

    def stub(url, params=None):
        return [
            {"trading_symbol": "^VIX", "index_name": "CBOE VIX", "time": "2026-06-26 15:00:00",
             "price": 14.2, "change": -0.3, "percentage_change": -2.07},
            {"trading_symbol": "^GSPC", "index_name": "S&P 500", "price": 6600.0,
             "percentage_change": 0.31},
            "garbage",
        ]

    rows = index_quotes(settings, ["^VIX", "^GSPC"], client=stub)
    assert len(rows) == 2
    assert {r["trading_symbol"] for r in rows} == {"^VIX", "^GSPC"}


def test_index_prices_helper(isolated_settings, monkeypatch):
    settings = _settings_with_key(monkeypatch)

    def stub(url, params=None):
        assert url.endswith("/index-prices")
        assert params["identifier"] == "^VIX"
        return [
            {"trading_symbol": "^VIX", "date": "2026-06-26", "close": 20.21},
            {"trading_symbol": "^VIX", "date": "2026-06-25", "close": 19.8},
        ]

    rows = index_prices(settings, "^VIX", client=stub)
    assert rows[0]["close"] == 20.21  # newest first
