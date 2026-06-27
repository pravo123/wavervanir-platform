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
LIVE_LENS_TIMEOUT_S = 6.0


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


def build(*, source: str = "live", generated_at_utc: Optional[str] = None, settings=None) -> dict:
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
    ok = [r for r in readings if r.get("status") == "ok"]
    return {
        "schema": SCHEMA,
        "source": source,
        "generated_at_utc": generated_at_utc,
        "readings": readings,
        "summary": {"total": len(readings), "live": len(ok),
                    "unavailable": len(readings) - len(ok)},
        "sources": sorted({r["source"] for r in readings}),
        "disclaimer": disclaimer,
        "output_sha256": sha256_of_obj(readings),
    }


def methodology() -> dict:
    """Static lens catalog — the systemic-risk methodology CBSRM reproduces."""
    specs = _lens_specs()
    return {
        "product": "CBSRM",
        "note": "Eight public systemic-risk lenses, each reproduced from public data.",
        "lenses": [
            {"id": s[0], "label": s[1], "lens": s[2], "unit": s[7], "source": s[8]}
            for s in specs
        ] + [
            {"id": _FD_LENS["id"], "label": _FD_LENS["label"], "lens": _FD_LENS["lens"],
             "unit": _FD_LENS["unit"], "source": _FD_LENS["source"]}
        ] + [
            {"id": i, "label": desk_lenses.NEW_LENS_META[i]["label"],
             "lens": desk_lenses.NEW_LENS_META[i]["lens"],
             "unit": desk_lenses.NEW_LENS_META[i]["unit"],
             "source": desk_lenses.NEW_LENS_META[i]["source"]}
            for i in desk_lenses.NEW_LENS_IDS
        ],
    }
