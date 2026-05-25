"""Sanitized broker-snapshot schemas.

These describe the ONLY shape of broker-derived data that may enter the
public ``wavervanir-platform`` service. The contract is:

  * No account numbers / customer ids / OAuth tokens / refresh tokens / SSN.
  * No raw broker-SDK payloads.
  * Position rows carry only symbol + side + size + valuation fields.

The intent is that an operator's PRIVATE workflow exports a redacted JSON or
CSV file from their broker, and this service accepts that file for
risk-aggregation purposes only. Direct broker connectivity is out of scope
and explicitly NOT permitted from this repo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AssetClass = Literal["equity", "option", "future", "etf", "crypto", "fx", "other"]


class Position(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    asset_class: AssetClass = "equity"
    quantity: float = Field(..., description="Signed quantity; +long, -short.")
    mark_price: float = Field(..., ge=0.0, description="Last mark / fair price per unit.")
    market_value: float = Field(..., description="Signed market value in USD (sign matches quantity).")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized PnL in USD.")


class BrokerPositionSnapshot(BaseModel):
    """Sanitized portfolio snapshot. Never accepts account_number / token fields."""

    schema_version: Literal["1.0"] = "1.0"
    snapshot_ts: datetime
    # An ALIAS — a non-identifying label like "paper-main" or "live-cash-a".
    # Must NEVER be the broker's actual account number.
    account_alias: str = Field(..., min_length=1, max_length=64)
    base_currency: str = Field(default="USD", min_length=3, max_length=8)
    positions: list[Position] = Field(default_factory=list)


class ByAssetClassExposure(BaseModel):
    asset_class: AssetClass
    gross_exposure_usd: float
    net_exposure_usd: float
    n_positions: int


class PortfolioRiskSummary(BaseModel):
    """Aggregate exposure metrics computed from a BrokerPositionSnapshot."""

    schema_version: Literal["1.0"] = "1.0"
    snapshot_ts: datetime
    account_alias: str
    base_currency: str = "USD"

    n_positions: int = Field(..., ge=0)
    total_gross_exposure_usd: float = Field(..., ge=0.0)
    total_long_exposure_usd: float = Field(..., ge=0.0)
    total_short_exposure_usd: float = Field(..., ge=0.0)
    total_unrealized_pnl_usd: float

    largest_position_pct_of_gross: float = Field(
        ..., ge=0.0, le=1.0, description="|MV| of the largest position / total gross."
    )
    concentration_top5_pct_of_gross: float = Field(
        ..., ge=0.0, le=1.0, description="|MV| of top 5 positions / total gross."
    )
    by_asset_class: list[ByAssetClassExposure] = Field(default_factory=list)
