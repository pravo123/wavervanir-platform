"""Per-lens BI analytics for the Desk terminal — time series + summary stats.

For each systemic-risk lens this builds a normalized analytics object:

    { id, label, unit, source, fmt, series:[{date,value}], stats:{...},
      bands:[{upto,label}], source_mode, output_sha256, note }

History sources, per lens:
  * EQUITY-VIX  — real daily ^VIX close via financialdata.net index-prices.
  * ECB / FRED  — real quarterly series via the public cbsrm indicators
                  (best-effort: needs network, FRED lenses need FRED_API_KEY).
  * ``source=demo`` — a deterministic synthetic series for every lens, so the
                  drill-down is fully functional offline / for preview.

Stats are plain, defensible BI: current, min, max, mean, std, z-score, and the
current reading's percentile rank within its own history.
"""

from __future__ import annotations

import math
from typing import Optional

from wavervanir_api import desk_lenses
from wavervanir_api.audit import sha256_of_obj
from wavervanir_api.desk_conditions import (
    _FD_LENS,
    _call_with_timeout,
    _lens_specs,
)

LIVE_SERIES_TIMEOUT_S = 8.0
_MAX_QUARTERS = 48
_MAX_VIX_DAYS = 120


# ── lens metadata + regime bands ────────────────────────────────────────────

def _ecb_bands() -> list[dict]:
    return [{"upto": 0.27, "label": "calm"}, {"upto": 0.5, "label": "elevated"},
            {"upto": None, "label": "severe"}]


_BANDS: dict[str, list[dict]] = {
    "EQUITY-VIX": [{"upto": 15, "label": "calm"}, {"upto": 20, "label": "normal"},
                   {"upto": 30, "label": "elevated"}, {"upto": None, "label": "stress"}],
    "STLFSI4": [{"upto": 1, "label": "normal"}, {"upto": 3, "label": "elevated"},
                {"upto": None, "label": "severe"}],
    "YIELD-CURVE": [{"upto": 0.3, "label": "low"}, {"upto": 0.5, "label": "watch"},
                    {"upto": None, "label": "high"}],
    "SAHM": [{"upto": 0.5, "label": "normal"}, {"upto": None, "label": "trigger"}],
    "CREDIT-SPREAD": [{"upto": 600, "label": "benign"}, {"upto": 1000, "label": "widening"},
                      {"upto": None, "label": "stress"}],
    "ECB-CISS-US": _ecb_bands(), "ECB-CISS-EA": _ecb_bands(), "ECB-CISS-UK": _ecb_bands(),
}


def _build_meta() -> dict[str, dict]:
    meta: dict[str, dict] = {}
    for s in _lens_specs():
        # (id, label, lens, args, value_field, state_field, fmt, unit, source)
        meta[s[0]] = {"label": s[1], "fmt": s[6], "unit": s[7], "source": s[8],
                      "bands": _BANDS.get(s[0], [])}
    meta[_FD_LENS["id"]] = {"label": _FD_LENS["label"], "fmt": "level",
                            "unit": _FD_LENS["unit"], "source": _FD_LENS["source"],
                            "bands": _BANDS.get("EQUITY-VIX", [])}
    for nid, m in desk_lenses.NEW_LENS_META.items():
        meta[nid] = {"label": m["label"], "fmt": m["fmt"], "unit": m["unit"],
                     "source": m["source"], "bands": m["bands"]}
    return meta


LENS_META: dict[str, dict] = _build_meta()


# ── demo series (deterministic, offline) ────────────────────────────────────

_REGIME_SCORE = {"RISK_OFF": 0, "TRANSITION_DOWN": 1, "TRANSITION_UP": 2, "RISK_ON": 3}
# Representative current level per lens for the synthetic series.
_DEMO_CURRENT: dict[str, float] = {
    "ECB-CISS-US": 0.071, "ECB-CISS-EA": 0.089, "ECB-CISS-UK": 0.064,
    "STLFSI4": -0.42, "YIELD-CURVE": 0.18, "MACRO-REGIME": 3.0,
    "SAHM": 0.13, "CREDIT-SPREAD": 312.0, "EQUITY-VIX": 14.2,
}


def _monthly_labels(n: int, end_year: int = 2026, end_month: int = 6) -> list[str]:
    out: list[str] = []
    y, m = end_year, end_month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}-01")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def _demo_series(lens_id: str) -> list[dict]:
    if lens_id in desk_lenses.NEW_LENS_IDS:
        return desk_lenses.demo_series(lens_id, _monthly_labels(24))
    cur = _DEMO_CURRENT.get(lens_id)
    if cur is None:
        return []
    n = 24
    dates = _monthly_labels(n)
    amp = 0.22
    pts = []
    for i in range(n):
        f = 1.0 + amp * math.sin(i * 0.5) - 0.4 * amp * math.cos(i * 0.31)
        pts.append(round(cur * f, 4))
    pts[-1] = round(cur, 4)
    return [{"date": d, "value": v} for d, v in zip(dates, pts)]


