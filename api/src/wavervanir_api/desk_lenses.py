"""Advanced systemic-risk lenses built on the financialdata.net feed.

Four lenses that turn raw data into defensible signals (the CBSRM value-add):

  * ``XBORDER-DY``      cross-border spillover — a real Diebold-Yilmaz (2012)
                        generalized total-connectedness index across major world
                        equity indexes, with a rolling-window history series.
  * ``OPTIONS-TAIL``    options put/call vega skew near the money (tail-hedging
                        demand) — best-effort from a few contracts' greeks.
  * ``FUND-FRAGILITY``  net redemption pressure across a sample of funds, from
                        real share_sale / share_redemption flows vs net assets.
  * ``ESG-TRANSITION``  climate/transition risk — mean industry environmental
                        risk score (BIS financial-stability angle).

Each lens exposes a ``reading`` (current value for the conditions grid) and a
``series`` (for the BI drill-down), in both ``live`` and deterministic ``demo``
forms. Live calls are network-bound and may degrade to ``unavailable``; demo is
offline and deterministic.
"""

from __future__ import annotations

import math
import threading
from typing import Any, Callable, Optional

from wavervanir_api.audit import sha256_of_obj  # noqa: F401  (kept for parity)

# ── small timeout helper (local, to avoid an import cycle) ──────────────────

def _call_with_timeout(fn: Callable[[], Any], timeout_s: float) -> Optional[Any]:
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["v"] = fn()
        except Exception:
            box["err"] = True

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive() or "err" in box:
        return None
    return box.get("v")


# ── lens metadata + regime bands ────────────────────────────────────────────

NEW_LENS_META: dict[str, dict] = {
    "XBORDER-DY": {
        "label": "Cross-border spillover · DY", "fmt": "level",
        "unit": "% connectedness", "source": "financialdata.net",
        "lens": "Contagion",
        "bands": [{"upto": 50, "label": "low"}, {"upto": 70, "label": "elevated"},
                  {"upto": None, "label": "high"}],
    },
    "OPTIONS-TAIL": {
        "label": "Options put/call vega skew", "fmt": "ratio",
        "unit": "put÷call vega", "source": "financialdata.net",
        "lens": "Tail / options",
        "bands": [{"upto": 1.0, "label": "balanced"}, {"upto": 1.3, "label": "put-skew"},
                  {"upto": None, "label": "tail-bid"}],
    },
    "FUND-FRAGILITY": {
        "label": "Fund redemption pressure", "fmt": "level",
        "unit": "% net 3m flow", "source": "financialdata.net",
        "lens": "Liquidity / flows",
        "bands": [{"upto": 0, "label": "inflows"}, {"upto": 2, "label": "mild"},
                  {"upto": None, "label": "outflows"}],
    },
    "ESG-TRANSITION": {
        "label": "Climate transition risk · ESG", "fmt": "level",
        "unit": "env risk 0-100", "source": "financialdata.net",
        "lens": "Transition / climate",
        "bands": [{"upto": 15, "label": "low"}, {"upto": 25, "label": "moderate"},
                  {"upto": None, "label": "high"}],
    },
}
NEW_LENS_IDS = list(NEW_LENS_META)

_DEMO_CURRENT = {
    "XBORDER-DY": 62.4, "OPTIONS-TAIL": 1.18, "FUND-FRAGILITY": 1.8, "ESG-TRANSITION": 16.5,
}

_INTL_INDEXES = ["^GSPC", "^FTSE", "^GDAXI", "^N225", "^HSI", "^FCHI", "^STOXX50E"]


def _meta_reading(lens_id: str, **extra) -> dict:
    m = NEW_LENS_META[lens_id]
    base = {"id": lens_id, "label": m["label"], "lens": m["lens"],
            "unit": m["unit"], "source": m["source"], "fmt": m["fmt"]}
    base.update(extra)
    return base


def _unavailable(lens_id: str, reason: str) -> dict:
    return _meta_reading(lens_id, status="unavailable", reason=reason)


