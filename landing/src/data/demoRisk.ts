/**
 * Demo Risk Intelligence dashboard fixture data.
 *
 * Frontend-only — mirrors the response shape of:
 *   GET  /v1/data/providers
 *   GET  /v1/data/snapshot/{SYM}?provider=demo&kind=market
 *   GET  /v1/data/snapshot/{SYM}?provider=demo&kind=flow
 *   POST /v1/data/broker-snapshot/risk-summary
 *
 * No live data. No account numbers. No broker connection. No secrets.
 * If you switch the dashboard to live `/v1/data/*` later, the same TypeScript
 * shapes apply.
 */

export const DEMO_DATA_DISCLAIMER =
  "This demo uses fixture/sample data. Live FMP, Bullflow, and broker-snapshot " +
  "integrations are provider-ready but not active on this public demo.";

// ---------------------------------------------------------------------------
// Provider status
// ---------------------------------------------------------------------------

export type ProviderKind = "fetch" | "upload";

export type ProviderStatus = {
  name: string;
  kind: ProviderKind;
  enabled: boolean;
  reason: string;
  requires: string[];
};

export const DEMO_PROVIDERS: ProviderStatus[] = [
  {
    name: "demo",
    kind: "fetch",
    enabled: true,
    reason: "Always available — no API key, no network.",
    requires: [],
  },
  {
    name: "fmp",
    kind: "fetch",
    enabled: false,
    reason: "Planned — disabled until FMP_API_KEY is configured.",
    requires: ["env: FMP_API_KEY"],
  },
  {
    name: "bullflow",
    kind: "fetch",
    enabled: false,
    reason: "Planned — disabled until BULLFLOW_API_KEY or BULLFLOW_DATA_FILE is configured.",
    requires: ["env: BULLFLOW_API_KEY OR BULLFLOW_DATA_FILE"],
  },
  {
    name: "broker_snapshot",
    kind: "upload",
    enabled: true,
    reason: "File-import path. Validates sanitized broker JSON/CSV; no SDK, no network.",
    requires: ["uploaded JSON or CSV payload"],
  },
];

// ---------------------------------------------------------------------------
// Market snapshots — deterministic, mirror the demo provider's outputs.
// ---------------------------------------------------------------------------

export type MarketSnapshot = {
  symbol: string;
  snapshot_ts: string;
  price: number;
  volume: number;
  day_change_pct: number;
  source: "demo";
  label: string;
};

export const DEMO_MARKET_SNAPSHOTS: MarketSnapshot[] = [
  {
    symbol: "SPY",
    label: "S&P 500 ETF",
    snapshot_ts: "2026-01-01T14:30:00Z",
    price: 542.18,
    volume: 78_900_000,
    day_change_pct: 0.0034,
    source: "demo",
  },
  {
    symbol: "QQQ",
    label: "Nasdaq-100 ETF",
    snapshot_ts: "2026-01-01T14:30:00Z",
    price: 478.96,
    volume: 46_200_000,
    day_change_pct: 0.0082,
    source: "demo",
  },
  {
    symbol: "IWM",
    label: "Russell 2000 ETF",
    snapshot_ts: "2026-01-01T14:30:00Z",
    price: 218.44,
    volume: 32_000_000,
    day_change_pct: -0.0041,
    source: "demo",
  },
  {
    symbol: "GLD",
    label: "Gold ETF",
    snapshot_ts: "2026-01-01T14:30:00Z",
    price: 244.05,
    volume: 8_300_000,
    day_change_pct: 0.0061,
    source: "demo",
  },
  {
    symbol: "TLT",
    label: "20+ Yr Treasury ETF",
    snapshot_ts: "2026-01-01T14:30:00Z",
    price: 96.71,
    volume: 14_900_000,
    day_change_pct: -0.0019,
    source: "demo",
  },
  {
    symbol: "BTCUSD",
    label: "Bitcoin / USD",
    snapshot_ts: "2026-01-01T14:30:00Z",
    price: 68_412.5,
    volume: 0,
    day_change_pct: 0.0157,
    source: "demo",
  },
];

// ---------------------------------------------------------------------------
// Flow / risk intelligence — single demo signal across a few symbols.
// ---------------------------------------------------------------------------

export type FlowSnapshot = {
  symbol: string;
  snapshot_ts: string;
  call_premium_usd: number;
  put_premium_usd: number;
  smart_money_ratio: number | null;
  n_trades: number;
  source: "demo";
  bias: "bullish" | "bearish" | "balanced";
  bias_note: string;
};

