"""Governed PipelineRecord for the Desk terminal — the "verify" promise.

The Desk pricing card promises **"Governed PipelineRecord + audit-chain access"**.
This module delivers the PipelineRecord half by wrapping cbsrm's *installed*
governed-report machinery (``cbsrm.reporting``) — no unpublished ``cbsrm.composer``
needed.

For a crisis window (2008Q4 / 2020Q1 / 2023Q1) it builds a **deterministic,
content-addressed, version-stamped** record of the CBSRM macro-composite pipeline:
the phase classification + driver features, the rendered governed report, and a
manifest carrying ``output_sha256`` / ``payload_sha256`` plus the cbsrm / registry
/ renderer versions. The record is *reproducible* — rebuilding the same window
yields the same hashes — which is exactly the governance guarantee the Desk sells.
The terminal can therefore pull a record and **verify** it reproduces, and every
access is written to the tamper-evident ledger (the "audit-chain access" half).
"""

from __future__ import annotations

from typing import Optional

REPORT_ID = "macro_composite"
RECORD_SCHEMA = "cbsrm-desk-pipeline-record/1.0.0"

# Human-readable context for each governed window (the crisis the snapshot captures).
_WINDOW_LABELS = {
    "2008Q4": "Global Financial Crisis — Lehman aftermath",
    "2020Q1": "COVID-19 crash — March 2020 liquidity shock",
    "2023Q1": "Regional-bank stress — SVB / Credit Suisse",
}


def _reporting():
    import cbsrm.reporting as R  # public, AST-boundary-allowed

    return R


def _cbsrm_version() -> str:
    import cbsrm

    return getattr(cbsrm, "__version__", "?")


def available_windows() -> list[str]:
    """The governed windows that can be reproduced, or ``[]`` if unavailable."""
    try:
        return list(_reporting().list_macro_composite_windows())
    except Exception:
        return []


def catalog() -> dict:
    """The governed-record catalog: which windows, which versions govern them."""
    R = _reporting()
    windows = available_windows()
    return {
        "schema": RECORD_SCHEMA,
        "product": "CBSRM Desk",
        "record_type": "governed_pipeline_record",
        "report_id": REPORT_ID,
        "windows": [
            {"window_id": w, "label": _WINDOW_LABELS.get(w, w)} for w in windows
        ],
        "versions": {
            "cbsrm": _cbsrm_version(),
            "manifest": getattr(R, "MANIFEST_VERSION", "?"),
            "registry": getattr(R, "REPORT_REGISTRY_VERSION", "?"),
            "renderer": getattr(R, "REPORT_RENDERER_VERSION", "?"),
        },
        "note": ("Each window builds a deterministic, content-addressed record. "
                 "Rebuild any record to verify it reproduces to the same SHA-256 — "
                 "that reproducibility, plus the audit-chained access, is the "
                 "governance guarantee."),
    }


CROSS_WINDOWS = ["2008Q4", "2020Q1", "2023Q1"]


def _diagnostics():
    import cbsrm.diagnostics as D  # public, AST-boundary-allowed

    return D


def _dossier_block(window_id: str) -> Optional[dict]:
    """Deterministic crisis dossier: system-stress channels, DebtRank contagion,
    regime, narrative — composed from cbsrm's fixtures (reproducible)."""
    try:
        D = _diagnostics()
        doss = D.build_crisis_dossier(window_id)
        fix = D.get_fixture_snapshot(window_id)
    except Exception:
        return None
    feat = fix.get("phase_features", {}) or {}
    net = doss.get("network_stress_summary", {}) or {}
    return {
        "title": doss.get("title"),
        "period": doss.get("period"),
        "shock_summary": doss.get("shock_summary"),
        "research_notes": doss.get("research_notes"),
        "phase": doss.get("phase_label"),
        "risk_posture": doss.get("risk_posture"),
        "dominant_drivers": doss.get("dominant_drivers", []),
        # the four supervisory stress channels behind the system-stress gauge
        "stress_channels": {
            "volatility": feat.get("volatility_z"),
            "credit": feat.get("credit_spread_z"),
            "systemic": feat.get("systemic_risk_z"),
            "liquidity": feat.get("liquidity_z"),
        },
        "debt_rank": {
            "value": net.get("debt_rank"), "n_banks": net.get("n_banks"),
            "iterations": net.get("iterations"), "converged": net.get("converged"),
            "seed_node": net.get("seed_node"),
        },
        "macro_events": doss.get("macro_event_scores", []),
    }


def _cross_crisis() -> dict:
    """Three windows, three lenses: DebtRank, volatility-z, and regime score —
    the cross-crisis comparison (network fragility vs benign macro in 2023Q1)."""
    R, D = _reporting(), _diagnostics()
    out = {"windows": CROSS_WINDOWS, "debt_rank": {}, "volatility_z": {}, "regime_score": {}}
    for w in CROSS_WINDOWS:
        try:
            doss = D.build_crisis_dossier(w)
            fix = D.get_fixture_snapshot(w)
            rep = R.build_macro_composite_report(w)
            out["debt_rank"][w] = (doss.get("network_stress_summary", {}) or {}).get("debt_rank")
            out["volatility_z"][w] = (fix.get("phase_features", {}) or {}).get("volatility_z")
            out["regime_score"][w] = (rep.get("phase_classification", {}) or {}).get("score")
        except Exception:
            continue
    return out


