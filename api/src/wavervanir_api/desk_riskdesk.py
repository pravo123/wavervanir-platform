"""Quant Cockpit (the Risk Desk) — institutional risk for any symbol the feed has.

A global, cross-asset risk cockpit: curated watchlist groups of the instruments
banks and hedge funds actually watch — US & world equity indices, FX majors,
commodities, US mega-caps, crypto — plus an **any-symbol** search so a desk can
pull the risk read for whatever ticker the financialdata.net feed supports.

For every instrument it computes the desk-grade risk read: level, 1-day & 1-month
return, 20-day annualised realised volatility, 1-day 95% historical Value-at-Risk,
beta to the S&P 500, maximum drawdown from the trailing-year high, and trend vs the
50- and 200-day moving averages — plus a composite group posture.

Honors the CBSRM import boundary: **no VolanX module is imported.** Every number is
recomputed here from public prices, dated, and content-addressed (SHA-256).
"""

from __future__ import annotations

import math
from typing import Optional

from wavervanir_api.audit import sha256_of_obj

SCHEMA = "cbsrm-desk-cockpit/3.0.0"
_MARKET = "^GSPC"  # beta reference (S&P 500)
VAR_WINDOW = 60
VAR_CONFIDENCE = 0.95

# Curated global watchlists (every symbol probed live on this feed). Each member
# is (ticker, feed_symbol, name, kind). ``kind`` picks the price endpoint.
GROUPS = [
    {"id": "us-benchmarks", "label": "US Benchmarks", "equity": True, "members": [
        ("SPY", "^GSPC", "S&P 500", "index"), ("DJI", "^DJI", "Dow Jones", "index"),
        ("IWM", "^RUT", "Russell 2000", "index"), ("QQQ", "^NDX", "Nasdaq 100", "index"),
    ]},
    {"id": "global-indices", "label": "Global Indices", "equity": True, "members": [
        ("FTSE", "^FTSE", "UK · FTSE 100", "index"), ("DAX", "^GDAXI", "Germany · DAX", "index"),
        ("CAC", "^FCHI", "France · CAC 40", "index"), ("STOXX", "^STOXX50E", "Europe · Euro Stoxx 50", "index"),
        ("NIKKEI", "^N225", "Japan · Nikkei 225", "index"), ("HSI", "^HSI", "Hong Kong · Hang Seng", "index"),
        ("STI", "^STI", "Singapore · STI", "index"), ("ASX", "^AXJO", "Australia · ASX 200", "index"),
        ("SENSEX", "^BSESN", "India · Sensex", "index"), ("NIFTY", "^NSEI", "India · Nifty 50", "index"),
        ("KOSPI", "^KS11", "Korea · KOSPI", "index"), ("TAIEX", "^TWII", "Taiwan · TAIEX", "index"),
        ("TSX", "^GSPTSE", "Canada · S&P/TSX", "index"),
    ]},
    {"id": "fx-majors", "label": "FX Majors", "equity": False, "members": [
        ("EURUSD", "EURUSD", "Euro / USD", "forex"), ("USDJPY", "USDJPY", "USD / Yen", "forex"),
        ("GBPUSD", "GBPUSD", "Sterling / USD", "forex"), ("USDCHF", "USDCHF", "USD / Swiss", "forex"),
        ("USDSGD", "USDSGD", "USD / Singapore $", "forex"), ("AUDUSD", "AUDUSD", "Aussie / USD", "forex"),
        ("USDHKD", "USDHKD", "USD / HK$", "forex"),
    ]},
    {"id": "commodities", "label": "Commodities", "equity": False, "members": [
        ("GOLD", "GC", "Gold", "commodity"), ("WTI", "CL", "WTI Crude", "commodity"),
        ("BRENT", "BZ", "Brent Crude", "commodity"), ("SILVER", "SI", "Silver", "commodity"),
        ("COPPER", "HG", "Copper", "commodity"), ("NATGAS", "NG", "Natural Gas", "commodity"),
    ]},
    {"id": "us-megacaps", "label": "US Mega-Caps", "equity": True, "members": [
        ("AAPL", "AAPL", "Apple", "stock"), ("MSFT", "MSFT", "Microsoft", "stock"),
        ("NVDA", "NVDA", "NVIDIA", "stock"), ("AMZN", "AMZN", "Amazon", "stock"),
        ("GOOG", "GOOG", "Alphabet", "stock"), ("META", "META", "Meta Platforms", "stock"),
        ("TSLA", "TSLA", "Tesla", "stock"), ("AVGO", "AVGO", "Broadcom", "stock"),
    ]},
    {"id": "crypto", "label": "Crypto", "equity": False, "members": [
        ("BTC", "BTCUSD", "Bitcoin", "crypto"), ("ETH", "ETHUSD", "Ethereum", "crypto"),
    ]},
]
_GROUP_BY_ID = {g["id"]: g for g in GROUPS}
DEFAULT_GROUP = "us-benchmarks"

