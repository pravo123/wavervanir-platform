"""CBSRM MCP server — governed systemic risk as agent-callable tools.

Exposes the CBSRM Desk engines as Model Context Protocol (MCP) tools, so an
institution's AI copilot (or Claude Desktop / any MCP client) can query systemic
risk directly — and **every response carries the reproducibility SHA-256 +
provenance**, the CBSRM moat made machine-callable. Unlike a generic data API, an
agent's answer here is content-addressed and audit-traceable, which is exactly the
trust gap a regulated institution has when it lets an LLM touch risk numbers.

Honors the CBSRM import boundary: imports only the public ``cbsrm`` package (via the
``desk_*`` modules), never any internal VolanX module.

Install + run:
    pip install -e '.[mcp]'
    python -m wavervanir_api.mcp_server          # stdio transport (Claude Desktop, etc.)

Environment (the institution supplies its own keys; demo works without them):
    FINANCIALDATA_API_KEY   market data (cockpit, SRISK, options/FX/commodities)
    FRED_API_KEY            FRED-backed stress / macro lenses
Every tool also accepts ``source="demo"`` where relevant for an offline, deterministic
response.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from wavervanir_api import (
    desk_analytics,
    desk_conditions,
    desk_pipeline,
    desk_riskdesk,
    desk_validation,
)
from wavervanir_api.config import get_settings

mcp = FastMCP("cbsrm-systemic-risk")


def _settings():
    return get_settings()


def _gov(result: Any) -> Any:
    """Stamp every tool response with explicit governance/provenance metadata."""
    if isinstance(result, dict):
        sha = (
            result.get("output_sha256")
            or (result.get("manifest") or {}).get("hashes", {}).get("output_sha256")
        )
        result.setdefault(
            "_governance",
            {
                "reproducible": True,
                "sha256": sha,
                "as_of": result.get("as_of") or result.get("generated_at_utc"),
                "note": ("Computed from public data; content-addressed and "
                         "audit-traceable (CBSRM, SR 26-2 framing). Risk measurement, "
                         "not investment advice."),
            },
        )
    return result


# ── tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def systemic_conditions(source: str = "live") -> dict:
    """Current systemic-risk conditions across 13 lenses — ECB CISS (US/EA/UK), Fed
    financial stress, yield-curve recession probability, Sahm rule, HY credit, VIX, a
    real Diebold-Yilmaz cross-border spillover index, options tail-skew, fund-redemption
    fragility, ESG transition. ``source='demo'`` returns deterministic offline readings."""
    return _gov(desk_conditions.build(source=source, settings=_settings()))


@mcp.tool()
def lens_detail(lens_id: str, source: str = "live") -> dict:
    """History + summary stats (current, z-score, percentile, regime bands) for one lens.
    Example ids: 'EQUITY-VIX', 'XBORDER-DY', 'STLFSI4', 'ESG-TRANSITION'."""
    return _gov(desk_analytics.lens_analytics(_settings(), lens_id, source=source))


@mcp.tool()
def methodology() -> dict:
    """The systemic-risk methodology catalog — per-lens what it measures, how CBSRM
    computes it, how to read it, and the canonical academic reference."""
    return desk_conditions.methodology()


@mcp.tool()
def risk_profile(symbol: str) -> dict:
    """Institutional cross-asset risk for ANY symbol the feed supports — a world index
    (^GSPC, ^N225, ^STI), FX pair (EURUSD), commodity (GC, CL), crypto (BTCUSD), or a US
    stock/ETF (AAPL). Returns Sharpe/Sortino, annualised & EWMA volatility, beta to the
    S&P, a 1D/5D/10D VaR & CVaR table, max drawdown, 50/200-DMA trend, beta-driven macro
    stress, a quant read, and candlestick + projection chart data."""
    p = desk_riskdesk.risk_profile(_settings(), symbol)
    return _gov(p) if p else {"error": "symbol_unavailable", "symbol": (symbol or "").upper()}


@mcp.tool()
def cockpit_group(group: str = "us-benchmarks") -> dict:
    """Risk-metric grid for a curated watchlist group. Groups: 'us-benchmarks',
    'global-indices', 'fx-majors', 'commodities', 'us-megacaps', 'crypto'."""
    return _gov(desk_riskdesk.build(group=group, settings=_settings()))


@mcp.tool()
def crisis_dossier(window_id: str) -> dict:
    """A governed, reproducible crisis-window dossier — system-stress channels, DebtRank
    network contagion, macro regime, narrative, and a cross-crisis comparison. Windows:
    '2008Q4' (GFC), '2020Q1' (COVID), '2023Q1' (SVB). Rebuild yields the same SHA-256."""
    try:
        return _gov(desk_pipeline.build_record(window_id))
    except KeyError:
        return {"error": "unknown_window", "supported": desk_pipeline.available_windows()}


@mcp.tool()
def systemic_capital_shortfall() -> dict:
    """Live SRISK Σ capital-shortfall + per-firm ranking + ΔCoVaR across the major US
    banks (JPMorgan, BofA, Citi, Wells, Goldman, Morgan Stanley), via the NYU V-Lab
    (Brownlees-Engle) and Adrian-Brunnermeier engines from public balance sheets, market
    cap, and prices. Read the ranking, not the absolute level (single shared LRMES caveat)."""
    return _gov(desk_pipeline.systemic_panel(_settings()))


@mcp.tool()
def model_validation() -> dict:
    """The SR 26-2 model-validation binder (MRM package): model inventory + materiality
    tiering, per-model conceptual soundness with citations, a materiality-rated assumption
    register, a computed SRISK parameter-sensitivity sweep (k × crisis threshold with
    rank-stability), an honest Monte-Carlo convergence check, and an attestation scaffold."""
    return _gov(desk_validation.validation_package(_settings()))


def main() -> None:
    """Console entry point (``cbsrm-mcp``) — runs the server on stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