def build_record(window_id: str, *, generated_at_utc: Optional[str] = None) -> dict:
    """Build the governed PipelineRecord for ``window_id``.

    Raises ``KeyError`` if the window is not a governed window. The returned
    ``manifest.hashes`` are reproducible: they hash the rendered report and the
    payload, not the wall-clock, so a rebuild yields identical hashes. The
    ``dossier`` + ``cross_crisis`` blocks are likewise deterministic (from
    cbsrm fixtures), so they fold into the governed record.
    """
    if window_id not in available_windows():
        raise KeyError(window_id)
    R = _reporting()
    report = R.build_macro_composite_report(window_id)
    markdown = R.render_macro_composite_markdown(report)
    manifest = R.build_report_manifest(
        report_id=REPORT_ID,
        output_text=markdown,
        output_format="markdown",
        window_id=window_id,
        payload=report,
        generated_at_utc=generated_at_utc,
    )
    phase = report.get("phase_classification", {}) or {}
    return {
        "schema": RECORD_SCHEMA,
        "window_id": window_id,
        "window_label": _WINDOW_LABELS.get(window_id, window_id),
        "title": report.get("title"),
        "phase": phase.get("phase"),
        "phase_score": phase.get("score"),
        "risk_posture": phase.get("risk_posture"),
        "dominant_drivers": phase.get("dominant_drivers", []),
        "phase_features": report.get("phase_features", {}),
        "research_notes": report.get("research_notes"),
        "disclaimer": report.get("disclaimer"),
        "markdown": markdown,
        "manifest": manifest,
        "dossier": _dossier_block(window_id),
        "cross_crisis": _cross_crisis(),
        "generated_at_utc": generated_at_utc,
    }


def verify_record(
    window_id: str, expected_output_sha256: Optional[str] = None
) -> dict:
    """Rebuild ``window_id`` and check reproducibility.

    Always reports ``deterministic`` (a second independent rebuild matches the
    first). If ``expected_output_sha256`` is supplied (e.g. a hash the customer
    recorded earlier), ``reproduced`` is whether the current build matches it —
    proof the governed record has not drifted.
    """
    if window_id not in available_windows():
        raise KeyError(window_id)
    a = build_record(window_id)["manifest"]["hashes"]
    b = build_record(window_id)["manifest"]["hashes"]  # independent rebuild
    deterministic = (
        a["output_sha256"] == b["output_sha256"]
        and a["payload_sha256"] == b["payload_sha256"]
    )
    out = {
        "schema": RECORD_SCHEMA,
        "window_id": window_id,
        "output_sha256": a["output_sha256"],
        "payload_sha256": a["payload_sha256"],
        "deterministic": deterministic,
        "versions": {"cbsrm": _cbsrm_version()},
    }
    if expected_output_sha256 is not None:
        out["expected_output_sha256"] = expected_output_sha256
        out["reproduced"] = expected_output_sha256 == a["output_sha256"]
    else:
        out["reproduced"] = deterministic
    return out


# ── live systemic capital-shortfall panel (SRISK + ΔCoVaR) ───────────────────
# The blueprint flagship: NYU V-Lab-style SRISK + Adrian-Brunnermeier ΔCoVaR on
# the current major-US-bank panel, from public balance sheets + market cap +
# prices. A single shared LRMES (default GARCH-DCC, calibrated for US-financials
# vs S&P) is applied to all firms — documented as a caveat, matching the standard
# simplification. This is LIVE (changes daily) so it is NOT folded into the
# governed record hash; it carries its own as-of stamp.

SYSTEMIC_BANKS = ["JPM", "BAC", "C", "WFC", "GS", "MS"]
SRISK_PARAMS = {"k": 0.08, "horizon_days": 126, "crisis_threshold": -0.40,
                "n_paths": 2000, "seed": 42}
_BANK_NAMES = {"JPM": "JPMorgan Chase", "BAC": "Bank of America", "C": "Citigroup",
               "WFC": "Wells Fargo", "GS": "Goldman Sachs", "MS": "Morgan Stanley"}


def _latest_date(rows) -> Optional[str]:
    """Max ISO trade date (``YYYY-MM-DD``) across price ``rows``, or ``None``.

    financialdata price rows carry a ``date`` field; ISO strings sort
    chronologically, so ``max`` is the freshest vintage regardless of row order.
    """
    if not isinstance(rows, list):
        return None
    dates = [str(r["date"])[:10] for r in rows
             if isinstance(r, dict) and r.get("date")]
    return max(dates) if dates else None


