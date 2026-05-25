import { useState } from "react";

import {
  DEMO_FLOW_SNAPSHOTS,
  DEMO_MARKET_SNAPSHOTS,
  DEMO_RISK_SUMMARY,
} from "../data/demoRisk";

/**
 * Frontend-only "Generate demo risk report" CTA.
 *
 * No backend dependency. Builds a small Markdown snapshot from the fixture
 * data so reviewers can see what a delivered report would look like.
 */
export default function DemoReportPreview() {
  const [shown, setShown] = useState(false);

  return (
    <div className="demo-report" data-testid="demo-report">
      <div className="demo-report__cta">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => setShown((v) => !v)}
          data-testid="demo-report-btn"
        >
          {shown ? "Hide demo risk report" : "Generate demo risk report"}
        </button>
        <p className="demo-report__hint">
          Renders a sample report from fixture data. No backend, no email, no PDF — preview only.
        </p>
      </div>

      {shown && (
        <pre className="demo-report__body" data-testid="demo-report-body">
{buildReport()}
        </pre>
      )}
    </div>
  );
}

function buildReport(): string {
  const lines: string[] = [];
  lines.push("# WaverVanir Risk Intelligence — Demo Report");
  lines.push("");
  lines.push("> Fixture-data preview. No live FMP / Bullflow / broker feeds.");
  lines.push("");

  lines.push("## 1. Market snapshot");
  lines.push("");
  lines.push("| Symbol | Price | Day change |");
  lines.push("|---|---:|---:|");
  for (const m of DEMO_MARKET_SNAPSHOTS) {
    const px = m.price >= 1000 ? m.price.toLocaleString() : m.price.toFixed(2);
    const chg = `${m.day_change_pct >= 0 ? "+" : ""}${(m.day_change_pct * 100).toFixed(2)}%`;
    lines.push(`| ${m.symbol} | $${px} | ${chg} |`);
  }
  lines.push("");

  lines.push("## 2. Flow signals");
  lines.push("");
  for (const f of DEMO_FLOW_SNAPSHOTS) {
    lines.push(`- **${f.symbol}** — bias: ${f.bias}. ${f.bias_note}`);
  }
  lines.push("");

  lines.push("## 3. Portfolio risk");
  lines.push("");
  lines.push(`- Account alias: \`${DEMO_RISK_SUMMARY.account_alias}\` (sanitized)`);
  lines.push(`- Positions: ${DEMO_RISK_SUMMARY.n_positions}`);
  lines.push(`- Gross exposure: $${DEMO_RISK_SUMMARY.total_gross_exposure_usd.toLocaleString()}`);
  lines.push(`- Net unrealized PnL: $${DEMO_RISK_SUMMARY.total_unrealized_pnl_usd.toLocaleString()}`);
  lines.push(
    `- Top-5 concentration: ${(DEMO_RISK_SUMMARY.concentration_top5_pct_of_gross * 100).toFixed(1)}%`,
  );
  lines.push("");

  lines.push("---");
  lines.push("Generated locally in the browser. No data leaves this page.");

  return lines.join("\n");
}
