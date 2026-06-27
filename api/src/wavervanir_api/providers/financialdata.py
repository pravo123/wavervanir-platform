"""financialdata.net adapter — env-gated, mockable.

Public surface:
  * ``FinancialDataProvider`` — the by-symbol ``DataProvider`` (``status`` +
    ``fetch_market`` via ``/stock-quotes``). ``status()`` is pure (no network)
    and reports ``enabled=False`` when ``FINANCIALDATA_API_KEY`` is unset.
  * ``index_quotes`` / ``get_json`` — thin REST helpers the CBSRM lenses use to
    pull index / forex / fundamentals data. The http client is always injectable
    so tests never touch the network.

API: ``https://financialdata.net/api/v1/<endpoint>?key=…`` returning JSON arrays
of records (see the integration guide). This adapter uses ``httpx`` only — no
third-party SDK.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from wavervanir_api.providers.base import ProviderStatus, ProviderUnavailableError
from wavervanir_api.schemas import FlowSnapshot, MarketSnapshot

FINANCIALDATA_BASE_URL = "https://financialdata.net/api/v1"


def _key(settings) -> str:
    return (getattr(settings, "financialdata_api_key", "") or "").strip()


class FinancialDataProvider:
    name = "financialdata"

    def status(self, settings) -> ProviderStatus:
        if not _key(settings):
            return ProviderStatus(
                name="financialdata",
                kind="fetch",
                enabled=False,
                reason="FINANCIALDATA_API_KEY env var is not set; provider disabled.",
                requires=["env: FINANCIALDATA_API_KEY"],
            )
        return ProviderStatus(
            name="financialdata",
            kind="fetch",
            enabled=True,
            reason="FINANCIALDATA_API_KEY present.",
            requires=["env: FINANCIALDATA_API_KEY"],
        )

    def fetch_market(self, symbol: str, settings, *, client: Any = None) -> MarketSnapshot:
        if not _key(settings):
            raise ProviderUnavailableError("FINANCIALDATA_API_KEY env var is not set")
        sym = symbol.strip().upper()
        payload = get_json(settings, "stock-quotes", params={"identifiers": sym}, client=client)
        return _quote_payload_to_snapshot(sym, payload)

    def fetch_flow(self, symbol: str, settings, *, client: Any = None) -> FlowSnapshot:
        raise ProviderUnavailableError(
            "financialdata provider does not supply options-flow data"
        )


# ── REST helpers (module-level so lenses + tests can inject a stub client) ──


def _default_client() -> Any:
    import httpx  # type: ignore

    return httpx.Client(timeout=httpx.Timeout(10.0))


def get_json(settings, endpoint: str, *, params: dict, client: Any = None) -> Any:
    """GET ``/<endpoint>`` with the API key appended. Returns parsed JSON.

    A stub ``client`` may be either callable ``stub(url, params=...) -> data`` or
    httpx-like ``stub.get(url, params=...).json()``.
    """
    key = _key(settings)
    if not key:
        raise ProviderUnavailableError("FINANCIALDATA_API_KEY env var is not set")
    url = f"{FINANCIALDATA_BASE_URL}/{endpoint.lstrip('/')}"
    q = {**params, "key": key}
    cli = client if client is not None else _default_client()
    if callable(cli):
        return cli(url, params=q)
    resp = cli.get(url, params=q)
    return resp.json() if hasattr(resp, "json") else resp


def index_quotes(settings, identifiers: list[str], *, client: Any = None) -> list[dict]:
    """Real-time quotes for one or more index symbols (e.g. ``^VIX``, ``^GSPC``).

    Note: the real-time quotes feed is Premium and market-hours only; for a
    reliable latest reading prefer :func:`index_prices` (daily close, Standard).
    """
    ids = ",".join(identifiers)
    data = get_json(settings, "index-quotes", params={"identifiers": ids}, client=client)
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def index_prices(settings, identifier: str, *, offset: int = 0, client: Any = None) -> list[dict]:
    """Daily OHLCV for an index, newest record first (e.g. ``^VIX``)."""
    data = get_json(
        settings, "index-prices", params={"identifier": identifier, "offset": offset}, client=client
    )
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _quote_payload_to_snapshot(symbol: str, payload: Any) -> MarketSnapshot:
    """Normalize a ``/stock-quotes`` record into a MarketSnapshot.

    Record keys: trading_symbol, time ("YYYY-MM-DD HH:MM:SS", EST), price,
    change, percentage_change. (Quotes carry no volume field.)
    """
    record: Any = None
    if isinstance(payload, list) and payload:
        record = payload[0]
    elif isinstance(payload, dict):
        record = payload
    if not isinstance(record, dict):
        raise ProviderUnavailableError(f"financialdata returned no quote for {symbol}")

    price = float(record.get("price", 0.0) or 0.0)
    pct = record.get("percentage_change")
    day_change_pct = (float(pct) / 100.0) if isinstance(pct, (int, float)) else None
    ts_raw = record.get("time")
    try:
        ts = datetime.strptime(str(ts_raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        ts = datetime.now(timezone.utc)

    return MarketSnapshot(
        symbol=symbol,
        snapshot_ts=ts,
        price=price,
        volume=0,
        day_change_pct=day_change_pct,
        source="financialdata",
    )