def _band_state(lens_id: str, value: float) -> Optional[str]:
    for b in NEW_LENS_META[lens_id]["bands"]:
        if b["upto"] is None or value < b["upto"]:
            return b["label"]
    return None


# ── Diebold-Yilmaz spillover (real econometrics, numpy) ──────────────────────

def _dy_total(R) -> float:
    """Diebold-Yilmaz (2012) generalized total connectedness index in [0,100].

    R: (T x N) returns matrix. Fits a VAR(2), inverts to VMA, computes the
    generalized forecast-error variance decomposition (Pesaran-Shin) at H=10,
    row-normalizes, and sums the off-diagonal share.
    """
    import numpy as np

    p, H = 2, 10
    R = np.asarray(R, dtype=float)
    T, N = R.shape
    Y = R[p:]
    cols = [np.ones((Y.shape[0], 1))]
    for k in range(1, p + 1):
        cols.append(R[p - k:T - k])
    X = np.hstack(cols)
    B = np.linalg.lstsq(X, Y, rcond=None)[0]          # (1+N*p) x N
    resid = Y - X @ B
    dof = max(1, Y.shape[0] - X.shape[1])
    Sigma = (resid.T @ resid) / dof
    coefs = B[1:].reshape(p, N, N)
    A = [coefs[k].T for k in range(p)]                # A_k: N x N
    Psi = [np.eye(N)]
    for i in range(1, H):
        s = np.zeros((N, N))
        for k in range(1, min(i, p) + 1):
            s += A[k - 1] @ Psi[i - k]
        Psi.append(s)
    sig = np.diag(Sigma)
    denom = np.zeros(N)
    for i in range(N):
        denom[i] = sum((Psi[h] @ Sigma @ Psi[h].T)[i, i] for h in range(H))
    theta = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            num = sum(((Psi[h] @ Sigma)[i, j]) ** 2 for h in range(H))
            theta[i, j] = (num / sig[j]) / denom[i] if (sig[j] > 0 and denom[i] > 0) else 0.0
    rowsum = theta.sum(axis=1, keepdims=True)
    rowsum[rowsum == 0] = 1.0
    thetan = theta / rowsum
    total = 100.0 * (thetan.sum() - np.trace(thetan)) / N
    return float(total)


def _dy_panel(settings):
    """Aligned log-return panel for the world indexes. (dates, returns, syms)."""
    import numpy as np

    from wavervanir_api.providers.financialdata import index_prices

    closes: dict[str, dict] = {}
    for sym in _INTL_INDEXES:
        rows = index_prices(settings, sym)
        closes[sym] = {str(r.get("date"))[:10]: float(r["close"])
                       for r in rows if isinstance(r.get("close"), (int, float))}
    sets = [set(m) for m in closes.values() if m]
    if len(sets) < len(_INTL_INDEXES):
        return [], None, _INTL_INDEXES
    common = sorted(set.intersection(*sets))[-160:]
    if len(common) < 60:
        return common, None, _INTL_INDEXES
    px = np.array([[closes[s][d] for s in _INTL_INDEXES] for d in common])
    rets = np.diff(np.log(px), axis=0)
    return common[1:], rets, _INTL_INDEXES


def _dy_reading_live(settings) -> dict:
    dates, rets, _ = _dy_panel(settings)
    if rets is None or rets.shape[0] < 60:
        return _unavailable("XBORDER-DY", "insufficient aligned history")
    total = round(_dy_total(rets[-120:]), 1)
    return _meta_reading("XBORDER-DY", status="ok", as_of=dates[-1], value=total,
                         state=_band_state("XBORDER-DY", total),
                         interpretation=f"{len(_INTL_INDEXES)} world equity indexes")


def _dy_series_live(settings) -> list[dict]:
    dates, rets, _ = _dy_panel(settings)
    if rets is None or rets.shape[0] < 110:
        return []
    win, step, out = 100, 3, []
    for end in range(win, rets.shape[0] + 1, step):
        out.append({"date": dates[end - 1], "value": round(_dy_total(rets[end - win:end]), 1)})
    return out


