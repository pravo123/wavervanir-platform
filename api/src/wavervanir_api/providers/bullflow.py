"""Bullflow flow/sentiment adapter — env-gated OR local file import.

Two modes, picked in order:

  1. **File mode** — ``BULLFLOW_DATA_FILE`` env var points at a local JSON
     (preferred) or CSV file with rows ``[{symbol, ts, call_premium_usd,
     put_premium_usd, smart_money_ratio?, n_trades?}, …]``. No network.
  2. **API mode** — ``BULLFLOW_API_KEY`` env var is set; the adapter uses
     an injectable httpx-like client. Tests pass a stub; live calls never
     happen in CI.

If neither is configured, the provider reports ``enabled=False`` and
raises ``ProviderUnavailableError`` on fetch.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from wavervanir_api.providers.base import ProviderStatus, ProviderUnavailableError
from wavervanir_api.schemas import FlowSnapshot, MarketSnapshot


BULLFLOW_BASE_URL = "https://api.bullflow.example/v1"


class BullflowProvider:
    name = "bullflow"

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def status(self, settings) -> ProviderStatus:
        file_path = (getattr(settings, "bullflow_data_file", "") or "").strip()
        key = (getattr(settings, "bullflow_api_key", "") or "").strip()
        if file_path:
            return ProviderStatus(
                name="bullflow",
                kind="fetch",
                enabled=Path(file_path).is_file(),
                reason=(
                    f"BULLFLOW_DATA_FILE points at {file_path!r} (file present)."
                    if Path(file_path).is_file()
                    else f"BULLFLOW_DATA_FILE points at {file_path!r} but the file is missing."
                ),
                requires=["env: BULLFLOW_DATA_FILE → local JSON/CSV"],
            )
        if key:
            return ProviderStatus(
                name="bullflow",
                kind="fetch",
                enabled=True,
                reason="BULLFLOW_API_KEY present.",
                requires=["env: BULLFLOW_API_KEY"],
            )
        return ProviderStatus(
            name="bullflow",
            kind="fetch",
            enabled=False,
            reason="Neither BULLFLOW_DATA_FILE nor BULLFLOW_API_KEY is set.",
            requires=["env: BULLFLOW_DATA_FILE OR BULLFLOW_API_KEY"],
        )

    # ------------------------------------------------------------------
    # fetch
    # ------------------------------------------------------------------
    def fetch_flow(self, symbol: str, settings, *, client: Any = None) -> FlowSnapshot:
        sym = symbol.strip().upper()

        # File mode wins.
        file_path = (getattr(settings, "bullflow_data_file", "") or "").strip()
        if file_path:
            return _flow_from_file(sym, Path(file_path))

        key = (getattr(settings, "bullflow_api_key", "") or "").strip()
        if not key:
            raise ProviderUnavailableError(
                "bullflow provider is disabled — set BULLFLOW_DATA_FILE or BULLFLOW_API_KEY"
            )

        cli = client if client is not None else _default_client()
        url = f"{BULLFLOW_BASE_URL}/flow/{sym}"
        params = {"apikey": key}
        payload = _http_get_json(cli, url, params=params)
        return _api_payload_to_flow(sym, payload)

    def fetch_market(self, symbol: str, settings, *, client: Any = None) -> MarketSnapshot:
        # Bullflow is flow-only, not a quotes provider.
        raise ProviderUnavailableError(
            "bullflow provider does not supply quote data; use fmp or demo"
        )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _default_client() -> Any:
    import httpx  # type: ignore

    return httpx.Client(timeout=httpx.Timeout(10.0))


def _http_get_json(client: Any, url: str, *, params: dict) -> Any:
    if callable(client):
        return client(url, params=params)
    response = client.get(url, params=params)
    if hasattr(response, "json"):
        return response.json()
    return response


def _flow_from_file(symbol: str, path: Path) -> FlowSnapshot:
    if not path.is_file():
        raise ProviderUnavailableError(f"bullflow file not found: {path}")

    rows: Iterable[dict]
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "rows" in data:
            rows = data["rows"]
        elif isinstance(data, list):
            rows = data
        else:
            raise ProviderUnavailableError(
                f"bullflow JSON file must be a list of rows or {{'rows': […]}}"
            )
    elif path.suffix.lower() in (".csv", ".tsv"):
        delim = "\t" if path.suffix.lower() == ".tsv" else ","
        with path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter=delim))
    else:
        raise ProviderUnavailableError(
            f"bullflow file must be .json/.csv/.tsv; got {path.suffix!r}"
        )

    match = None
    for row in rows:
        if str(row.get("symbol", "")).upper() == symbol:
            match = row
            break
    if match is None:
        raise ProviderUnavailableError(f"bullflow file has no row for {symbol}")

    return _row_to_flow(symbol, match)


def _row_to_flow(symbol: str, row: dict) -> FlowSnapshot:
    ts_raw = row.get("snapshot_ts") or row.get("ts")
    if isinstance(ts_raw, (int, float)):
        ts = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc)
    elif isinstance(ts_raw, str):
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    else:
        ts = datetime.now(timezone.utc)

    smr = row.get("smart_money_ratio")
    smr_val = float(smr) if smr not in (None, "", "null") else None

    return FlowSnapshot(
        symbol=symbol,
        snapshot_ts=ts,
        call_premium_usd=float(row.get("call_premium_usd", 0) or 0),
        put_premium_usd=float(row.get("put_premium_usd", 0) or 0),
        smart_money_ratio=smr_val,
        n_trades=int(row.get("n_trades", 0) or 0),
        source="bullflow_file",
    )


def _api_payload_to_flow(symbol: str, payload: Any) -> FlowSnapshot:
    if isinstance(payload, list):
        if not payload:
            raise ProviderUnavailableError(f"bullflow returned empty payload for {symbol}")
        record = payload[0]
    elif isinstance(payload, dict):
        record = payload
    else:
        raise ProviderUnavailableError(
            f"bullflow returned unexpected payload type for {symbol}"
        )
    return _row_to_flow(symbol, record)
