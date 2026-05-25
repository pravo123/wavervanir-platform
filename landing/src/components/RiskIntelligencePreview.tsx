import { DEMO_FLOW_SNAPSHOTS, type FlowSnapshot } from "../data/demoRisk";

export type Props = { flows?: FlowSnapshot[] };

function ratio(call: number, put: number): string {
  if (put === 0) return "∞";
  return (call / put).toFixed(2);
}

export default function RiskIntelligencePreview({ flows = DEMO_FLOW_SNAPSHOTS }: Props) {
  return (
    <div className="flow-grid" data-testid="flow-grid">
      {flows.map((f) => (
        <div
          key={f.symbol}
          className={`flow-card flow-card--${f.bias}`}
          data-testid={`flow-${f.symbol}`}
        >
          <div className="flow-card__head">
            <span className="flow-card__sym">{f.symbol}</span>
            <span className={`flow-card__bias flow-card__bias--${f.bias}`}>{f.bias}</span>
          </div>
          <div className="flow-card__row">
            <span>Call premium</span>
            <span>${f.call_premium_usd.toLocaleString()}</span>
          </div>
          <div className="flow-card__row">
            <span>Put premium</span>
            <span>${f.put_premium_usd.toLocaleString()}</span>
          </div>
          <div className="flow-card__row">
            <span>Call / put</span>
            <span>{ratio(f.call_premium_usd, f.put_premium_usd)}</span>
          </div>
          {f.smart_money_ratio !== null && (
            <div className="flow-card__row">
              <span>Smart-money ratio</span>
              <span>{f.smart_money_ratio.toFixed(2)}</span>
            </div>
          )}
          <p className="flow-card__note">{f.bias_note}</p>
          <div className="flow-card__src">source: {f.source} fixture</div>
        </div>
      ))}
    </div>
  );
}
