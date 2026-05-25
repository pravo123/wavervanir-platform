"""Options-flow / sentiment snapshot — what Bullflow-style providers emit."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FlowSnapshot(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    snapshot_ts: datetime
    call_premium_usd: float = Field(default=0.0, ge=0.0, description="Total notional premium on call side.")
    put_premium_usd: float = Field(default=0.0, ge=0.0, description="Total notional premium on put side.")
    smart_money_ratio: float | None = Field(
        default=None,
        description="Provider-supplied ratio in [0, 1]; higher = more institutional. None if not provided.",
    )
    n_trades: int = Field(default=0, ge=0, description="Count of option trades in the window.")
    source: str = Field(..., description="Provider id that produced this snapshot.")
