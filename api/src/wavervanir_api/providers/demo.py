"""Deterministic demo provider — no network, no env, always available."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from wavervanir_api.providers.base import ProviderStatus
from wavervanir_api.schemas import FlowSnapshot, MarketSnapshot


def _seed(symbol: str) -> int:
    """Deterministic per-symbol integer in [0, 2**16)."""
    digest = hashlib.sha256(symbol.upper().encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big")


class DemoProvider:
    name = "demo"

    def status(self, settings) -> ProviderStatus:
        return ProviderStatus(
            name="demo",
            kind="fetch",
            enabled=True,
            reason="Always available — no API key, no network.",
            requires=[],
        )

    def fetch_market(self, symbol: str, settings, *, client=None) -> MarketSnapshot:
        sym = symbol.strip().upper()
        s = _seed(sym)
        price = 10.0 + (s % 1000)        # deterministic but varies per symbol
        change = ((s % 200) - 100) / 1000  # in [-0.10, +0.10)
        volume = 100_000 + (s * 37) % 5_000_000
        # Stable timestamp epoch for determinism in tests.
        ts = datetime(2026, 1, 1, 14, 30, 0, tzinfo=timezone.utc)
        return MarketSnapshot(
            symbol=sym,
            snapshot_ts=ts,
            price=round(price, 2),
            volume=volume,
            day_change_pct=round(change, 4),
            source="demo",
        )

    def fetch_flow(self, symbol: str, settings, *, client=None) -> FlowSnapshot:
        sym = symbol.strip().upper()
        s = _seed(sym)
        call_prem = float((s * 11) % 1_000_000)
        put_prem = float((s * 7) % 1_000_000)
        n_trades = (s % 500) + 10
        # Smart-money in [0, 1] deterministically.
        smart_money = round((s % 100) / 100.0, 3)
        ts = datetime(2026, 1, 1, 14, 30, 0, tzinfo=timezone.utc)
        return FlowSnapshot(
            symbol=sym,
            snapshot_ts=ts,
            call_premium_usd=call_prem,
            put_premium_usd=put_prem,
            smart_money_ratio=smart_money,
            n_trades=n_trades,
            source="demo",
        )
