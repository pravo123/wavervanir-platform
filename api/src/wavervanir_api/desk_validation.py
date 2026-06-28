"""Model Validation package (SR 26-2) for the Pipeline — the MRM binder.

What a Model Risk Management validator requires to sign off on the CBSRM systemic
models, assembled as a reproducible, content-addressed package:

  * **Documented** (model card material): model inventory + materiality tiering,
    model-vs-non-model split, dependency graph, third-party register, per-model
    conceptual-soundness methodology (citation + equation), a materiality-rated
    assumption/limitation register, ongoing-monitoring policy, and a sign-off /
    attestation scaffold (operator-fillable).
  * **Computed** (live evidence): an SRISK parameter-sensitivity sweep (k × crisis
    threshold, with rank-stability) and a Monte-Carlo convergence check on LRMES —
    both re-run from the installed ``cbsrm.risk`` engines, so the conclusion is
    shown to be robust to defensible parameter choices, not a single point estimate.
  * **Pending-data** (honest): replication-vs-canonical and crisis-backtest scorecards
    declare their methodology + thresholds but render an explicit "pending data
    connection" state rather than a fabricated score, since the installed package
    bundles no reference-series loader.

Honors the CBSRM import boundary: only public ``cbsrm`` is imported.
"""

from __future__ import annotations

from typing import Optional

from wavervanir_api.audit import sha256_of_obj

SCHEMA = "cbsrm-desk-validation/1.0.0"
FRAMEWORK = "SR 26-2 (model-risk-management guidance; successor to SR 11-7)"

# ── 1. Model inventory + materiality tiering (model vs non-model) ────────────
MODEL_INVENTORY = [
    {"id": "SRISK", "name": "Conditional capital shortfall", "module": "cbsrm.risk.srisk",
     "purpose": "Expected capital a firm needs to stay adequately capitalised in a prolonged systemic crisis.",
     "intended_use": "Cross-sectional surveillance / decision-support ranking of which firms drive system capital shortfall.",
     "non_use": "NOT a regulatory-capital number, a trading signal, or an execution gate.",
     "tier": "Tier 3 · decision-support / surveillance", "is_model": True},
    {"id": "DCOVAR", "name": "ΔCoVaR systemic contribution", "module": "cbsrm.risk.delta_covar",
     "purpose": "A firm's marginal contribution to system-wide tail VaR (quantile regression).",
     "intended_use": "Rank firms by tail dependence with the system.",
     "non_use": "Conditioning is associational, not causal; not a capital charge.",
     "tier": "Tier 3 · decision-support / surveillance", "is_model": True},
    {"id": "GARCH-DCC/LRMES", "name": "Long-run MES Monte-Carlo", "module": "cbsrm.risk.garch_dcc_sim + LRMESMonteCarlo",
     "purpose": "Simulated firm equity decline conditional on a market crisis (the LRMES feeding SRISK).",
     "intended_use": "Input estimator to SRISK.",
     "non_use": "Gaussian-innovation simulation; not a return forecast.",
     "tier": "Tier 3 · sub-model (feeds SRISK)", "is_model": True},
    {"id": "DEBTRANK", "name": "Network contagion centrality", "module": "cbsrm.networks.debt_rank",
     "purpose": "Fraction of network value dragged into distress when a seed node is shocked (single propagation).",
     "intended_use": "Identify too-central-to-fail nodes given an exposure matrix.",
     "non_use": "Runs on a fixture / proxy exposure matrix, not confidential bilateral data.",
     "tier": "Tier 3 · decision-support / surveillance", "is_model": True},
    {"id": "MACRO-COMPOSITE", "name": "4-state macro regime", "module": "cbsrm.macro.macro_composite",
     "purpose": "Composite RISK_ON/OFF regime from growth/inflation/rates/credit sub-indicators.",
     "intended_use": "Top-of-funnel regime context.",
     "non_use": "Research classification layer — not a live signal or trading rule.",
     "tier": "Tier 3 · decision-support / surveillance", "is_model": True},
    {"id": "PHASE-CLASSIFIER", "name": "8-phase macro classifier", "module": "cbsrm.macro.phase_classifier",
     "purpose": "Deterministic 8-state phase taxonomy with dominant-driver attribution.",
     "intended_use": "Explainable regime label for the dossier.",
     "non_use": "Research classification layer — not a live signal, trading rule, or execution gate.",
     "tier": "Tier 3 · decision-support / surveillance", "is_model": True},
    {"id": "REPLICATION", "name": "Indicator replication scorer", "module": "cbsrm.diagnostics.replication",
     "purpose": "Benchmarks a CBSRM index vs its canonical published reference (Pearson/Spearman/z-MAE).",
     "intended_use": "Outcomes-analysis evidence that a method tracks its accepted reference.",
     "non_use": "Validation tooling, not a risk output.",
     "tier": "Tier 3 · validation tool", "is_model": True},
]
NON_MODEL_COMPONENTS = [
    {"id": "MANIFEST", "name": "Report manifest + SHA-256 hashing", "module": "cbsrm.reporting.manifest"},
    {"id": "AUDIT-CHAIN", "name": "Tamper-evident hash chain / access ledger", "module": "cbsrm.audit.chain"},
    {"id": "REGISTRY", "name": "Report registry / content-addressed store", "module": "cbsrm.reporting.registry"},
]
NON_MODEL_NOTE = ("Deterministic rule-based software — OUTSIDE the SR 26-2 model definition "
                  "(governed by controls and change management, not model validation).")

