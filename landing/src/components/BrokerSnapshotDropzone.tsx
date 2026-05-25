import { useMemo, useState } from "react";

import {
  SAMPLE_BROKER_SNAPSHOT,
  isBrokerSnapshotApiConfigured,
  postBrokerSnapshotRiskSummary,
  type PortfolioRiskSummary,
  type SnapshotApiError,
} from "../api/brokerSnapshot";

const DARK_INPUT: React.CSSProperties = {
  background: "#000",
  color: "var(--fg)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  padding: "12px 14px",
  fontSize: 13,
  fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace",
  width: "100%",
  minHeight: 180,
};

const ERROR_BOX: React.CSSProperties = {
  marginTop: 12,
  border: "1px solid rgba(226, 106, 106, 0.4)",
  borderRadius: 10,
  padding: "10px 14px",
  background: "rgba(226, 106, 106, 0.08)",
  color: "#e26a6a",
  fontSize: 13,
};

const HINT: React.CSSProperties = {
  marginTop: 8,
  fontSize: 12,
  color: "var(--fg-muted)",
};

const STAT_GRID: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: 12,
  marginTop: 16,
};

const STAT_CARD: React.CSSProperties = {
  background: "#000",
  border: "1px solid var(--border)",
  borderRadius: 10,
  padding: "10px 14px",
};

const STAT_LABEL: React.CSSProperties = {
  fontSize: 11,
  color: "var(--fg-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.12em",
};

const STAT_VALUE: React.CSSProperties = {
  fontWeight: 700,
  fontSize: 16,
  marginTop: 4,
};

const TABLE: React.CSSProperties = {
  width: "100%",
  minWidth: 360,
  borderCollapse: "collapse",
  fontSize: 13,
  marginTop: 12,
};

const TABLE_CELL: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 10px",
  borderBottom: "1px solid var(--border)",
  whiteSpace: "nowrap",
};

const TABLE_SCROLL: React.CSSProperties = {
  overflowX: "auto",
  WebkitOverflowScrolling: "touch",
};

function fmtUsd(n: number): string {
  const sign = n < 0 ? "-$" : "$";
  return `${sign}${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export default function BrokerSnapshotDropzone() {
  const configured = useMemo(() => isBrokerSnapshotApiConfigured(), []);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<PortfolioRiskSummary | null>(null);
  const [error, setError] = useState<SnapshotApiError | { kind: "parse"; reason: string } | null>(
    null,
  );

  function loadSample() {
    setText(JSON.stringify(SAMPLE_BROKER_SNAPSHOT, null, 2));
    setError(null);
    setSummary(null);
  }

  async function analyze() {
    setError(null);
    setSummary(null);

    let payload: unknown;
    try {
      payload = JSON.parse(text);
    } catch (e) {
      setError({ kind: "parse", reason: `Invalid JSON: ${(e as Error).message}` });
      return;
    }

    setBusy(true);
    try {
      const result = await postBrokerSnapshotRiskSummary(payload);
      setSummary(result);
    } catch (e) {
      // postBrokerSnapshotRiskSummary throws SnapshotApiError objects
      setError(e as SnapshotApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="broker-dropzone">
      <p style={HINT}>
        Paste sanitized broker-snapshot JSON below or load the bundled sample.
        The payload is POSTed to the platform's <code>/v1/data/broker-snapshot/risk-summary</code>
        endpoint. No broker SDKs. No credentials. No account numbers leave your browser raw —
        the platform's validator rejects payloads that contain Stripe/JWT/account-number shapes.
      </p>

      <textarea
        data-testid="broker-textarea"
        style={DARK_INPUT}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder='{"schema_version":"1.0", "snapshot_ts":"…", "account_alias":"paper-main", "base_currency":"USD", "positions":[…]}'
        spellCheck={false}
      />

      <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          data-testid="broker-sample-button"
          onClick={loadSample}
        >
          Load sample
        </button>
        <button
          type="button"
          className="btn btn--primary"
          data-testid="broker-analyze-button"
          onClick={analyze}
          disabled={!configured || busy || text.trim().length === 0}
        >
          {busy ? "Analyzing…" : "Analyze"}
        </button>
        {!configured && (
          <span style={HINT} data-testid="broker-unconfigured-note">
            Set <code>VITE_WAVERVANIR_API_URL</code> to enable live snapshot analysis.
          </span>
        )}
      </div>

      {error && (
        <div style={ERROR_BOX} data-testid="broker-error">
          {error.kind === "parse" && <strong>JSON error.</strong>}
          {error.kind === "validation" && <strong>Snapshot rejected.</strong>}
          {error.kind === "network" && <strong>Snapshot API unavailable.</strong>}
          {error.kind === "unknown" && <strong>Snapshot error.</strong>}
          <div style={{ marginTop: 4 }}>{error.reason}</div>
          {"scrub_violations" in error && error.scrub_violations.length > 0 && (
            <ul data-testid="broker-scrub-violations" style={{ margin: "8px 0 0", paddingLeft: 18 }}>
              {error.scrub_violations.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {summary && (
        <div data-testid="broker-summary">
          <div style={STAT_GRID}>
            <SummaryStat label="Account alias" value={summary.account_alias} />
            <SummaryStat label="Currency" value={summary.base_currency} />
            <SummaryStat label="Positions" value={String(summary.n_positions)} />
            <SummaryStat label="Gross exposure" value={fmtUsd(summary.total_gross_exposure_usd)} />
            <SummaryStat label="Long" value={fmtUsd(summary.total_long_exposure_usd)} />
            <SummaryStat label="Short" value={fmtUsd(summary.total_short_exposure_usd)} />
            <SummaryStat label="Unrealized PnL" value={fmtUsd(summary.total_unrealized_pnl_usd)} />
            <SummaryStat
              label="Largest position"
              value={fmtPct(summary.largest_position_pct_of_gross)}
            />
            <SummaryStat
              label="Top-5 concentration"
              value={fmtPct(summary.concentration_top5_pct_of_gross)}
            />
          </div>

          {summary.by_asset_class.length > 0 && (
            <div style={TABLE_SCROLL}>
              <table style={TABLE} data-testid="broker-summary-table">
                <thead>
                  <tr>
                    <th style={TABLE_CELL}>Asset class</th>
                    <th style={TABLE_CELL}>Gross</th>
                    <th style={TABLE_CELL}>Net</th>
                    <th style={TABLE_CELL}>#</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_asset_class.map((b) => (
                    <tr key={b.asset_class} data-testid={`broker-bucket-${b.asset_class}`}>
                      <td style={TABLE_CELL}>{b.asset_class}</td>
                      <td style={TABLE_CELL}>{fmtUsd(b.gross_exposure_usd)}</td>
                      <td style={TABLE_CELL}>{fmtUsd(b.net_exposure_usd)}</td>
                      <td style={TABLE_CELL}>{b.n_positions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={STAT_CARD}>
      <div style={STAT_LABEL}>{label}</div>
      <div style={STAT_VALUE}>{value}</div>
    </div>
  );
}