_ENDPOINT = {"index": None, "forex": "forex-prices", "commodity": "commodity-prices",
             "crypto": "crypto-prices", "stock": "stock-prices", "etf": "etf-prices"}
_COMMODITY_CODES = {"GC", "CL", "BZ", "SI", "HG", "NG", "PL", "PA", "ZC", "ZW", "ZS", "KC", "SB", "CT"}
_CRYPTO_BASES = {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "LTC", "AVAX", "DOT"}

METHODOLOGY = {
    "vol_20d": "Annualised realised volatility: stdev of 20 daily log returns x sqrt(252).",
    "var_95_1d": "Historical 1-day 95% VaR: 5th-percentile of the last 60 daily returns (no normality assumption), shown as a positive loss.",
    "beta": "OLS beta to the S&P 500 (^GSPC) over up to 60 date-aligned daily returns (cross-asset: gold/FX show their equity-beta).",
    "drawdown": "Decline from the trailing 252-day high (max drawdown, 1y).",
    "trend": "Close vs the 50- and 200-day simple moving averages.",
    "source": "financialdata.net — index / stock / etf / forex / commodity / crypto prices, daily close.",
    "coverage": "Curated global watchlists plus any symbol the feed supports (^index, FX pair, commodity code, CRYPTO-USD, stock/ETF ticker).",
    "disclaimer": "Risk measurement of public instruments — not investment advice.",
}


def available_groups() -> list[dict]:
    return [{"id": g["id"], "label": g["label"], "equity": g["equity"],
             "count": len(g["members"])} for g in GROUPS]


def _state(drawdown_pct: float, vs_sma50_pct: float) -> str:
    if vs_sma50_pct >= 0 and drawdown_pct > -5:
        return "risk-on"
    if vs_sma50_pct < 0 and drawdown_pct <= -10:
        return "risk-off"
    return "caution"


def _fetch(settings, symbol: str, kind: str):
    """Newest-first [(date, close)] for a symbol of the given kind, or None."""
    from wavervanir_api.providers.financialdata import get_json, index_prices

    if kind == "index":
        rows = index_prices(settings, symbol)
    else:
        ep = _ENDPOINT.get(kind, "stock-prices")
        rows = get_json(settings, ep, params={"identifier": symbol, "offset": 0})
    if not isinstance(rows, list) or not rows:
        return None
    pairs = [(str(r.get("date"))[:10], float(r["close"]))
             for r in rows if isinstance(r.get("close"), (int, float))]
    return pairs or None


def _safe_fetch(settings, symbol: str, kind: str):
    try:
        return _fetch(settings, symbol, kind)
    except Exception:
        return None


def _resolve_kinds(symbol: str) -> list[str]:
    """Best-effort ordered list of endpoints to try for an arbitrary symbol."""
    s = symbol.upper()
    if s.startswith("^"):
        return ["index"]
    if s in _COMMODITY_CODES:
        return ["commodity", "stock"]
    if len(s) >= 6 and s.endswith("USD") and s[:-3] in _CRYPTO_BASES:
        return ["crypto", "forex"]
    if len(s) == 6 and s.isalpha():
        return ["forex", "stock"]
    return ["stock", "etf"]