# ── options put/call vega skew (best-effort) ─────────────────────────────────

def _options_reading_live(settings) -> dict:
    import httpx

    from wavervanir_api.providers.financialdata import get_json

    cli = httpx.Client(timeout=httpx.Timeout(12.0))
    und = "AAPL"
    sp = get_json(settings, "stock-prices", params={"identifier": und, "offset": 0}, client=cli)
    spot = float(sp[0]["close"]) if isinstance(sp, list) and sp else None
    chain = get_json(settings, "option-chain", params={"identifier": und, "offset": 0}, client=cli)
    if spot is None or not isinstance(chain, list) or not chain:
        return _unavailable("OPTIONS-TAIL", "chain/spot unavailable")
    exps = sorted({c.get("expiration_date") for c in chain if c.get("expiration_date")})
    rows = [c for c in chain if c.get("expiration_date") == exps[0]]
    puts = sorted([c for c in rows if c.get("put_or_call") == "Put" and (c.get("strike_price") or 0) < spot],
                  key=lambda c: -c["strike_price"])[:2]
    calls = sorted([c for c in rows if c.get("put_or_call") == "Call" and (c.get("strike_price") or 0) > spot],
                   key=lambda c: c["strike_price"])[:2]

    def vega(c):
        g = get_json(settings, "option-greeks", params={"identifier": c["contract_name"]}, client=cli)
        rec = g[0] if isinstance(g, list) and g else (g if isinstance(g, dict) else None)
        try:
            return abs(float(rec.get("vega"))) if rec and rec.get("vega") is not None else None
        except (TypeError, ValueError):
            return None

    pv = [v for v in (vega(c) for c in puts) if v]
    cv = [v for v in (vega(c) for c in calls) if v]
    if not pv or not cv or sum(cv) == 0:
        return _unavailable("OPTIONS-TAIL", "greeks unavailable")
    skew = round((sum(pv) / len(pv)) / (sum(cv) / len(cv)), 3)
    return _meta_reading("OPTIONS-TAIL", status="ok", as_of=str(exps[0]), value=skew,
                         state=_band_state("OPTIONS-TAIL", skew),
                         interpretation=f"{und} near-the-money, exp {exps[0]}")


# ── fund redemption pressure (real flows) ────────────────────────────────────

# AUM-weighted fund sample. The per-fund statistics calls are fetched
# concurrently (financialdata.net Enterprise allows 50 req/s) so the whole lens
# resolves in ~2s wall-clock instead of ~8s sequential — which used to graze the
# 9s lens timeout and intermittently degrade the card to "unavailable".
_FUND_SAMPLE_SIZE = 16
_FUND_FETCH_WORKERS = 8
_FUND_FETCH_BUDGET_S = 7.0


def _fund_one(settings, fsym) -> Optional[tuple]:
    """(net_flow, net_assets, period) for one fund, or None. Network-bound."""
    from wavervanir_api.providers.financialdata import get_json

    try:
        d = get_json(settings, "mutual-fund-statistics", params={"identifier": fsym})
    except Exception:
        return None
    if not isinstance(d, list) or not d:
        return None
    r = d[0]
    na = float(r.get("net_assets") or 0)
    if na <= 0:
        return None
    red = sum(float(r.get(f"share_redemption_preceding_month{i}") or 0) for i in (1, 2, 3))
    sal = sum(float(r.get(f"share_sale_preceding_month{i}") or 0) for i in (1, 2, 3))
    return (red - sal, na, str(r.get("period_of_report") or ""))