export const DEMO_FLOW_SNAPSHOTS: FlowSnapshot[] = [
  {
    symbol: "SPY",
    snapshot_ts: "2026-01-01T14:30:00Z",
    call_premium_usd: 95_000_000,
    put_premium_usd: 110_000_000,
    smart_money_ratio: 0.48,
    n_trades: 5_200,
    source: "demo",
    bias: "balanced",
    bias_note: "Calls / puts roughly balanced; mild put lean.",
  },
  {
    symbol: "NVDA",
    snapshot_ts: "2026-01-01T14:30:00Z",
    call_premium_usd: 38_000_000,
    put_premium_usd: 22_000_000,
    smart_money_ratio: 0.71,
    n_trades: 1_108,
    source: "demo",
    bias: "bullish",
    bias_note: "Heavy call premium and high smart-money ratio.",
  },
  {
    symbol: "IWM",
    snapshot_ts: "2026-01-01T14:30:00Z",
    call_premium_usd: 6_100_000,
    put_premium_usd: 14_400_000,
    smart_money_ratio: 0.31,
    n_trades: 612,
    source: "demo",
    bias: "bearish",
    bias_note: "Put premium ≈ 2.4× calls; low smart-money confidence.",
  },
];

// ---------------------------------------------------------------------------
// Portfolio risk summary — output of POST /broker-snapshot/risk-summary.
// Mirrors api/tests/fixtures/sample_broker_snapshot.json aggregation.
// ---------------------------------------------------------------------------

export type ByAssetClassExposure = {
  asset_class: "equity" | "option" | "future" | "etf" | "crypto" | "fx" | "other";
  gross_exposure_usd: number;
  net_exposure_usd: number;
  n_positions: number;
};

export type PortfolioRiskSummary = {
  schema_version: "1.0";
  snapshot_ts: string;
  account_alias: string;
  base_currency: "USD";
  n_positions: number;
  total_gross_exposure_usd: number;
  total_long_exposure_usd: number;
  total_short_exposure_usd: number;
  total_unrealized_pnl_usd: number;
  largest_position_pct_of_gross: number;
  concentration_top5_pct_of_gross: number;
  by_asset_class: ByAssetClassExposure[];
};

export const DEMO_RISK_SUMMARY: PortfolioRiskSummary = {
  schema_version: "1.0",
  snapshot_ts: "2026-05-24T18:00:00Z",
  account_alias: "paper-main",
  base_currency: "USD",
  n_positions: 5,
  total_gross_exposure_usd: 52_334.0,
  total_long_exposure_usd: 42_134.0,
  total_short_exposure_usd: 10_200.0,
  total_unrealized_pnl_usd: 343.5,
  largest_position_pct_of_gross: 0.3736,
  concentration_top5_pct_of_gross: 1.0,
  by_asset_class: [
    { asset_class: "crypto", gross_exposure_usd: 3_400.0, net_exposure_usd: 3_400.0, n_positions: 1 },
    { asset_class: "equity", gross_exposure_usd: 36_034.0, net_exposure_usd: 36_034.0, n_positions: 2 },
    { asset_class: "etf", gross_exposure_usd: 10_200.0, net_exposure_usd: -10_200.0, n_positions: 1 },
    { asset_class: "option", gross_exposure_usd: 2_700.0, net_exposure_usd: 2_700.0, n_positions: 1 },
  ],
};

export type DemoPosition = {
  symbol: string;
  asset_class: ByAssetClassExposure["asset_class"];
  quantity: number;
  market_value: number;
  unrealized_pnl: number;
};

// Mirrors api/tests/fixtures/sample_broker_snapshot.json. No account numbers.
export const DEMO_TOP_POSITIONS: DemoPosition[] = [
  { symbol: "AAPL", asset_class: "equity", quantity: 100, market_value: 19_550.0, unrealized_pnl: 312.5 },
  { symbol: "MSFT", asset_class: "equity", quantity: 40, market_value: 16_484.0, unrealized_pnl: -84.0 },
  { symbol: "SPY", asset_class: "etf", quantity: -20, market_value: -10_200.0, unrealized_pnl: 45.0 },
  { symbol: "BTCUSD", asset_class: "crypto", quantity: 0.05, market_value: 3_400.0, unrealized_pnl: -50.0 },
  { symbol: "NVDA 240621C00800000", asset_class: "option", quantity: 2, market_value: 2_700.0, unrealized_pnl: 120.0 },
];