def _fetch_any(settings, symbol: str):
    """Resolve + fetch an arbitrary symbol. Returns (pairs, kind) or (None, None)."""
    for kind in _resolve_kinds(symbol):
        pairs = _safe_fetch(settings, symbol, kind)
        if pairs:
            return pairs, kind
    return None, None


def _metrics(pairs: list) -> Optional[dict]:
    import numpy as np

    c = [px for _, px in pairs]  # newest-first
    if len(c) < 51:
        return None
    spot = c[0]
    chg_1d = (c[0] / c[1] - 1) * 100 if c[1] else 0.0
    ret_21 = (c[0] / c[21] - 1) * 100 if len(c) > 21 and c[21] else 0.0
    log_rets = [math.log(c[i] / c[i + 1]) for i in range(20) if c[i + 1] > 0]
    vol = float(np.std(log_rets, ddof=1)) * math.sqrt(252) * 100 if len(log_rets) > 2 else 0.0
    simple = [(c[i] / c[i + 1] - 1) for i in range(min(VAR_WINDOW, len(c) - 1)) if c[i + 1] > 0]
    var95 = max(0.0, -float(np.percentile(simple, (1 - VAR_CONFIDENCE) * 100)) * 100) if simple else 0.0
    sma50 = sum(c[:50]) / 50
    vs_sma50 = (spot / sma50 - 1) * 100 if sma50 else 0.0
    sma200 = sum(c[:200]) / 200 if len(c) >= 200 else None
    vs_sma200 = (spot / sma200 - 1) * 100 if sma200 else None
    window = c[:252] if len(c) >= 252 else c
    peak = max(window) if window else spot
    dd = (spot / peak - 1) * 100 if peak else 0.0
    return {
        "spot": round(spot, 4 if spot < 10 else 2), "chg_1d": round(chg_1d, 2),
        "ret_21d": round(ret_21, 2), "vol_20d": round(vol, 1), "var_95_1d": round(var95, 2),
        "beta": None, "drawdown": round(dd, 2), "vs_sma50": round(vs_sma50, 2),
        "vs_sma200": round(vs_sma200, 2) if vs_sma200 is not None else None,
        "state": _state(dd, vs_sma50),
    }


def _beta(sym_pairs: list, mkt_pairs: list, n: int = VAR_WINDOW) -> Optional[float]:
    import numpy as np

    if not mkt_pairs:
        return None
    mkt = dict(mkt_pairs)
    aligned = [(d, px) for d, px in sym_pairs if d in mkt][: n + 1]
    if len(aligned) < 20:
        return None
    s = [px for _, px in aligned]
    m = [mkt[d] for d, _ in aligned]
    sr = np.array([s[i] / s[i + 1] - 1 for i in range(len(s) - 1)])
    mr = np.array([m[i] / m[i + 1] - 1 for i in range(len(m) - 1)])
    var = float(np.var(mr))
    if var <= 0:
        return None
    return float(np.cov(sr, mr, ddof=0)[0, 1] / var)


def _posture(rows: list, equity: bool) -> dict:
    ok = [i for i in rows if i.get("status") == "ok"]
    if not ok:
        return {"label": "unavailable"}
    above = sum(1 for i in ok if (i.get("vs_sma50") or 0) >= 0)
    avg_dd = sum(i.get("drawdown", 0.0) for i in ok) / len(ok)
    avg_var = sum(i.get("var_95_1d", 0.0) for i in ok) / len(ok)
    out = {"breadth_above_50dma": f"{above}/{len(ok)}",
           "avg_drawdown_pct": round(avg_dd, 2), "avg_var_95_1d_pct": round(avg_var, 2)}
    if equity:
        out["label"] = "RISK-ON" if (above >= 0.75 * len(ok) and avg_dd > -5) else \
            ("RISK-OFF" if (above <= 0.25 * len(ok) or avg_dd <= -10) else "NEUTRAL")
    else:
        out["label"] = None
    return out


# ── deterministic demo (offline / tests) ────────────────────────────────────