def _fund_reading_live(settings) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from wavervanir_api.providers.financialdata import get_json

    syms = get_json(settings, "mutual-fund-symbols", params={"offset": 0})
    if not isinstance(syms, list) or not syms:
        return _unavailable("FUND-FRAGILITY", "fund universe unavailable")
    sample = [s.get("trading_symbol") for s in syms[:_FUND_SAMPLE_SIZE]
              if s.get("trading_symbol")]

    net_flow, net_assets, used, latest = 0.0, 0.0, 0, ""
    ex = ThreadPoolExecutor(max_workers=_FUND_FETCH_WORKERS)
    futs = [ex.submit(_fund_one, settings, f) for f in sample]
    try:
        for fut in as_completed(futs, timeout=_FUND_FETCH_BUDGET_S):
            res = fut.result()
            if res is None:
                continue
            df, na, per = res
            net_flow += df
            net_assets += na
            used += 1
            latest = max(latest, per)
    except TimeoutError:
        pass  # aggregate whatever returned within budget; don't blank the card
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    if used == 0 or net_assets <= 0:
        return _unavailable("FUND-FRAGILITY", "no fund flow data")
    pct = round(100.0 * net_flow / net_assets, 2)
    return _meta_reading("FUND-FRAGILITY", status="ok", as_of=latest[:10] or None, value=pct,
                         state=_band_state("FUND-FRAGILITY", pct),
                         interpretation=f"net redemptions across {used} funds (AUM-weighted)")


# ── ESG / climate transition (real industry env scores) ──────────────────────

def _esg_reading_live(settings) -> dict:
    from wavervanir_api.providers.financialdata import get_json

    for d in ("2025-12-31", "2025-09-30", "2025-06-30", "2024-12-31"):
        try:
            rows = get_json(settings, "industry-esg-scores", params={"date": d, "offset": 0})
        except Exception:
            rows = None
        if isinstance(rows, list) and rows:
            env = [float(r["environmental_risk_score"]) for r in rows
                   if isinstance(r.get("environmental_risk_score"), (int, float))]
            if env:
                val = round(sum(env) / len(env), 2)
                return _meta_reading("ESG-TRANSITION", status="ok", as_of=d, value=val,
                                     state=_band_state("ESG-TRANSITION", val),
                                     interpretation=f"mean of {len(env)} industries")
    return _unavailable("ESG-TRANSITION", "no ESG scores returned")


# ── demo (deterministic) readings + series ──────────────────────────────────

_LIVE_READING = {
    "XBORDER-DY": _dy_reading_live,
    "OPTIONS-TAIL": _options_reading_live,
    "FUND-FRAGILITY": _fund_reading_live,
    "ESG-TRANSITION": _esg_reading_live,
}


def demo_reading(lens_id: str) -> dict:
    cur = _DEMO_CURRENT[lens_id]
    return _meta_reading(lens_id, status="ok", as_of="2026-06-26", value=cur,
                         state=_band_state(lens_id, cur), demo=True)


def demo_series(lens_id: str, monthly_labels: list[str]) -> list[dict]:
    cur = _DEMO_CURRENT[lens_id]
    n = len(monthly_labels)
    amp = 0.16
    pts = [round(cur * (1.0 + amp * math.sin(i * 0.5) - 0.4 * amp * math.cos(i * 0.29)), 4)
           for i in range(n)]
    pts[-1] = round(cur, 4)
    return [{"date": d, "value": v} for d, v in zip(monthly_labels, pts)]


def live_reading(settings, lens_id: str, *, timeout_s: float = 9.0) -> dict:
    r = _call_with_timeout(lambda: _LIVE_READING[lens_id](settings), timeout_s)
    return r if r is not None else _unavailable(lens_id, "upstream timeout")


def live_series(settings, lens_id: str, *, timeout_s: float = 10.0) -> list[dict]:
    if lens_id == "XBORDER-DY":
        return _call_with_timeout(lambda: _dy_series_live(settings), timeout_s) or []
    # Other lenses are point-in-time on this source; history is a follow-up.
    return []


def conditions_readings(settings, *, source: str) -> list[dict]:
    if source == "demo":
        return [demo_reading(i) for i in NEW_LENS_IDS]
    return [live_reading(settings, i) for i in NEW_LENS_IDS]
