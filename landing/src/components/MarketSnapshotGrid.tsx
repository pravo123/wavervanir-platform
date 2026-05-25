import { DEMO_MARKET_SNAPSHOTS, type MarketSnapshot } from "../data/demoRisk";

export type Props = { snapshots?: MarketSnapshot[] };

function fmtPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return p.toFixed(2);
}

function fmtPct(p: number): string {
  const sign = p >= 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

export default function MarketSnapshotGrid({ snapshots = DEMO_MARKET_SNAPSHOTS }: Props) {
  return (
    <div className="market-grid" data-testid="market-grid">
      {snapshots.map((s) => {
        const up = s.day_change_pct >= 0;
        return (
          <div
            key={s.symbol}
            className={`mkt-card mkt-card--${up ? "up" : "down"}`}
            data-testid={`mkt-${s.symbol}`}
          >
            <div className="mkt-card__head">
              <span className="mkt-card__sym">{s.symbol}</span>
              <span className="mkt-card__label">{s.label}</span>
            </div>
            <div className="mkt-card__price">${fmtPrice(s.price)}</div>
            <div className={`mkt-card__chg mkt-card__chg--${up ? "up" : "down"}`}>
              {fmtPct(s.day_change_pct)}
            </div>
            <div className="mkt-card__src">source: {s.source} fixture</div>
          </div>
        );
      })}
    </div>
  );
}