def _demo_metrics(sym: str) -> dict:
    h = sum(ord(ch) for ch in sym)
    dd = round(-(h % 15), 2)
    vs50 = round((h % 9) - 4, 2)
    return {
        "spot": round(50 + (h % 950) + (h % 7) / 10, 2), "chg_1d": round(((h % 7) - 3) * 0.3, 2),
        "ret_21d": round(((h % 11) - 5) * 0.8, 2), "vol_20d": round(10 + (h % 40), 1),
        "var_95_1d": round(1 + (h % 5) + (h % 3) / 10, 2), "beta": round(0.5 + (h % 12) / 10, 2),
        "drawdown": dd, "vs_sma50": vs50, "vs_sma200": round((h % 17) - 8, 2),
        "state": _state(dd, vs50), "as_of": "2026-06-26",
    }


# ── public API ──────────────────────────────────────────────────────────────

def _row(member, series, market_pairs):
    tk, sym, name, kind = member
    base = {"ticker": tk, "symbol": sym, "name": name, "kind": kind}
    pairs = series.get(tk)
    m = _metrics(pairs) if pairs else None
    if m is None:
        return {**base, "status": "unavailable"}
    b = _beta(pairs, market_pairs)
    m["beta"] = round(b, 2) if b is not None else None
    return {**base, "status": "ok", "as_of": pairs[0][0], **m}


def build(*, group: str = DEFAULT_GROUP, source: str = "live", settings=None,
          generated_at_utc: Optional[str] = None) -> dict:
    g = _GROUP_BY_ID.get(group) or _GROUP_BY_ID[DEFAULT_GROUP]
    if source == "demo":
        rows = [{"ticker": tk, "symbol": sym, "name": name, "kind": kind,
                 "status": "ok", "demo": True, **_demo_metrics(tk)}
                for (tk, sym, name, kind) in g["members"]]
    else:
        from concurrent.futures import ThreadPoolExecutor

        members = g["members"]
        with ThreadPoolExecutor(max_workers=8) as ex:
            series = dict(zip([m[0] for m in members],
                              ex.map(lambda mm: _safe_fetch(settings, mm[1], mm[3]), members)))
        market_pairs = _safe_fetch(settings, _MARKET, "index")
        rows = [_row(m, series, market_pairs) for m in members]
    posture = _posture(rows, g["equity"])
    ok = [i for i in rows if i.get("status") == "ok"]
    as_of = max((i.get("as_of", "") for i in ok), default=None) or None
    return {
        "schema": SCHEMA, "source": source, "group": g["id"], "group_label": g["label"],
        "group_equity": g["equity"], "as_of": as_of, "generated_at_utc": generated_at_utc,
        "available_groups": available_groups(), "rows": rows, "posture": posture,
        "summary": {"total": len(rows), "live": len(ok), "unavailable": len(rows) - len(ok)},
        "methodology": METHODOLOGY,
        "disclaimer": (METHODOLOGY["disclaimer"] if source != "demo"
                       else "DEMONSTRATION readings — synthetic, not live market data."),
        "output_sha256": sha256_of_obj({"group": g["id"], "rows": rows}),
    }