def _bank_inputs(settings, sym, lrmes):
    """(srisk_input, firm_returns, as_of) for one bank, or (None, None, None).

    ``as_of`` is the latest trade date present in the stock-price rows actually
    used (the price-data vintage), for the live panel's data-lineage stamp.
    """
    from wavervanir_api.providers.financialdata import get_json

    try:
        px = get_json(settings, "stock-prices", params={"identifier": sym, "offset": 0})
        mc = get_json(settings, "market-cap", params={"identifier": sym, "offset": 0})
        bs = get_json(settings, "balance-sheet-statements", params={"identifier": sym, "offset": 0})
    except Exception:
        return None, None, None
    if not (isinstance(px, list) and px and isinstance(mc, list) and mc
            and isinstance(bs, list) and bs):
        return None, None, None
    try:
        W = float(mc[0]["market_cap"])
        D = float(bs[0]["total_liabilities"])
    except (KeyError, TypeError, ValueError):
        return None, None, None
    closes = [float(r["close"]) for r in px if isinstance(r.get("close"), (int, float))]
    return ({"firm": sym, "market_cap_W": W, "book_debt_D": D, "lrmes": lrmes},
            closes, _latest_date(px))


def systemic_panel(settings, *, firms=None, generated_at_utc: Optional[str] = None) -> dict:
    """Live SRISK Σ capital-shortfall + per-firm + ΔCoVaR across the bank panel."""
    import numpy as np

    from cbsrm.risk import DeltaCoVaREstimator, LRMESMonteCarlo, srisk_panel
    from wavervanir_api.providers.financialdata import index_prices

    firms = firms or SYSTEMIC_BANKS
    lrmes = float(LRMESMonteCarlo(
        horizon_days=SRISK_PARAMS["horizon_days"], crisis_threshold=SRISK_PARAMS["crisis_threshold"],
        n_paths=SRISK_PARAMS["n_paths"], seed=SRISK_PARAMS["seed"]).compute()["lrmes"])
    as_of_dates: list[str] = []
    try:
        mrows = index_prices(settings, "^GSPC")
        mkt = [float(r["close"]) for r in mrows if isinstance(r.get("close"), (int, float))]
        mret = np.diff(np.log(mkt[::-1])) if len(mkt) > 2 else None
        m_date = _latest_date(mrows)
        if m_date:
            as_of_dates.append(m_date)
    except Exception:
        mret = None

    inputs, covars = [], []
    for sym in firms:
        row, closes, bank_date = _bank_inputs(settings, sym, lrmes)
        if row is None:
            continue
        inputs.append(row)
        if bank_date:
            as_of_dates.append(bank_date)
        if mret is not None and closes and len(closes) > 3:
            fret = np.diff(np.log(np.array(closes[::-1])))
            n = min(len(fret), len(mret))
            try:
                cv = DeltaCoVaREstimator(q=0.05).estimate(
                    firm=sym, firm_returns=fret[-n:], system_returns=mret[-n:])
                covars.append({"firm": sym, "name": _BANK_NAMES.get(sym, sym),
                               "delta_covar": round(float(cv.delta_covar), 5)})
            except Exception:
                pass
    if not inputs:
        return {"available": False, "reason": "bank fundamentals unavailable"}

    as_of = max(as_of_dates) if as_of_dates else None  # freshest vintage actually used

    panel = srisk_panel(inputs, k=SRISK_PARAMS["k"])
    per = [{"firm": r["firm"], "name": _BANK_NAMES.get(r["firm"], r["firm"]),
            "srisk_bn": round(r["srisk"] / 1e9, 2),
            "market_cap_bn": round(next(x["market_cap_W"] for x in inputs if x["firm"] == r["firm"]) / 1e9, 1),
            "book_debt_bn": round(next(x["book_debt_D"] for x in inputs if x["firm"] == r["firm"]) / 1e9, 1),
            "is_shortfall": bool(r.get("is_shortfall"))}
           for r in panel["per_firm"]]
    covars.sort(key=lambda c: c["delta_covar"])  # most tail-dependent first
    return {
        "available": True,
        "as_of": as_of,
        "generated_at_utc": generated_at_utc,
        "lrmes": round(lrmes, 4),
        "params": SRISK_PARAMS,
        "srisk": {
            "total_bn": round(panel["total_srisk"] / 1e9, 2),
            "net_bn": round(panel["total_srisk_net"] / 1e9, 2),
            "n_firms": panel["n_firms"], "n_shortfall": panel["n_shortfall"],
            "per_firm": per,
        },
        "delta_covar": covars,
        "methodology": {
            "srisk": "SRISK (Brownlees-Engle 2017, NYU V-Lab): expected capital shortfall in a "
                     "prolonged market crisis. SRISK = k·Debt − (1−k)·MktCap·(1−LRMES).",
            "delta_covar": "ΔCoVaR (Adrian-Brunnermeier 2016): a firm's marginal contribution to "
                           "system-wide tail VaR, via quantile regression.",
            "lrmes": f"Single shared LRMES {round(lrmes, 3)} from a default GARCH-DCC sim "
                     "(calibrated for US-financials vs S&P) applied to all firms — see caveat.",
            "caveat": "Live read on current balance sheets — NOT a point-in-time crisis vintage. "
                      "GARCH-DCC defaults are calibrated for US financials; treat magnitudes as "
                      "indicative and read the ranking, not the absolute level.",
        },
        "disclaimer": "Systemic-risk measurement of public data — not investment advice.",
    }
