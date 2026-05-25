# Public / Private Boundary

This repo is **public**. The following invariants are enforced by CI and code review.

## Allowed dependencies

| Source | Allowed? | Notes |
| --- | --- | --- |
| `cbsrm` (public, Apache-2.0) | ✅ | Pinned: `cbsrm @ git+https://github.com/pravo123/cbsrm.git@v0.9.0`. |
| `derivatives-risk-framework` (public, Apache-2.0) | ✅ if needed | Currently unused in MVP. |
| Standard libs + FastAPI/Pydantic/SQLModel/httpx/Stripe SDK | ✅ | Pinned in `api/pyproject.toml`. |

## Forbidden dependencies

| Source | Forbidden | Reason |
| --- | --- | --- |
| `volanx`, `VOLANX`, `VOLANX.*` | ❌ | Private strategy / execution / risk-army code. |
| `risk_army`, `gauntlet`, `truth_ledger`, `bayesian_gate` | ❌ | Internal subsystem names. |
| `BrokerRouter`, `OrderSpec`, `place_order` | ❌ | Internal broker abstractions. |
| Tastytrade / IBKR / broker SDKs | ❌ in MVP | No execution surface in public API. |
| Telegram client tokens, bot tokens | ❌ | Owner-only comms. |

## Forbidden content

- Screenshots of VolanX dashboards, gauntlet UI, options-intel pages.
- Internal P&L numbers, expert agent names (TSLA-expert, NVDA-expert, ...), strategy parameter values.
- Operator's broker account IDs, balances, OAuth tokens.
- Any string starting with `TASTYTRADE_`, `IBKR_`, `ROBINHOOD_`, `ALPACA_` outside `.env.example`.

## Enforcement

- `api/tests/test_no_private_imports.py` — AST guard over `api/src/`.
- CI runs the guard on every PR.
- Code review checklist: any new file in `api/` must be inspectable for the above.

## Allowed marketing positioning

- "Hosted CBSRM API"
- "Cross-border systemic-risk monitoring"
- "Open methodology, hosted execution"
- "Audit-friendly risk reporting"

## Forbidden marketing positioning

- "Trading signals"
- "Hedge fund strategies"
- "Profitable / backtested / win rate ..."
- Any reference to live PnL, paper PnL, expert agents, gauntlet, or specific tickers traded.
