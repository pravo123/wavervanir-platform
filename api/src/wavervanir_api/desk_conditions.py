"""Current-conditions snapshot for the gated Desk terminal.

Reuses the **public cbsrm CLI** as the computation contract — the same lenses the
public site shows — wrapped so any unavailable source (missing FRED key, network,
provider error) degrades to ``status="unavailable"`` rather than failing the
request. Every reading carries its own ``as_of`` date and source; the envelope is
content-addressed with the same SHA-256 the audit layer uses.

``source="demo"`` returns deterministic synthetic readings (clearly labelled) for
offline preview and tests — it never touches the network.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import io
import json
import threading
from typing import Any, Callable, Optional

from wavervanir_api import desk_lenses
from wavervanir_api.audit import sha256_of_obj

SCHEMA = "cbsrm-desk-conditions/1.0.0"
# Per-lens wall-clock cap for live fetches, so one slow/hanging upstream can't
# block the request. cbsrm's stdout-capturing CLI is not thread-safe, so lenses
# run sequentially — each in its own daemon thread we can abandon on timeout.
#
# Cold ECB SDMX fetches (a fresh container — e.g. just after a Render deploy — has
# an empty ``.cbsrm_cache``, so the build does a real network round-trip) were
# measured at ~2.5–6.5s, straddling the old 6.0s cap. Whichever CISS variant
# happened to land on the slow side was clipped to "unavailable" even though the
# data was fine (the drill-down, on an 8s cap + warm cache, showed the real value).
# The build is cached (1h TTL) and refreshed off the hot path, so a generous cap is
# cheap; combined with the last-good fallback below, a transient blip no longer
# blanks a card.
LIVE_LENS_TIMEOUT_S = 12.0


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


def _start(years: int) -> str:
    today = _dt.date.today()
    try:
        return today.replace(year=today.year - years).isoformat()
    except ValueError:  # Feb 29 guard
        return today.replace(year=today.year - years, day=28).isoformat()


# Lens spec mirrors the public site generator (tools/build_current_snapshot.py):
# (id, label, lens, cli_args, value_field, state_field, fmt, unit, source).
def _lens_specs() -> list[tuple]:
    return [
        ("ECB-CISS-US", "ECB CISS — United States", "System stress",
         ["ecb-ciss", "--variant", "US"], "value", None, "ratio", "index 0-1", "ECB SDMX"),
        ("ECB-CISS-EA", "ECB CISS — Euro Area", "System stress",
         ["ecb-ciss", "--variant", "EA"], "value", None, "ratio", "index 0-1", "ECB SDMX"),
        ("ECB-CISS-UK", "ECB CISS — United Kingdom", "System stress",
         ["ecb-ciss", "--variant", "UK"], "value", None, "ratio", "index 0-1", "ECB SDMX"),
        ("STLFSI4", "St. Louis Fed Financial Stress", "System stress",
         ["latest", "STLFSI4"], "value", None, "signed", "z · 0 = normal", "FRED"),
        ("YIELD-CURVE", "Recession probability · 12m", "Macro regime",
         ["yield-curve", "--start", _start(3)], "latest_recession_prob_12mo", None,
         "probability", "Estrella-Mishkin", "FRED"),
        ("MACRO-REGIME", "Macro regime · 4-state", "Macro regime",
         ["macro-regime", "--start", _start(3)], None, "latest_regime",
         "state", "composite", "FRED"),
        ("SAHM", "Sahm Rule recession signal", "Macro regime",
         ["sahm-rule", "--start", _start(3)], "value", "classification",
         "pp2", "pp · trigger 0.50", "FRED"),
        ("CREDIT-SPREAD", "HY credit-spread · OAS", "Tail / credit",
         ["credit-spread", "--start", _start(3)], "value", "regime", "bps", "bps", "FRED"),
    ]


def _run_json(args: list[str]) -> Optional[dict]:
    """Invoke the cbsrm CLI in-process and parse its JSON stdout, or None."""
    try:
        from cbsrm.cli import main  # public CLI contract
    except Exception:
        return None
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            main(args)
    except SystemExit:
        pass
    except Exception:
        return None
    out = buf.getvalue().strip()
    if not out.startswith("{"):
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _as_date(iso: Any) -> Optional[str]:
    return iso[:10] if isinstance(iso, str) and iso else None


def _live_reading(spec: tuple) -> dict:
    key, label, lens, args, vfield, sfield, fmt, unit, source = spec
    base = {"id": key, "label": label, "lens": lens, "unit": unit, "source": source}
    data = _run_json(args)
    if data is None:
        return {**base, "status": "unavailable",
                "reason": "no data (missing key, provider error, or non-JSON output)"}
    as_of = _as_date(data.get("as_of") or data.get("date") or data.get("observation_date"))
    value = data.get(vfield) if vfield else None
    state = data.get(sfield) if sfield else None
    out = {**base, "status": "ok", "as_of": as_of, "fmt": fmt}
    if isinstance(value, (int, float)):
        out["value"] = round(float(value), 6)
    if isinstance(state, str):
        out["state"] = state
    if out.get("value") is None and out.get("state") is None:
        out["status"] = "unavailable"
        out["reason"] = "fetched but no recognised value/state field"
    return out


# Deterministic synthetic readings — calm-market illustration, clearly labelled.
_DEMO_VALUES = {
    "ECB-CISS-US": ("value", 0.071, "2026-06-26"),
    "ECB-CISS-EA": ("value", 0.089, "2026-06-26"),
    "ECB-CISS-UK": ("value", 0.064, "2026-06-26"),
    "STLFSI4": ("value", -0.42, "2026-06-20"),
    "YIELD-CURVE": ("value", 0.18, "2026-06-25"),
    "MACRO-REGIME": ("state", "RISK_ON", "2026-06-25"),
    "SAHM": ("value", 0.13, "2026-05-31"),
    "CREDIT-SPREAD": ("value", 312.0, "2026-06-25"),
}


def _demo_reading(spec: tuple) -> dict:
    key, label, lens, _args, _vf, _sf, fmt, unit, source = spec
    kind, val, as_of = _DEMO_VALUES[key]
    out = {"id": key, "label": label, "lens": lens, "unit": unit, "source": source,
           "status": "ok", "as_of": as_of, "fmt": fmt, "demo": True}
    out[kind] = val
    return out


# ── financialdata.net lens: equity volatility (VIX) systemic stress ──
_FD_LENS = {"id": "EQUITY-VIX", "label": "Equity volatility · VIX",
            "lens": "System stress", "unit": "VIX pts", "source": "financialdata.net"}


def _fd_unavailable(reason: str) -> dict:
    return {**_FD_LENS, "status": "unavailable", "reason": reason}


def _classify_vix(v: float) -> str:
    if v < 15:
        return "CALM"
    if v < 20:
        return "NORMAL"
    if v < 30:
        return "ELEVATED"
    return "STRESS"


def _equity_stress_live(settings) -> dict:
    """Latest VIX close (+ S&P daily move) via financialdata.net. Never raises.

    Uses ``index-prices`` (daily close, Standard tier, newest record first) which
    is more reliable than the market-hours-only real-time quotes feed.
    """
    from wavervanir_api.providers.financialdata import index_prices

    try:
        vix = index_prices(settings, "^VIX")
    except Exception as exc:
        return _fd_unavailable(f"{type(exc).__name__}")
    if not vix or not isinstance(vix[0].get("close"), (int, float)):
        return _fd_unavailable("VIX price not returned (check key / subscription)")
    level = round(float(vix[0]["close"]), 2)
    out = {**_FD_LENS, "status": "ok", "as_of": str(vix[0].get("date", ""))[:10],
           "fmt": "level", "value": level, "state": _classify_vix(level)}
    try:
        spx = index_prices(settings, "^GSPC")
        if spx and len(spx) >= 2 and float(spx[1].get("close") or 0):
            chg = (float(spx[0]["close"]) / float(spx[1]["close"]) - 1.0) * 100.0
            out["interpretation"] = f"S&P 500 {chg:+.2f}%"
    except Exception:
        pass
    return out


def _equity_stress_demo() -> dict:
    return {**_FD_LENS, "status": "ok", "as_of": "2026-06-26", "fmt": "level",
            "value": 14.2, "state": "CALM", "interpretation": "S&P 500 +0.31%", "demo": True}


def _apply_last_good(readings: list[dict], prev_readings: Optional[list[dict]]) -> list[dict]:
    """Backfill any unavailable reading with the last good value for that lens.

    A transient upstream miss (timeout, provider blip) should not blank a card
    when we served a real value an hour ago — that reads as "the product is
    broken" when it is merely "ECB SDMX was briefly slow". For each reading that
    is not ``ok``, if the previous snapshot held an ``ok`` reading for the same
    lens id, carry it forward marked ``stale`` (its original ``as_of`` is
    preserved, so the staleness is visible). Returns a new list; never mutates
    the inputs.
    """
    if not prev_readings:
        return readings
    prev_ok = {r.get("id"): r for r in prev_readings if r.get("status") == "ok"}
    out: list[dict] = []
    for r in readings:
        if r.get("status") != "ok" and r.get("id") in prev_ok:
            carried = dict(prev_ok[r["id"]])
            carried["stale"] = True
            carried["stale_reason"] = r.get("reason", "live fetch unavailable")
            out.append(carried)
        else:
            out.append(r)
    return out


def build(*, source: str = "live", generated_at_utc: Optional[str] = None, settings=None,
          prev_readings: Optional[list[dict]] = None) -> dict:
    specs = _lens_specs()
    if source == "demo":
        readings = [_demo_reading(s) for s in specs]
        readings.append(_equity_stress_demo())
        readings.extend(desk_lenses.conditions_readings(None, source="demo"))
        disclaimer = ("DEMONSTRATION readings — synthetic, not live market data. "
                      "Use source=live for current public readings.")
    else:
        readings = []
        for s in specs:
            r = _call_with_timeout(lambda spec=s: _live_reading(spec), LIVE_LENS_TIMEOUT_S)
            if r is None:
                r = {"id": s[0], "label": s[1], "lens": s[2], "unit": s[7],
                     "source": s[8], "status": "unavailable", "reason": "upstream timeout"}
            readings.append(r)
        # financialdata.net lens (needs the API key on ``settings``).
        if settings is not None:
            fd = _call_with_timeout(lambda: _equity_stress_live(settings), LIVE_LENS_TIMEOUT_S)
            readings.append(fd if fd is not None else _fd_unavailable("upstream timeout"))
            readings.extend(desk_lenses.conditions_readings(settings, source="live"))
        else:
            readings.append(_fd_unavailable("FINANCIALDATA_API_KEY not configured"))
            for _nid in desk_lenses.NEW_LENS_IDS:
                readings.append(desk_lenses._unavailable(_nid, "FINANCIALDATA_API_KEY not configured"))
        disclaimer = ("Latest available public readings, each dated to its provider's "
                      "last publication. Risk measurement — not investment advice.")
    readings = _apply_last_good(readings, prev_readings)
    ok = [r for r in readings if r.get("status") == "ok"]
    stale = [r for r in ok if r.get("stale")]
    return {
        "schema": SCHEMA,
        "source": source,
        "generated_at_utc": generated_at_utc,
        "readings": readings,
        "summary": {"total": len(readings), "live": len(ok) - len(stale),
                    "stale": len(stale), "unavailable": len(readings) - len(ok)},
        "sources": sorted({r["source"] for r in readings}),
        "disclaimer": disclaimer,
        "output_sha256": sha256_of_obj(readings),
    }


# ── cache (serve the slow multi-upstream live build instantly) ──────────────

CONDITIONS_CACHE_TTL_S = 3600  # 1 hour


def _aware(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_dt.timezone.utc)


def _cache_get(settings, key: str):
    from sqlmodel import Session, select

    from wavervanir_api.db import SnapshotCache, get_engine

    engine = get_engine(settings.db_url)
    with Session(engine) as s:
        row = s.exec(select(SnapshotCache).where(SnapshotCache.cache_key == key)).first()
        return (row.generated_at, row.payload_json) if row else None


def _cache_set(settings, key: str, source: str, payload_json: str) -> None:
    from sqlmodel import Session, select

    from wavervanir_api.db import SnapshotCache, get_engine

    engine = get_engine(settings.db_url)
    with Session(engine) as s:
        row = s.exec(select(SnapshotCache).where(SnapshotCache.cache_key == key)).first()
        now = _dt.datetime.now(_dt.timezone.utc)
        if row:
            row.generated_at, row.payload_json, row.source = now, payload_json, source
        else:
            row = SnapshotCache(cache_key=key, source=source, generated_at=now,
                                payload_json=payload_json)
        s.add(row)
        s.commit()


def cache_peek(settings, source: str = "live") -> Optional[dict]:
    """Cheap read-only look at the cached conditions snapshot for readiness checks.

    Returns ``{"age_s": int, "live": int|None, "generated_at": str}`` or ``None``
    if the cache is cold. Never rebuilds (so /health/ready stays fast)."""
    got = _cache_get(settings, f"conditions:{source}")
    if not got:
        return None
    gen_at, payload_json = got
    age = int((_dt.datetime.now(_dt.timezone.utc) - _aware(gen_at)).total_seconds())
    try:
        live = json.loads(payload_json).get("summary", {}).get("live")
    except (json.JSONDecodeError, AttributeError):
        live = None
    return {"age_s": age, "live": live, "generated_at": _aware(gen_at).isoformat()}


def build_cached(*, source: str, settings, max_age_s: int = CONDITIONS_CACHE_TTL_S,
                 force: bool = False, generated_at_utc: Optional[str] = None) -> dict:
    """Return a cached conditions snapshot if fresher than ``max_age_s``, else
    recompute (the slow path), cache it, and return it. Adds a ``cache`` field."""
    key = f"conditions:{source}"
    # Load any existing snapshot regardless of force/TTL: it both serves a fresh
    # cache hit AND seeds the last-good fallback when we recompute.
    got = _cache_get(settings, key)
    if got and not force:
        gen_at, payload_json = got
        age = (_dt.datetime.now(_dt.timezone.utc) - _aware(gen_at)).total_seconds()
        if age <= max_age_s:
            snap = json.loads(payload_json)
            snap["cache"] = {"hit": True, "age_s": int(age)}
            return snap
    prev_readings = None
    if got:
        try:
            prev_readings = json.loads(got[1]).get("readings")
        except (json.JSONDecodeError, AttributeError):
            prev_readings = None
    snap = build(source=source, settings=settings, generated_at_utc=generated_at_utc,
                 prev_readings=prev_readings)
    _cache_set(settings, key, source, json.dumps(snap))
    snap["cache"] = {"hit": False, "age_s": 0}
    return snap


# ── methodology detail (the deep-dive behind each lens) ─────────────────────
# Each entry is a structured write-up: what the lens measures, how CBSRM
# reproduces it from public data, how to read the number (with thresholds), and
# the primary academic / institutional reference. This is the product's
# intellectual content — served from the API so it is one auditable source of
# truth for both the terminal and any documentation.
LENS_DETAIL: dict[str, dict] = {
    "ECB-CISS-US": {
        "what": "The Composite Indicator of Systemic Stress (CISS) collapses 15 raw "
                "stress measures spanning five market segments — money markets, bond "
                "markets, equity markets, financial intermediaries, and foreign exchange "
                "— into a single 0–1 index for the U.S. financial system.",
        "how": "Each raw measure is transformed to its recursive empirical CDF, grouped "
               "into five sub-indices, then aggregated with a time-varying cross-segment "
               "correlation matrix — so the headline rises more when stress is broad-based "
               "across segments (the systemic feature) than when it is isolated to one. "
               "CBSRM pulls the published series directly from the ECB SDMX Data Portal "
               "and reproduces the level.",
        "interpret": "0 = no stress, 1 = historical maximum. Bands: < 0.27 calm · "
                     "0.27–0.50 elevated · > 0.50 severe. The defining property is the "
                     "correlation weighting: a reading is 'systemic' only when several "
                     "segments are stressed at once.",
        "reference": "Holló, Kremer & Lo Duca (2012), ECB Working Paper No. 1426.",
    },
    "ECB-CISS-EA": {
        "what": "The original euro-area CISS — the same five-segment systemic-stress "
                "construction applied to the euro-area financial system.",
        "how": "Identical methodology to the U.S. variant (recursive-CDF sub-indices "
               "aggregated with a time-varying correlation matrix), computed by the ECB "
               "over euro-area instruments. CBSRM reads the published series from ECB SDMX.",
        "interpret": "0 = no stress, 1 = historical maximum. Bands: < 0.27 calm · "
                     "0.27–0.50 elevated · > 0.50 severe. This is the flagship series the "
                     "ECB itself monitors for the euro area.",
        "reference": "Holló, Kremer & Lo Duca (2012), ECB Working Paper No. 1426.",
    },
    "ECB-CISS-UK": {
        "what": "The CISS systemic-stress construction applied to the United Kingdom "
                "financial system — a cross-check that lets you compare stress regimes "
                "across the three major Western blocs on one scale.",
        "how": "Same recursive-CDF, correlation-weighted aggregation as the other CISS "
               "variants, computed over UK instruments and published via ECB SDMX. CBSRM "
               "reproduces the level from the public flow.",
        "interpret": "0 = no stress, 1 = historical maximum. Bands: < 0.27 calm · "
                     "0.27–0.50 elevated · > 0.50 severe. Divergence between US/EA/UK CISS "
                     "flags whether stress is local or globally synchronised.",
        "reference": "Holló, Kremer & Lo Duca (2012), ECB Working Paper No. 1426.",
    },
    "STLFSI4": {
        "what": "The St. Louis Fed Financial Stress Index (v4) measures the degree of "
                "financial stress in U.S. markets from 18 weekly series — 7 interest "
                "rates, 6 yield spreads, and 5 other indicators (e.g. the VIX, breakevens).",
        "how": "The 18 series are combined by principal-component analysis; the first "
               "principal component — the common factor driving all of them — is extracted "
               "and standardised so 0 = average financial-market conditions. CBSRM reads "
               "STLFSI4 from FRED.",
        "interpret": "0 = normal; each unit ≈ one standard deviation of stress. > 0 = "
                     "above-average stress, < 0 = below-average. Bands: < 1 normal · 1–3 "
                     "elevated · > 3 severe.",
        "reference": "Federal Reserve Bank of St. Louis, STLFSI4 (FRED).",
    },
    "YIELD-CURVE": {
        "what": "The model-implied probability of a U.S. recession 12 months ahead, read "
                "off the slope of the Treasury yield curve (10-year minus 3-month).",
        "how": "A probit model maps the T10Y3M term spread to a recession probability "
               "(the Estrella–Mishkin specification): a flat or inverted curve historically "
               "precedes recessions by about a year. CBSRM pulls T10Y3M from FRED and "
               "applies the calibrated probit link.",
        "interpret": "0–1 probability. Bands: < 0.30 low · 0.30–0.50 watch · > 0.50 high. "
                     "Curve inversion (negative spread) is the classic warning; the probit "
                     "turns the depth of inversion into a probability.",
        "reference": "Estrella & Mishkin (1998); NY Fed yield-curve recession model.",
    },
    "MACRO-REGIME": {
        "what": "A four-state read on the macro environment — RISK_ON, TRANSITION_UP, "
                "TRANSITION_DOWN, RISK_OFF — built from a composite of growth, inflation, "
                "and financial-conditions signals.",
        "how": "CBSRM standardises several FRED macro series into a composite z-score and "
               "applies state thresholds plus transition logic to label the current regime. "
               "The output is categorical, so it carries a label rather than a numeric "
               "history series.",
        "interpret": "RISK_ON = supportive (growth firm, conditions easy); RISK_OFF = "
                     "defensive (deteriorating growth / tightening); the TRANSITION states "
                     "flag the turn. Used as a top-of-funnel filter over the other lenses.",
        "reference": "CBSRM composite-regime construction; cf. Hamilton (1989) regime-switching.",
    },
    "SAHM": {
        "what": "The Sahm Rule — a real-time recession indicator based on how far the "
                "unemployment rate has risen off its recent low.",
        "how": "Computed as the 3-month moving average of the U-3 unemployment rate minus "
               "its minimum over the prior 12 months. CBSRM pulls UNRATE from FRED and "
               "evaluates the rule.",
        "interpret": "Units = percentage points. A reading ≥ 0.50 pp signals a recession "
                     "has likely already begun. Bands: < 0.50 normal · ≥ 0.50 trigger. "
                     "Designed to fire promptly with very few historical false positives.",
        "reference": "Claudia Sahm (2019), The Hamilton Project; FRED SAHMREALTIME.",
    },
    "CREDIT-SPREAD": {
        "what": "The U.S. high-yield corporate option-adjusted spread (OAS) — the extra "
                "yield demanded to hold sub-investment-grade credit over Treasuries — a "
                "market-priced gauge of default and tail risk.",
        "how": "CBSRM reads the ICE BofA US High Yield OAS (BAMLH0A0HYM2) from FRED and "
               "classifies the regime by spread level. OAS removes embedded optionality so "
               "the spread reflects pure credit-risk premium.",
        "interpret": "Units = basis points. Bands: < 600 bps benign · 600–1000 widening · "
                     "> 1000 stress. Spreads blow out fastest at the onset of credit "
                     "events, making this a leading tail-risk signal.",
        "reference": "ICE BofA US High Yield Index OAS (FRED BAMLH0A0HYM2).",
    },
    "EQUITY-VIX": {
        "what": "The CBOE Volatility Index — 30-day implied volatility of the S&P 500 "
                "backed out of option prices — the market's 'fear gauge'.",
        "how": "CBOE computes VIX model-free from a strip of out-of-the-money SPX options "
               "(a variance-swap replication). CBSRM reads the latest ^VIX daily close via "
               "financialdata.net index-prices and classifies the level.",
        "interpret": "Units = annualised volatility points. Bands: < 15 calm · 15–20 "
                     "normal · 20–30 elevated · > 30 stress. Spikes are coincident with "
                     "equity drawdowns; persistently low VIX can flag complacency.",
        "reference": "CBOE VIX White Paper (model-free implied volatility).",
    },
    "XBORDER-DY": {
        "what": "The Diebold–Yilmaz total connectedness index — how much of the variation "
                "across major world equity markets is driven by cross-market spillovers "
                "rather than own-market shocks. A direct measure of global contagion.",
        "how": "CBSRM fits a VAR(2) to the returns of seven indices (S&P 500, FTSE 100, "
               "DAX, Nikkei, Hang Seng, CAC 40, Euro Stoxx 50), computes a generalized "
               "(Pesaran–Shin, order-invariant) forecast-error variance decomposition at "
               "horizon H=10, and sums the off-diagonal (cross-market) share — all in "
               "numpy from financialdata.net index-prices.",
        "interpret": "Units = % connectedness (0–100). Bands: < 50 low · 50–70 elevated · "
                     "> 70 high. Independent markets → near 0; markets coupled in a crisis "
                     "→ 70–90. Rising connectedness means a local shock is more likely to "
                     "propagate globally.",
        "reference": "Diebold & Yilmaz (2012), 'Better to Give than to Receive'.",
    },
    "OPTIONS-TAIL": {
        "what": "An options-implied tail-risk gauge — the relative richness of downside "
                "protection (puts) versus upside (calls), read through near-the-money "
                "vega-weighted option pricing.",
        "how": "CBSRM pulls option-greeks for the index and forms the ratio of put vega to "
               "call vega near the money. On the current data tier the chain is LEAPS-led "
               "and lacks per-contract IV/OI, so this lens is best-effort and longer-dated; "
               "a ratio above 1 means the market pays up more for downside convexity.",
        "interpret": "put÷call vega ratio. Bands: < 1.0 balanced · 1.0–1.3 put-skew "
                     "(hedging demand) · > 1.3 tail-bid (crash protection in demand). "
                     "Rising skew flags growing demand for tail hedges.",
        "reference": "Volatility-skew / risk-reversal and option-implied tail-risk literature.",
    },
    "FUND-FRAGILITY": {
        "what": "A fund-flow fragility gauge — net redemptions as a share of assets across "
                "a fund sample, a proxy for forced-selling / liquidity-spiral risk in the "
                "asset-management sector.",
        "how": "CBSRM aggregates reported share sales and share redemptions against net "
               "assets across an AUM-weighted fund sample (mutual-fund statistics from "
               "financialdata.net) into a net 3-month redemption ratio.",
        "interpret": "Units = % of assets (net, 3-month). Bands: < 0 inflows (healthy) · "
                     "0–2% mild outflows · > 2% outflows (fragility). Heavy net redemptions "
                     "can force funds to sell into falling markets, amplifying stress — the "
                     "run-on-funds channel.",
        "reference": "ICI/SEC fund-flow analysis; fire-sale literature (Shleifer–Vishny).",
    },
    "ESG-TRANSITION": {
        "what": "A climate-transition systemic-risk gauge — mean environmental-risk "
                "exposure across industries, a top-down read on how exposed the economy is "
                "to a disorderly low-carbon transition (stranded assets, carbon repricing).",
        "how": "CBSRM averages the environmental-risk score across ~64 industries "
               "(industry-ESG scores from financialdata.net) into a single 0–100 "
               "transition-risk level, aligned with BIS/NGFS framing of climate as a source "
               "of systemic financial risk.",
        "interpret": "Units = 0–100 environmental risk. Bands: < 15 low · 15–25 moderate · "
                     "> 25 high. Higher = more of the economy exposed to transition shocks; "
                     "a forward-looking, slow-moving systemic factor, not a timing signal.",
        "reference": "BIS 'green swan' (2020); NGFS climate scenarios.",
    },
}


def methodology() -> dict:
    """Lens catalog + the deep-dive methodology behind each lens.

    Each entry carries a structured ``detail`` (what / how / interpret /
    reference) so the terminal can render a click-through write-up and the
    methodology is one auditable source of truth.
    """
    specs = _lens_specs()
    rows = [(s[0], s[1], s[2], s[7], s[8]) for s in specs]
    rows.append((_FD_LENS["id"], _FD_LENS["label"], _FD_LENS["lens"],
                 _FD_LENS["unit"], _FD_LENS["source"]))
    for i in desk_lenses.NEW_LENS_IDS:
        m = desk_lenses.NEW_LENS_META[i]
        rows.append((i, m["label"], m["lens"], m["unit"], m["source"]))
    lenses = [
        {"id": rid, "label": label, "lens": lens, "unit": unit, "source": source,
         "detail": LENS_DETAIL.get(rid)}
        for (rid, label, lens, unit, source) in rows
    ]
    return {
        "product": "CBSRM",
        "note": f"{len(lenses)} systemic-risk lenses, each reproduced from public data — "
                "click any lens for the full methodology.",
        "lenses": lenses,
    }