def read_symbol(settings, symbol: str, *, generated_at_utc: Optional[str] = None) -> Optional[dict]:
    """Compact risk row for any symbol the feed supports, or None if not found."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return None
    pairs, kind = _fetch_any(settings, sym)
    if pairs is None:
        return None
    m = _metrics(pairs)
    if m is None:
        return None
    market_pairs = pairs if sym == _MARKET else _safe_fetch(settings, _MARKET, "index")
    b = _beta(pairs, market_pairs)
    m["beta"] = round(b, 2) if b is not None else None
    return {"ticker": sym, "symbol": sym, "name": sym, "kind": kind,
            "status": "ok", "as_of": pairs[0][0], "ad_hoc": True, **m}


# ── institutional single-symbol risk profile (the cockpit detail) ────────────

PROFILE_SCHEMA = "cbsrm-desk-risk-profile/1.0.0"
_EWMA_LAMBDA = 0.94  # RiskMetrics


def _ret_stats(pairs: list, market_pairs, vix_pairs) -> dict:
    """Full institutional risk statistics from a newest-first price series."""
    import numpy as np

    c = np.array([px for _, px in pairs], dtype=float)  # newest-first
    rets = c[:-1] / c[1:] - 1.0                          # newest-first daily simple returns
    n = len(rets)
    spot = float(c[0])
    mu_ann = float(rets.mean()) * 252
    sd = float(rets.std(ddof=1)) if n > 1 else 0.0
    ann_vol = sd * math.sqrt(252) * 100
    downs = rets[rets < 0]
    dsd = float(downs.std(ddof=1)) if len(downs) > 1 else sd
    sharpe = round(mu_ann / (sd * math.sqrt(252)), 2) if sd > 0 else 0.0
    sortino = round(mu_ann / (dsd * math.sqrt(252)), 2) if dsd > 0 else 0.0
    # EWMA (RiskMetrics) volatility, oldest->newest recursion
    chrono = rets[::-1]
    v = float(chrono[0] ** 2)
    for x in chrono[1:]:
        v = _EWMA_LAMBDA * v + (1 - _EWMA_LAMBDA) * float(x) ** 2
    ewma_vol = math.sqrt(v * 252) * 100
    # max drawdown over the sample
    prices_chrono = c[::-1]
    peak = np.maximum.accumulate(prices_chrono)
    max_dd = float((prices_chrono / peak - 1.0).min()) * 100
    # historical VaR / CVaR table (positive losses), sqrt-time scaled
    var_table = []
    for conf in (0.95, 0.99):
        q = float(np.percentile(rets, (1 - conf) * 100))
        tail = rets[rets <= q]
        cvar_1d = -float(tail.mean()) if len(tail) else -q
        for h in (1, 5, 10):
            var_table.append({
                "horizon": f"{h}D", "confidence": f"{int(conf*100)}%",
                "var_pct": round(-q * math.sqrt(h) * 100, 2),
                "cvar_pct": round(cvar_1d * math.sqrt(h) * 100, 2),
            })
    beta_m = _beta(pairs, market_pairs)
    return {
        "spot": spot, "points": int(n + 1), "ann_return_pct": round(mu_ann * 100, 2),
        "ann_vol_pct": round(ann_vol, 1), "ewma_vol_pct": round(ewma_vol, 1),
        "sharpe": sharpe, "sortino": sortino, "max_drawdown_pct": round(max_dd, 2),
        "beta_sp": round(beta_m, 2) if beta_m is not None else None,
        "var_table": var_table, "_rets": rets, "_pairs": pairs,
    }


def _vix_beta(pairs: list, vix_pairs) -> Optional[float]:
    """Sensitivity of the symbol's daily return to a 1-point change in VIX."""
    import numpy as np

    if not vix_pairs:
        return None
    vix = dict(vix_pairs)
    common = [(d, px) for d, px in pairs if d in vix][:121]  # newest-first
    if len(common) < 30:
        return None
    p = np.array([px for _, px in common], dtype=float)
    vx = np.array([vix[d] for d, _ in common], dtype=float)
    r = p[:-1] / p[1:] - 1.0
    dvix = vx[:-1] - vx[1:]
    var = float(np.var(dvix))
    if var <= 0:
        return None
    return float(np.cov(r, dvix, ddof=0)[0, 1] / var)


def _stress(spot: float, beta_m: Optional[float], vix_beta: Optional[float]) -> list[dict]:
    """Factor-shock stress scenarios (beta-driven, reproducible)."""
    b = beta_m if beta_m is not None else 1.0
    out = [
        ("Risk-off · S&P −5%", b * -5.0),
        ("Tail · S&P −10%", b * -10.0),
        ("Risk-on relief · S&P +3%", b * 3.0),
    ]
    if vix_beta is not None:
        out.append(("Vol shock · VIX +10pt", vix_beta * 10.0 * 100))
    rows = []
    for name, mv in out:
        rows.append({"scenario": name, "move_pct": round(mv, 2),
                     "implied_price": round(spot * (1 + mv / 100.0), 2)})
    return rows


