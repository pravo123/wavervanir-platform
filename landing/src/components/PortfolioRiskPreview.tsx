import {
  DEMO_RISK_SUMMARY,
  DEMO_TOP_POSITIONS,
  type DemoPosition,
  type PortfolioRiskSummary,
} from "../data/demoRisk";

export type Props = {
  summary?: PortfolioRiskSummary;
  positions?: DemoPosition[];
};

function usd(n: number): string {
  const sign = n < 0 ? "-$" : "$";
  return `${sign}${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export default function PortfolioRiskPreview({
  summary = DEMO_RISK_SUMMARY,
  positions = DEMO_TOP_POSITIONS,
}: Props) {
  return (
    <div className="risk-preview" data-testid="risk-preview">
      <div className="risk-preview__head">
        <div>
          <div className="risk-preview__label">Account alias</div>
          <div className="risk-preview__alias">{summary.account_alias}</div>
        </div>
        <div className="risk-preview__warn" role="note" data-testid="no-account-warning">
          No account numbers. No live brokerage connection. Snapshot is a sanitized example.
        </div>
      </div>

      <div className="risk-stats">
        <Stat label="Positions" value={String(summary.n_positions)} />
        <Stat label="Gross exposure" value={usd(summary.total_gross_exposure_usd)} />
        <Stat label="Long" value={usd(summary.total_long_exposure_usd)} />
        <Stat label="Short" value={usd(summary.total_short_exposure_usd)} />
        <Stat label="Unrealized PnL" value={usd(summary.total_unrealized_pnl_usd)} />
        <Stat label="Top-5 concentration" value={pct(summary.concentration_top5_pct_of_gross)} />
      </div>

      <div className="risk-breakdown">
        <h4 className="risk-breakdown__title">Exposure by asset class</h4>
        <table className="risk-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Gross</th>
              <th>Net</th>
              <th>#</th>
            </tr>
          </thead>
          <tbody>
            {summary.by_asset_class.map((b) => (
              <tr key={b.asset_class} data-testid={`bucket-${b.asset_class}`}>
                <td>{b.asset_class}</td>
                <td>{usd(b.gross_exposure_usd)}</td>
                <td>{usd(b.net_exposure_usd)}</td>
                <td>{b.n_positions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="risk-breakdown">
        <h4 className="risk-breakdown__title">Top positions</h4>
        <table className="risk-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Class</th>
              <th>Qty</th>
              <th>Market value</th>
              <th>uPnL</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.symbol} data-testid={`pos-${p.symbol.replace(/\s+/g, "-")}`}>
                <td>{p.symbol}</td>
                <td>{p.asset_class}</td>
                <td>{p.quantity}</td>
                <td>{usd(p.market_value)}</td>
                <td>{usd(p.unrealized_pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="risk-stat">
      <div className="risk-stat__label">{label}</div>
      <div className="risk-stat__value">{value}</div>
    </div>
  );
}
