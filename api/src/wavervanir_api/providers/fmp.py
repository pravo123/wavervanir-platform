"""Financial Modeling Prep (FMP) adapter — env-gated, mockable.

Public surface:
  * ``status()`` — pure, no network. Returns ``enabled=False`` if ``FMP_API_KEY``
    is missing.
  * ``fetch_market()`` — accepts an injectable ``client`` (defaults to a
    stub-friendly ``_default_client`` factory). Tests pass a mock client and
    never hit the network.

This adapter does NOT depend on any third-party FMP SDK. It uses ``httpx``
(already a project dependency) so the transitive surface stays small.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from wavervanir_api.providers.base import ProviderStatus, ProviderUnavailableError
from wavervanir_api.schemas import FlowSnapshot, MarketSnapshot


FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


class FmpProvider:
    name = "fmp"

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def status(self, settings) -> ProviderStatus:
        key = (getattr(settings, "fmp_api_key", "") or "").strip()
        if not key:
            return ProviderStatus(
                name="fmp",
                kind="fetch",
                enabled=False,
                reason="FMP_API_KEY env var is not set; provider disabled.",
                requires=["env: FMP_API_KEY"],
            )
        return ProviderStatus(
            name="fmp",
            kind="fetch",
            enabled=True,
            reason="FMP_API_KEY present.",
            requires=["env: FMP_API_KEY"],
        )

    # ------------------------------------------------------------------
    # fetch
    # ------------------------------------------------------------------
    def fetch_market(self, symbol: str, settings, *, client: Any = None) -> MarketSnapshot:
        key = (getattr(settings, "fmp_api_key", "") or "").strip()
        if not key:
            raise ProviderUnavailableError("FMP_API_KEY env var is not set")

        sym = symbol.strip().upper()
        cli = client if client is not None else _default_client()
        url = f"{FMP_BASE_URL}/quote/{sym}"
        params = {"apikey": key}

        payload = _http_get_json(cli, url, params=params)
        return _quote_payload_to_snapshot(sym, payload)

    def fetch_flow(self, symbol: str, settings, *, client: Any = None) -> FlowSnapshot:
        # FMP is not an options-flow provider; surface a clean error rather
        # than fabricating data.
        raise ProviderUnavailableError(
            "fmp provider does not supply options-flow data; use bullflow"
        )


# ----------------------------------------------------------------------
# helpers (kept module-level so tests can inject a stub client easily)
# ----------------------------------------------------------------------


def _default_client() -> Any:
    """Construct an httpx Client. Deferred so tests need not import httpx."""
    import httpx  # type: ignore

    return httpx.Client(timeout=httpx.Timeout(10.0))


def _http_get_json(client: Any, url: str, *, params: dict) -> Any:
    """Tiny wrapper that supports both real httpx clients and test stubs.

    A stub may implement either ``.get(url, params=...).json()`` (httpx-like)
    or a callable signature ``stub(url, params=...) -> dict``.
    """
    if callable(client):
        return client(url, params=params)
    response = client.get(url, params=params)
    # Test stubs may return a plain dict; httpx returns a Response.
    if hasattr(response, "json"):
        return response.json()
    return response


def _quote_payload_to_snapshot(symbol: str, payload: Any) -> MarketSnapshot:
    """Normalize the FMP /quote/{SYM} response into a MarketSnapshot.

    FMP returns a single-element list of dicts with keys including:
      price, volume, change, changesPercentage, timestamp
    """
    if isinstance(payload, list):
        if not payload:
            raise ProviderUnavailableError(f"fmp returned empty payload for {symbol}")
        record = payload[0]
    elif isinstance(payload, dict):
        record = payload
    else:
        raise ProviderUnavailableError(f"fmp returned unexpected payload type for {symbol}")

    price = float(record.get("price", 0.0))
    volume = int(record.get("volume", 0) or 0)
    pct = record.get("changesPercentage")
    day_change_pct = (float(pct) / 100.0) if pct is not None else None
    ts_epoch = record.get("timestamp")
    if isinstance(ts_epoch, (int, float)):
        ts = datetime.fromtimestamp(float(ts_epoch), tz=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    return MarketSnapshot(
        symbol=symbol,
        snapshot_ts=ts,
        price=price,
        volume=volume,
        day_change_pct=day_change_pct,
        source="fmp",
    )
