# CBSRM MCP Server — Developer Guide

**Governed systemic risk, agent-callable.** The CBSRM MCP server exposes the CBSRM
Desk engines as [Model Context Protocol](https://modelcontextprotocol.io) tools, so an
institution's AI copilot — Claude Desktop, a custom agent, any MCP client — can query
systemic risk directly. **Every response carries a reproducibility SHA-256 + provenance**,
so an agent's answer is content-addressed and audit-traceable — the trust gap a regulated
institution has when it lets an LLM touch risk numbers.

Source: `api/src/wavervanir_api/mcp_server.py` · Boundary: imports only the public
`cbsrm` package (never internal VolanX; AST-enforced).

---

## Install & run

```bash
cd api
pip install -e '.[mcp]'        # adds the MCP SDK on top of the core API
python -m wavervanir_api.mcp_server     # or: cbsrm-mcp   (stdio transport)
```

**Environment** (the institution supplies its own keys; `source="demo"` works offline):

| Var | Purpose |
|---|---|
| `FINANCIALDATA_API_KEY` | market data — cockpit, SRISK, options/FX/commodities |
| `FRED_API_KEY` | FRED-backed stress / macro lenses |

---

## Tools

| Tool | What it returns |
|---|---|
| `systemic_conditions(source="live")` | 13-lens systemic-risk snapshot (CISS, Fed stress, yield-curve, VIX, Diebold-Yilmaz spillover, ESG, …) |
| `lens_detail(lens_id, source="live")` | history + stats (z-score, percentile, bands) for one lens |
| `methodology()` | per-lens what / how / interpret / reference catalog |
| `risk_profile(symbol)` | institutional cross-asset profile for **any** symbol (^GSPC, EURUSD, GC, BTCUSD, AAPL): Sharpe/Sortino, vol, beta, VaR/CVaR, drawdown, stress, chart data |
| `cockpit_group(group="us-benchmarks")` | risk grid for a watchlist group (global-indices, fx-majors, commodities, us-megacaps, crypto) |
| `crisis_dossier(window_id)` | governed crisis dossier — DebtRank, stress channels, cross-crisis (2008Q4/2020Q1/2023Q1); reproducible SHA-256 |
| `systemic_capital_shortfall()` | live SRISK Σ + per-firm + ΔCoVaR across major US banks (NYU V-Lab / Adrian-Brunnermeier) |
| `model_validation()` | SR 26-2 MRM binder — inventory, conceptual soundness, SRISK sensitivity sweep, MC convergence, attestation |

Every tool result includes a `_governance` block:
```json
"_governance": {
  "reproducible": true,
  "sha256": "…",
  "as_of": "2026-06-26",
  "note": "Computed from public data; content-addressed and audit-traceable (CBSRM, SR 26-2). Risk measurement, not investment advice."
}
```

---

## Connect to Claude Desktop

Add to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`,
Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "cbsrm-systemic-risk": {
      "command": "python",
      "args": ["-m", "wavervanir_api.mcp_server"],
      "env": {
        "FINANCIALDATA_API_KEY": "<your key>",
        "FRED_API_KEY": "<your key>"
      }
    }
  }
}
```

Use the absolute path to the venv's python (e.g. `.../api/.venv/bin/python`) if the
package isn't on the global path. Restart Claude Desktop; the CBSRM tools appear.

---

## Example agent prompts

- *"What's systemic stress right now, and which lens is most elevated?"* → `systemic_conditions`
- *"Give me the risk profile for the Nikkei and gold."* → `risk_profile("^N225")`, `risk_profile("GC")`
- *"Which US bank carries the most capital shortfall in a crisis?"* → `systemic_capital_shortfall`
- *"Pull the 2008 crisis dossier and the cross-crisis DebtRank comparison."* → `crisis_dossier("2008Q4")`
- *"Show me the SR 26-2 validation package for the SRISK model."* → `model_validation`

Because each response is content-addressed, the agent can **cite the SHA-256** and the
result can be reproduced and audited later — which is exactly what a model-risk function
needs before it trusts an AI-surfaced risk number.

---

## Notes

- The MCP server is **stateless** for the data tools (no DB, no user auth) — it runs with
  the institution's own data keys. Gate distribution by who you hand the package to.
- Heavy tools (`systemic_capital_shortfall`, `model_validation`) run live compute (a few
  seconds); agents wait for the result.
- The same engines back the web terminal — the MCP is a thin, governed wrapper, so the
  numbers an agent sees match the terminal exactly.