def _quant_read(sym: str, state: str, st: dict, var5: Optional[float]) -> str:
    bits = [f"{sym} is {state.replace('-', ' ')}",
            f"annualised volatility {st['ann_vol_pct']}% (EWMA {st['ewma_vol_pct']}%)",
            f"Sharpe {st['sharpe']}, Sortino {st['sortino']}"]
    if st.get("beta_sp") is not None:
        bits.append(f"beta to the S&P {st['beta_sp']}")
    if var5 is not None:
        bits.append(f"5-day 95% VaR {var5}%")
    bits.append(f"max 1y drawdown {st['max_drawdown_pct']}%")
    return ". ".join(bits[:1]) + " — " + ", ".join(bits[1:]) + ". Risk measurement, not advice."


def _fetch_bars(settings, symbol: str, kind: str):
    """Newest-first OHLC bars [{date,o,h,l,c}] for a symbol, or None."""
    from wavervanir_api.providers.financialdata import get_json, index_prices

    if kind == "index":
        rows = index_prices(settings, symbol)
    else:
        rows = get_json(settings, _ENDPOINT.get(kind, "stock-prices"),
                        params={"identifier": symbol, "offset": 0})
    if not isinstance(rows, list) or not rows:
        return None
    bars = []
    for r in rows:
        try:
            o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        except (KeyError, TypeError, ValueError):
            continue
        bars.append({"date": str(r.get("date"))[:10], "o": o, "h": h, "l": l, "c": c})
    return bars or None


def _fetch_bars_any(settings, symbol: str):
    for kind in _resolve_kinds(symbol):
        try:
            bars = _fetch_bars(settings, symbol, kind)
        except Exception:
            bars = None
        if bars:
            return bars, kind
    return None, None


def _build_chart(bars: list, var_table: list) -> dict:
    """Candlestick bars + projected levels: MAs, VaR levels, and a forward
    drift + volatility cone (statistical projection, reproducible — not a forecast)."""
    import numpy as np

    chrono = list(reversed(bars))  # oldest-first
    closes = [b["c"] for b in chrono]
    n = len(chrono)

    def sma(i, w):
        return None if i + 1 < w else sum(closes[i + 1 - w:i + 1]) / w

    sma50 = [sma(i, 50) for i in range(n)]
    sma200 = [sma(i, 200) for i in range(n)]
    disp = chrono[-120:]
    off = n - len(disp)
    bars_out = [{"t": b["date"], "o": round(b["o"], 4), "h": round(b["h"], 4),
                 "l": round(b["l"], 4), "c": round(b["c"], 4)} for b in disp]
    sma50_out = [None if sma50[off + i] is None else round(sma50[off + i], 4) for i in range(len(disp))]
    sma200_out = [None if sma200[off + i] is None else round(sma200[off + i], 4) for i in range(len(disp))]

    spot = closes[-1]
    rec = closes[-64:]
    rets = np.diff(np.log(rec)) if len(rec) > 2 else np.array([0.0])
    drift = float(np.mean(rets))
    sigma = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    cone = []
    for k in range(0, 64, 3):
        mid = spot * math.exp(drift * k)
        sd = sigma * math.sqrt(k)
        cone.append({"k": k, "mid": round(mid, 4),
                     "lo1": round(mid * math.exp(-sd), 4), "hi1": round(mid * math.exp(sd), 4),
                     "lo2": round(mid * math.exp(-2 * sd), 4), "hi2": round(mid * math.exp(2 * sd), 4)})

    def tgt(days):
        return round(spot * math.exp(drift * days), 4)

    def var_level(h, conf):
        r = next((x for x in var_table if x["horizon"] == h and x["confidence"] == conf), None)
        return round(spot * (1 - r["var_pct"] / 100), 4) if r else None

    levels = [{"label": "Last", "price": round(spot, 4), "kind": "price"}]
    if sma50_out and sma50_out[-1] is not None:
        levels.append({"label": "50-DMA", "price": sma50_out[-1], "kind": "ma50"})
    if sma200_out and sma200_out[-1] is not None:
        levels.append({"label": "200-DMA", "price": sma200_out[-1], "kind": "ma200"})
    levels.append({"label": "1M proj", "price": tgt(21), "kind": "proj"})
    v95, v99 = var_level("5D", "95%"), var_level("5D", "99%")
    if v95:
        levels.append({"label": "5D VaR95", "price": v95, "kind": "var95"})
    if v99:
        levels.append({"label": "5D VaR99", "price": v99, "kind": "var99"})

    return {
        "bars": bars_out, "sma50": sma50_out, "sma200": sma200_out, "levels": levels,
        "projection": {
            "cone": cone, "targets": {"1w": tgt(5), "1m": tgt(21), "3m": tgt(63)},
            "drift_daily": round(drift, 5), "vol_daily": round(sigma, 5),
            "note": ("Projection = trailing-63d drift carried forward with a ±1σ/±2σ "
                     "volatility cone. Statistical and reproducible — not an ML forecast."),
        },
    }


