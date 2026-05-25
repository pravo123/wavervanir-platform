"""Reference/market-data snapshot — what FMP-style providers emit."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketSnapshot(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, description="Ticker symbol (uppercased).")
    snapshot_ts: datetime = Field(..., description="UTC timestamp of the snapshot.")
    price: float = Field(..., description="Last/close price in quote currency.")
    volume: int = Field(default=0, ge=0, description="Day volume in shares.")
    day_change_pct: float | None = Field(default=None, description="Day change as decimal (0.012 = +1.2 %).")
    source: str = Field(..., description="Provider id that produced this snapshot.")