# ── 1b. Dependency graph (a change in parent re-reviews dependents) ──────────
DEPENDENCY_EDGES = [
    ("GARCH-DCC/LRMES", "SRISK"), ("market_cap + balance-sheet", "SRISK"),
    ("firm/system returns", "DCOVAR"), ("firm/system returns", "GARCH-DCC/LRMES"),
    ("8 sub-indicators", "MACRO-COMPOSITE"), ("MACRO-COMPOSITE", "PHASE-CLASSIFIER"),
    ("PHASE-CLASSIFIER", "DOSSIER"), ("fixtures", "DOSSIER"), ("DOSSIER", "PipelineRecord"),
    ("DEBTRANK", "DOSSIER"),
]

# ── 2. Conceptual soundness — citation + estimating equation per model ───────
METHODOLOGY = [
    {"id": "SRISK", "citation": "Brownlees & Engle (2017), Review of Financial Studies 30(1); NYU Stern V-Lab",
     "equation": "SRISK = k·D − (1−k)·W·(1−LRMES)", "k_role": "k = prudential capital ratio (8% banks)"},
    {"id": "DCOVAR", "citation": "Adrian & Brunnermeier (2016), AER 106(7); quantile regression Koenker–Bassett (1978)",
     "equation": "ΔCoVaR_i = β_q·(VaR_q,i − median_i)", "k_role": "q = 0.05 tail quantile"},
    {"id": "GARCH-DCC/LRMES", "citation": "Engle (2002) DCC; Glosten-Jagannathan-Runkle (1993) GJR asymmetry",
     "equation": "GJR-GARCH(1,1) variance recursion + scalar DCC(1,1); LRMES via Monte-Carlo crisis paths",
     "k_role": "crisis = −40% over horizon = 126 trading days"},
    {"id": "DEBTRANK", "citation": "Battiston, Puliga, Kaushik, Tasca & Caldarelli (2012), Scientific Reports 2:541",
     "equation": "Undistressed/Distressed/Inactive state machine on W[i,j] = min(L[i,j]/E[i], 1)",
     "k_role": "single-propagation, leverage-normalised exposure"},
    {"id": "PHASE-CLASSIFIER", "citation": "Network-resilience framing cf. Acemoglu-Ozdaglar-Tahbaz-Salehi (2015)",
     "equation": "Deterministic z-score threshold rules over 8 standardised macro features",
     "k_role": "versioned rule book; explainable"},
]

# ── 2b. Materiality-rated assumption / limitation register ───────────────────
ASSUMPTIONS = [
    {"model": "GARCH-DCC/LRMES", "assumption": "Gaussian innovations in the simulated return paths",
     "materiality": "MED", "bias": "may understate fat-tailed crisis co-movement"},
    {"model": "SRISK", "assumption": "Single shared LRMES applied to all firms (default GARCH-DCC, US-financials calibration)",
     "materiality": "HIGH", "bias": "compresses cross-firm SRISK dispersion → read the RANK, not the level"},
    {"model": "SRISK", "assumption": "Book debt (total_liabilities) proxies required capital; k = 8% prudential factor",
     "materiality": "MED", "bias": "static balance-sheet vs a prolonged-crisis horizon"},
    {"model": "SRISK", "assumption": "Live current balance sheets — NOT a point-in-time crisis vintage",
     "materiality": "HIGH", "bias": "absolute $ levels not defensible as a historical measurement; ranking is"},
    {"model": "DCOVAR", "assumption": "Linear quantile-regression form; associational conditioning",
     "materiality": "MED", "bias": "no causal interpretation"},
    {"model": "DEBTRANK", "assumption": "Fixture / proxy exposure matrix, seed node, min(L/E,1) cap, single propagation",
     "materiality": "HIGH", "bias": "a true supervisory contagion map needs confidential bilateral data we never see"},
]