def risk_profile(settings, symbol: str, *, generated_at_utc: Optional[str] = None) -> Optional[dict]:
    """Institutional single-symbol cockpit read: returns, risk-desk stats, VaR/CVaR
    table, macro-stress scenarios, a candlestick chart with projected levels, a quant
    read, and reproducible provenance."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return None
    bars, kind = _fetch_bars_any(settings, sym)
    if bars is None or len(bars) < 51:
        return None
    pairs = [(b["date"], b["c"]) for b in bars]
    market_pairs = pairs if sym == _MARKET else _safe_fetch(settings, _MARKET, "index")
    vix_pairs = _safe_fetch(settings, "^VIX", "index")
    base = _metrics(pairs)  # spot, chg_1d, ret_21d, vol_20d, var_95_1d, drawdown, vs_sma50/200, state
    st = _ret_stats(pairs, market_pairs, vix_pairs)
    c = [px for _, px in pairs]
    horizons = {
        "ret_1w_pct": round((c[0] / c[5] - 1) * 100, 2) if len(c) > 5 and c[5] else None,
        "ret_1m_pct": base.get("ret_21d"),
        "ret_3m_pct": round((c[0] / c[63] - 1) * 100, 2) if len(c) > 63 and c[63] else None,
    }
    vb = _vix_beta(pairs, vix_pairs)
    stress = _stress(st["spot"], st.get("beta_sp"), vb)
    var5_95 = next((r["var_pct"] for r in st["var_table"]
                    if r["horizon"] == "5D" and r["confidence"] == "95%"), None)
    profile = {
        "schema": PROFILE_SCHEMA, "symbol": sym, "kind": kind, "as_of": pairs[0][0],
        "generated_at_utc": generated_at_utc, "state": base["state"],
        "price": st["spot"], "chg_1d_pct": base["chg_1d"], "horizons": horizons,
        "risk_desk": {
            "sharpe": st["sharpe"], "sortino": st["sortino"], "ann_vol_pct": st["ann_vol_pct"],
            "ewma_vol_pct": st["ewma_vol_pct"], "beta_sp": st["beta_sp"],
            "max_drawdown_pct": st["max_drawdown_pct"], "ann_return_pct": st["ann_return_pct"],
        },
        "var_table": st["var_table"],
        "trend": {"vs_sma50_pct": base.get("vs_sma50"), "vs_sma200_pct": base.get("vs_sma200")},
        "macro_stress": stress,
        "provenance": {"data_points": st["points"], "as_of": pairs[0][0],
                       "source": "financialdata.net", "endpoint_kind": kind,
                       "vix_factor": vb is not None, "market_factor": st.get("beta_sp") is not None},
        "methodology": METHODOLOGY,
        "disclaimer": METHODOLOGY["disclaimer"],
    }
    profile["chart"] = _build_chart(bars, st["var_table"])
    profile["quant_read"] = _quant_read(sym, base["state"], st, var5_95)
    profile["output_sha256"] = sha256_of_obj(
        {k: v for k, v in profile.items() if k != "generated_at_utc"})
    return profile
