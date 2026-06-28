"""US-index risk desk for the Desk terminal.

A native CBSRM view of the four major US equity benchmarks the trading desk
watches — SPY (S&P 500), DJI (Dow Jones), IWM (Russell 2000), QQQ (Nasdaq 100) —
computed from the financialdata.net index-prices feed. For each it reports the
at-a-glance desk read: level, 1-day & 1-month return, 20-day realised volatility
(annualised), drawdown from the trailing-year high, and trend vs the 50-day
average — plus a composite breadth / risk posture (how many benchmarks sit above
their 50-DMA, average drawdown, and small-cap-vs-large-cap leadership).

Honors the CBSRM import boundary: **no VolanX module is imported.** Everything is
recomputed here from public index prices, each value dated, and the whole snapshot
is content-addressed (SHA-256) in the governed CBSRM style.
"""

from __future__ import annotations

import math
from typing import Optional

from wavervanir_api.audit import sha256_of_obj

SCHEMA = "cbsrm-desk-riskdesk/1.0.0"

# (ticker the desk knows, financialdata.net index symbol, full benchmark name).
# The ETF tickers (SPY/DIA/IWM/QQQ) are empty on this data tier, so we use the
# index underlyings — the same four benchmarks.
BENCHMARKS = [
    ("SPY", "^GSPC", "S&P 500"),
    ("DJI", "^DJI", "Dow Jones Industrial Average"),
    ("IWM", "^RUT", "Russell 2000"),
    ("QQQ", "^NDX", "Nasdaq 100"),
]

# Deterministic demo snapshot (offline / tests / preview) — clearly labelled.
_DEMO = {
    "SPY": dict(spot=7357.49, chg_1d=0.21, ret_21d=2.4, vol_20d=12.5, vs_sma50=3.1,
                drawdown=-1.2, state="risk-on", as_of="2026-06-25"),
    "DJI": dict(spot=51920.62, chg_1d=0.15, ret_21d=1.8, vol_20d=11.0, vs_sma50=2.4,
                drawdown=-1.6, state="risk-on", as_of="2026-06-25"),
    "IWM": dict(spot=3007.86, chg_1d=-0.10, ret_21d=0.6, vol_20d=17.8, vs_sma50=-0.8,
                drawdown=-6.4, state="caution", as_of="2026-06-25"),
    "QQQ": dict(spot=29440.32, chg_1d=0.34, ret_21d=3.6, vol_20d=15.2, vs_sma50=4.2,
                drawdown=-0.9, state="risk-on", as_of="2026-06-25"),
}


def _state(drawdown_pct: float, vs_sma50_pct: float) -> str:
    """Per-benchmark risk state from trend + drawdown."""
    if vs_sma50_pct >= 0 and drawdown_pct > -5:
        return "risk-on"
    if vs_sma50_pct < 0 and drawdown_pct <= -10:
        return "risk-off"
    return "caution"


def _metrics(closes: list) -> Optional[dict]:
    """Risk metrics from a newest-first list of closes (needs >= 51 points)."""
    import numpy as np

    c = [float(x) for x in closes if isinstance(x, (int, float))]
    if len(c) < 51:
        return None
    spot = c[0]
    chg_1d = (c[0] / c[1] - 1) * 100 if c[1] else 0.0
    ret_21 = (c[0] / c[21] - 1) * 100 if len(c) > 21 and c[21] else 0.0
    rets = [math.log(c[i] / c[i + 1]) for i in range(20) if c[i + 1] > 0]
    vol = float(np.std(rets, ddof=1)) * math.sqrt(252) * 100 if len(rets) > 2 else 0.0
    sma50 = sum(c[:50]) / 50
    vs_sma = (spot / sma50 - 1) * 100 if sma50 else 0.0
    window = c[:252] if len(c) >= 252 else c
    peak = max(window) if window else spot
    dd = (spot / peak - 1) * 100 if peak else 0.0
    return {
        "spot": round(spot, 2),
        "chg_1d": round(chg_1d, 2),
        "ret_21d": round(ret_21, 2),
        "vol_20d": round(vol, 1),
        "vs_sma50": round(vs_sma, 2),
        "drawdown": round(dd, 2),
        "state": _state(dd, vs_sma),
    }


def _live_one(settings, symbol: str):
    from wavervanir_api.providers.financialdata import index_prices

    rows = index_prices(settings, symbol)
    if not isinstance(rows, list) or not rows:
        return None, None
    closes = [r.get("close") for r in rows]  # newest-first
    as_of = str(rows[0].get("date"))[:10]
    return _metrics(closes), as_of


def _posture(indices: list) -> dict:
    """Composite breadth / risk posture across the available benchmarks."""
    ok = [i for i in indices if i.get("status") == "ok"]
    if not ok:
        return {"label": "unavailable"}
    above = sum(1 for i in ok if i.get("vs_sma50", 0) >= 0)
    avg_dd = sum(i.get("drawdown", 0.0) for i in ok) / len(ok)
    by = {i["ticker"]: i for i in ok}
    lead = None
    if "IWM" in by and "SPY" in by:  # small-cap leadership = risk-on broadening
        lead = round(by["IWM"]["ret_21d"] - by["SPY"]["ret_21d"], 2)
    if above >= 3 and avg_dd > -5:
        label = "RISK-ON"
    elif above <= 1 or avg_dd <= -10:
        label = "RISK-OFF"
    else:
        label = "NEUTRAL"
    return {
        "label": label,
        "breadth_above_50dma": f"{above}/{len(ok)}",
        "avg_drawdown_pct": round(avg_dd, 2),
        "smallcap_leadership_pct": lead,
    }


def build(*, source: str = "live", settings=None, generated_at_utc: Optional[str] = None) -> dict:
    if source == "demo":
        indices = [
            {"ticker": t, "symbol": sym, "name": name, "status": "ok", "demo": True, **_DEMO[t]}
            for (t, sym, name) in BENCHMARKS
        ]
    else:
        indices = []
        for (t, sym, name) in BENCHMARKS:
            try:
                m, as_of = _live_one(settings, sym)
            except Exception:
                m, as_of = None, None
            base = {"ticker": t, "symbol": sym, "name": name}
            if m is None:
                indices.append({**base, "status": "unavailable"})
            else:
                indices.append({**base, "status": "ok", "as_of": as_of, **m})
    posture = _posture(indices)
    ok = [i for i in indices if i.get("status") == "ok"]
    return {
        "schema": SCHEMA,
        "source": source,
        "generated_at_utc": generated_at_utc,
        "indices": indices,
        "posture": posture,
        "summary": {"total": len(indices), "live": len(ok),
                    "unavailable": len(indices) - len(ok)},
        "disclaimer": ("Risk measurement of public benchmark indices — not investment "
                       "advice." if source != "demo" else
                       "DEMONSTRATION readings — synthetic, not live market data."),
        "output_sha256": sha256_of_obj({"indices": indices, "posture": posture}),
    }