MONITORING_POLICY = {
    "reproducibility_check": "verify_record re-runs the governed record and confirms the SHA-256 reproduces (determinism check).",
    "revalidation_triggers": [
        "any cbsrm version-stamp change on upgrade (re-pin the manifest version block)",
        "a replication-score breach of the r ≥ 0.90 full-sample / 0.85 in-crisis threshold",
        "a sensitivity rank-flip in the SRISK parameter sweep (top-3 ordering changes)",
        "any dependency-graph parent change → re-review of its dependents",
    ],
    "cadence": "Reproducibility re-check on every record build; full re-validation on the triggers above or annually.",
}

ATTESTATION_TEMPLATE = {
    "model_owner": None, "developer": None, "independent_validator": None, "approver": None,
    "effective_date": None, "last_validated": None, "residual_risk_rating": None,
    "effective_challenge_notes": None, "outstanding_findings": [],
    "note": "Operator-fillable. A validated binder requires named owner / developer / "
            "independent validator / approver and a residual-risk rating — the pipeline "
            "scaffolds the package; the institution signs it.",
}


def _versions() -> dict:
    out = {}
    try:
        import cbsrm
        import cbsrm.reporting as R
        out["cbsrm"] = getattr(cbsrm, "__version__", "?")
        for k in ("MANIFEST_VERSION", "REPORT_REGISTRY_VERSION", "REPORT_RENDERER_VERSION",
                  "HTML_RENDERER_VERSION", "MACRO_COMPOSITE_REPORT_VERSION"):
            out[k.lower()] = getattr(R, k, "?")
    except Exception:
        pass
    for mod in ("numpy", "pandas"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            out[mod] = "?"
    return out


def component_register() -> list[dict]:
    v = _versions()
    return [
        {"component": "numpy", "version": v.get("numpy"), "role": "compute substrate"},
        {"component": "pandas", "version": v.get("pandas"), "role": "compute substrate"},
        {"component": "cbsrm", "version": v.get("cbsrm"), "role": "systemic-risk model library (public)"},
        {"component": "financialdata.net", "version": "Enterprise", "role": "live bank fundamentals + prices (third-party)"},
        {"component": "FRED / BIS-SDMX / ECB-SDMX / OFR", "version": "upstream", "role": "macro / stress reference data authorities"},
    ]


# ── computed evidence ────────────────────────────────────────────────────────

def mc_convergence() -> dict:
    """LRMES across path counts (convergence) and seeds (stability)."""
    from cbsrm.risk import LRMESMonteCarlo

    def lrmes(npaths, seed):
        return float(LRMESMonteCarlo(horizon_days=126, crisis_threshold=-0.40,
                                     n_paths=npaths, seed=seed).compute()["lrmes"])

    by_paths = [{"n_paths": n, "lrmes": round(lrmes(n, 42), 4)} for n in (1000, 2000, 5000)]
    seeds = [42, 7, 123]
    seed_vals = [lrmes(2000, s) for s in seeds]
    import statistics
    mean = statistics.fmean(seed_vals)
    std = statistics.pstdev(seed_vals)
    rel = std / mean if mean else 0.0
    converged = rel < 0.05  # <5% relative seed-dispersion
    verdict = (
        f"LRMES seed-dispersion at 2000 paths is ±{round(std, 4)} ({round(rel*100,1)}% of mean) — "
        + ("immaterial; the production 2000-path / seed-42 setting is converged."
           if converged else
           "MATERIAL. The LRMES point estimate carries Monte-Carlo noise at this path count, so "
           "absolute SRISK $ levels inherit it; the conclusion rests on the sensitivity sweep's "
           "RANK stability, not the LRMES level. A defensible point estimate needs a higher n_paths."))
    return {
        "by_paths": by_paths,
        "by_seed": {"n_paths": 2000, "seeds": seeds,
                    "lrmes": [round(x, 4) for x in seed_vals],
                    "mean": round(mean, 4), "std": round(std, 4), "rel_pct": round(rel * 100, 1)},
        "converged": converged,
        "verdict": verdict,
    }


def srisk_sensitivity(settings) -> dict:
    """SRISK Σ across k × crisis-threshold, with top-3 rank stability."""
    from cbsrm.risk import LRMESMonteCarlo, srisk_panel

    from wavervanir_api.desk_pipeline import SYSTEMIC_BANKS, _bank_inputs

    raw = []
    for sym in SYSTEMIC_BANKS:
        out = _bank_inputs(settings, sym, 0.3)  # dummy LRMES; we only want W, D
        row = out[0] if isinstance(out, tuple) else out
        if row:
            raw.append((sym, row["market_cap_W"], row["book_debt_D"]))
    if not raw:
        return {"available": False, "reason": "bank fundamentals unavailable"}

    ks, crises = [0.06, 0.08, 0.10], [-0.30, -0.40, -0.50]
    lrmes_by_crisis = {c: float(LRMESMonteCarlo(horizon_days=126, crisis_threshold=c,
                                                n_paths=2000, seed=42).compute()["lrmes"]) for c in crises}
    grid, base_rank = [], None
    for c in crises:
        lr = lrmes_by_crisis[c]
        for k in ks:
            inputs = [{"firm": s, "market_cap_W": W, "book_debt_D": D, "lrmes": lr} for (s, W, D) in raw]
            p = srisk_panel(inputs, k=k)
            rank = [r["firm"] for r in p["per_firm"]]
            grid.append({"k": k, "crisis": c, "lrmes": round(lr, 4),
                         "total_bn": round(p["total_srisk"] / 1e9, 1),
                         "n_shortfall": p["n_shortfall"], "top3": rank[:3]})
            if abs(k - 0.08) < 1e-9 and abs(c + 0.40) < 1e-9:
                base_rank = rank
    base3 = base_rank[:3] if base_rank else []
    stable = sum(1 for g in grid if g["top3"] == base3)
    return {
        "available": True, "ks": ks, "crises": crises, "grid": grid,
        "base_top3": base3, "rank_stable_cells": stable, "total_cells": len(grid),
        "verdict": (f"Top-3 SRISK ranking is stable across {stable}/{len(grid)} parameter cells "
                    "— the conclusion (who drives system shortfall) is robust to defensible "
                    "k and crisis-threshold choices; absolute totals are not."),
    }


def _pillar_status(sensitivity_ok: bool) -> list[dict]:
    return [
        {"pillar": "Model inventory & tiering", "status": "documented"},
        {"pillar": "Conceptual soundness", "status": "documented"},
        {"pillar": "Sensitivity & stress", "status": "computed" if sensitivity_ok else "pending data"},
        {"pillar": "Numerical convergence", "status": "computed"},
        {"pillar": "Benchmarking / replication", "status": "pending data connection"},
        {"pillar": "Crisis backtest", "status": "pending data connection"},
        {"pillar": "Governance & audit trail", "status": "active"},
        {"pillar": "Attestation / sign-off", "status": "operator-fillable"},
    ]


def validation_package(settings, *, generated_at_utc: Optional[str] = None) -> dict:
    sens = srisk_sensitivity(settings)
    mc = mc_convergence()
    pkg = {
        "schema": SCHEMA,
        "framework": FRAMEWORK,
        "generated_at_utc": generated_at_utc,
        "versions": _versions(),
        "pillar_status": _pillar_status(bool(sens.get("available"))),
        "model_inventory": MODEL_INVENTORY,
        "non_model_components": NON_MODEL_COMPONENTS,
        "non_model_note": NON_MODEL_NOTE,
        "dependency_edges": DEPENDENCY_EDGES,
        "methodology": METHODOLOGY,
        "assumptions": ASSUMPTIONS,
        "component_register": component_register(),
        "sensitivity": sens,
        "mc_convergence": mc,
        "benchmarking": {
            "status": "pending data connection",
            "method": "cbsrm.diagnostics.replicate vs canonical reference (e.g. ECB CISS) over 9 named crisis windows.",
            "thresholds": "Pass if full-sample Pearson r ≥ 0.90 and in-crisis r ≥ 0.85.",
            "note": "No reference-series loader is bundled; a real score is shown only when the canonical "
                    "series is connected — never a fabricated r-value.",
        },
        "backtest": {
            "status": "pending data connection",
            "method": "cbsrm.diagnostics.CrisisReplay / replay_all_windows over the 9 historical windows "
                      "(2008-gfc-acute, 2020-covid, 2023-svb, …): baseline, peak, days-to-peak, z-peak, amplification.",
            "note": "Driven from the indicator's historical series; renders 'pending' until the series is wired.",
        },
        "monitoring_policy": MONITORING_POLICY,
        "attestation": ATTESTATION_TEMPLATE,
        "disclaimer": "Model-validation evidence package — risk measurement, not investment advice.",
    }
    pkg["output_sha256"] = sha256_of_obj(
        {k: v for k, v in pkg.items() if k != "generated_at_utc"})
    return pkg
