"""Sanitized broker-snapshot validator + risk aggregator.

This module is intentionally **file-only**. It has zero broker SDK imports,
zero network calls, and zero account-ID handling. Its single purpose is to
accept a payload that the operator's *private* workflow has already
sanitized (per ``docs/TASTYWORKS_SNAPSHOT_SCHEMA.md``) and:

  1. Validate the schema strictly (Pydantic).
  2. Refuse the payload if forbidden-field patterns leak through.
  3. Compute a small set of aggregate exposure metrics.

If the payload contains anything that looks like an account number, OAuth
token, refresh token, password, SSN, or any other obvious credential
shape, validation FAILS — the caller must scrub upstream before retrying.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from wavervanir_api.schemas import (
    BrokerPositionSnapshot,
    ByAssetClassExposure,
    PortfolioRiskSummary,
)


# Forbidden field-NAME patterns (case-insensitive). Matched against every
# leaf key in the inbound payload.
FORBIDDEN_FIELD_PATTERNS = [
    r"account[_-]?number",
    r"account[_-]?id",
    r"^cus_",                       # Stripe-shaped customer ids
    r"^acc_",                       # generic account ids
    r"customer[_-]?id",
    r"oauth[_-]?token",
    r"refresh[_-]?token",
    r"access[_-]?token",
    r"bearer[_-]?token",
    r"^password$",
    r"^pwd$",
    r"^pin$",
    r"^ssn$",
    r"tax[_-]?id",
    r"routing[_-]?number",
    r"sort[_-]?code",
    r"\bcvv\b",
    r"card[_-]?number",
]
_FORBIDDEN_FIELD_RE = re.compile(
    "|".join(FORBIDDEN_FIELD_PATTERNS), flags=re.IGNORECASE
)

# Forbidden VALUE patterns (case-insensitive). Matched against every leaf
# string value. Targets at obvious secret shapes.
FORBIDDEN_VALUE_PATTERNS = [
    r"^sk_(test|live)_[A-Za-z0-9]{8,}$",     # Stripe secret keys
    r"^whsec_[A-Za-z0-9]{8,}$",              # Stripe webhook secrets
    r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\b",  # JWT
    r"^[0-9]{8,12}$",                        # bare numeric account-number shape
]
_FORBIDDEN_VALUE_RE = re.compile("|".join(FORBIDDEN_VALUE_PATTERNS))


class SnapshotValidationError(ValueError):
    """Raised when the payload structurally fails or trips a forbidden pattern."""


def scrub_check(payload: Any, *, path: str = "$") -> list[str]:
    """Walk every (key, value) pair; return a list of human-readable violations."""
    violations: list[str] = []

    if isinstance(payload, dict):
        for k, v in payload.items():
            if isinstance(k, str) and _FORBIDDEN_FIELD_RE.search(k):
                violations.append(f"forbidden field name at {path}.{k}")
            violations.extend(scrub_check(v, path=f"{path}.{k}"))
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            violations.extend(scrub_check(item, path=f"{path}[{i}]"))
    elif isinstance(payload, str):
        if _FORBIDDEN_VALUE_RE.search(payload):
            violations.append(f"forbidden value shape at {path}")
    # other scalars: no value check

    return violations


def validate_snapshot(payload: Any) -> BrokerPositionSnapshot:
    """Validate the payload strictly. Raises ``SnapshotValidationError`` on any issue."""
    if not isinstance(payload, dict):
        raise SnapshotValidationError(
            "broker snapshot payload must be a JSON object at the root"
        )

    violations = scrub_check(payload)
    if violations:
        raise SnapshotValidationError(
            "payload tripped sanitization rules:\n  " + "\n  ".join(violations)
        )

    try:
        snap = BrokerPositionSnapshot.model_validate(payload)
    except ValidationError as exc:
        raise SnapshotValidationError(f"schema validation failed: {exc!s}") from exc

    return snap


def risk_summary(snapshot: BrokerPositionSnapshot) -> PortfolioRiskSummary:
    """Compute aggregate exposure from a validated snapshot."""
    positions = snapshot.positions
    n = len(positions)
    if n == 0:
        return PortfolioRiskSummary(
            snapshot_ts=snapshot.snapshot_ts,
            account_alias=snapshot.account_alias,
            base_currency=snapshot.base_currency,
            n_positions=0,
            total_gross_exposure_usd=0.0,
            total_long_exposure_usd=0.0,
            total_short_exposure_usd=0.0,
            total_unrealized_pnl_usd=0.0,
            largest_position_pct_of_gross=0.0,
            concentration_top5_pct_of_gross=0.0,
            by_asset_class=[],
        )

    abs_mv = [abs(p.market_value) for p in positions]
    gross = sum(abs_mv)
    long = sum(p.market_value for p in positions if p.market_value > 0)
    short = -sum(p.market_value for p in positions if p.market_value < 0)
    upnl = sum(p.unrealized_pnl for p in positions)

    # concentration
    sorted_abs = sorted(abs_mv, reverse=True)
    largest_pct = (sorted_abs[0] / gross) if gross > 0 else 0.0
    top5_pct = (sum(sorted_abs[:5]) / gross) if gross > 0 else 0.0

    # per-asset-class
    buckets: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"gross": 0.0, "net": 0.0, "n": 0}
    )
    for p in positions:
        b = buckets[p.asset_class]
        b["gross"] = float(b["gross"]) + abs(p.market_value)
        b["net"] = float(b["net"]) + p.market_value
        b["n"] = int(b["n"]) + 1
    by_asset = [
        ByAssetClassExposure(
            asset_class=cls,  # type: ignore[arg-type]
            gross_exposure_usd=float(b["gross"]),
            net_exposure_usd=float(b["net"]),
            n_positions=int(b["n"]),
        )
        for cls, b in sorted(buckets.items())
    ]

    return PortfolioRiskSummary(
        snapshot_ts=snapshot.snapshot_ts,
        account_alias=snapshot.account_alias,
        base_currency=snapshot.base_currency,
        n_positions=n,
        total_gross_exposure_usd=round(gross, 2),
        total_long_exposure_usd=round(long, 2),
        total_short_exposure_usd=round(short, 2),
        total_unrealized_pnl_usd=round(upnl, 2),
        largest_position_pct_of_gross=round(largest_pct, 6),
        concentration_top5_pct_of_gross=round(top5_pct, 6),
        by_asset_class=by_asset,
    )