# ── live series ─────────────────────────────────────────────────────────────

def _vix_series(settings) -> list[dict]:
    from wavervanir_api.providers.financialdata import index_prices

    rows = index_prices(settings, "^VIX")
    rows = [r for r in rows if isinstance(r.get("close"), (int, float))][:_MAX_VIX_DAYS]
    rows = list(reversed(rows))  # oldest-first for charting
    return [{"date": str(r.get("date"))[:10], "value": round(float(r["close"]), 2)} for r in rows]


def _cbsrm_series(lens_id: str) -> list[dict]:
    """Real quarterly series via public cbsrm indicators (network; FRED needs key)."""
    import pandas as pd

    def q(series) -> list[dict]:
        s = series.dropna()
        s.index = pd.to_datetime(s.index)
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        try:
            qq = s.resample("QE").last().dropna()
        except ValueError:
            qq = s.resample("Q").last().dropna()
        out = [{"date": str(p), "value": round(float(v), 6)}
               for p, v in zip(qq.index.to_period("Q"), qq.values)]
        return out[-_MAX_QUARTERS:]

    if lens_id.startswith("ECB-CISS-"):
        from cbsrm.data import ECBSDMXClient
        from cbsrm.indicators import ECBCISSWrap

        variant = lens_id.split("-")[-1]
        client = ECBSDMXClient()
        fetch = {"US": client.get_ciss_us, "EA": client.get_ciss_euro_area,
                 "UK": client.get_ciss_uk}[variant]
        return q(ECBCISSWrap(variant=variant).compute(fetch()).values)
    if lens_id == "STLFSI4":
        from cbsrm.data import FREDClient
        from cbsrm.indicators import STLFSIWrap

        return q(STLFSIWrap().compute(FREDClient().get_multi(["STLFSI4"])).values)
    if lens_id == "YIELD-CURVE":
        from cbsrm.data import FREDClient
        from cbsrm.macro import YieldCurveIndicator

        df = FREDClient().get_multi(["T10Y3M"], frequency="d")
        return q(YieldCurveIndicator().compute(df).values)
    if lens_id == "SAHM":
        from cbsrm.data import FREDClient
        from cbsrm.macro import SahmRuleIndicator

        df = FREDClient().get_multi(["UNRATE"], frequency="m")
        return q(SahmRuleIndicator().compute(df).values)
    if lens_id == "CREDIT-SPREAD":
        from cbsrm.data import FREDClient
        from cbsrm.macro import CreditSpreadRegimeIndicator

        df = FREDClient().get_multi(["BAMLH0A0HYM2"], frequency="d")
        return q(CreditSpreadRegimeIndicator().compute(df).values)
    return []  # MACRO-REGIME (categorical) has no numeric live series yet


def _live_series(settings, lens_id: str) -> list[dict]:
    try:
        if lens_id in desk_lenses.NEW_LENS_IDS:
            return desk_lenses.live_series(settings, lens_id)
        if lens_id == "EQUITY-VIX":
            return _vix_series(settings)
        return _cbsrm_series(lens_id)
    except Exception:
        return []


# ── stats ───────────────────────────────────────────────────────────────────

def _stats(values: list[float]) -> Optional[dict]:
    if not values:
        return None
    n = len(values)
    cur = values[-1]
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
    rank = sum(1 for v in values if v <= cur) / n
    prev = values[-2] if n >= 2 else cur
    return {
        "n": n,
        "current": round(cur, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "z": round((cur - mean) / std, 2) if std > 0 else 0.0,
        "percentile": round(rank, 3),
        "change": round(cur - prev, 4),
    }


# ── public API ──────────────────────────────────────────────────────────────

def lens_analytics(settings, lens_id: str, *, source: str = "live") -> dict:
    meta = LENS_META[lens_id]
    if source == "demo":
        series = _demo_series(lens_id)
    else:
        series = _call_with_timeout(
            lambda: _live_series(settings, lens_id), LIVE_SERIES_TIMEOUT_S
        ) or []
    values = [p["value"] for p in series]
    stats = _stats(values)
    return {
        "id": lens_id,
        "label": meta["label"],
        "unit": meta["unit"],
        "source": meta["source"],
        "fmt": meta["fmt"],
        "bands": meta["bands"],
        "series": series,
        "stats": stats,
        "source_mode": source,
        "note": None if values else "history unavailable for this source (try source=demo)",
        "output_sha256": sha256_of_obj(series),
    }
