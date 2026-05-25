/**
 * Read-only client for /v1/data/broker-snapshot/risk-summary.
 *
 * Contract:
 *   - `isBrokerSnapshotApiConfigured()` returns true only when
 *     VITE_WAVERVANIR_API_URL is set; UI uses this to gate the analyze CTA.
 *   - `postBrokerSnapshotRiskSummary(payload)` POSTs the (already-sanitized)
 *     JSON payload to the platform and returns a normalized result.
 *   - On non-2xx responses, parses the FastAPI detail envelope and surfaces
 *     `detail.reason` + `detail.scrub_violations` so the UI can render the
 *     sanitization warning inline.
 *
 * Boundary:
 *   - No Authorization header is sent. The endpoint is a sanitization +
 *     aggregation surface; sanitization rules are enforced server-side.
 *   - `credentials: omit`. No cookies. No third-party tokens.
 *   - The "sample" sanitized payload below is a literal mirror of
 *     api/tests/fixtures/sample_broker_snapshot.json — kept inline so the
 *     widget has zero external data dependency.
 */

// Mirror landing/src/api/providers.ts's safe ImportMeta cast.
type ImportMetaWithEnv = ImportMeta & {
  env?: { VITE_WAVERVANIR_API_URL?: string };
};

export function getApiUrl(): string {
  const meta = import.meta as ImportMetaWithEnv;
  const raw = (meta.env?.VITE_WAVERVANIR_API_URL ?? "") as string;
  return raw.trim().replace(/\/+$/, "");
}

export function isBrokerSnapshotApiConfigured(): boolean {
  return getApiUrl().length > 0;
}

export type AssetClass =
  | "equity"
  | "option"
  | "future"
  | "etf"
  | "crypto"
  | "fx"
  | "other";

export type ByAssetClassExposure = {
  asset_class: AssetClass;
  gross_exposure_usd: number;
  net_exposure_usd: number;
  n_positions: number;
};

/**
 * Client-side normalized summary. Field names are kept aligned with the
 * server response (see api/src/wavervanir_api/schemas/broker.py) so the
 * mapping is 1:1 and easy to audit.
 */
export type PortfolioRiskSummary = {
  account_alias: string;
  base_currency: string;
  n_positions: number;
  total_gross_exposure_usd: number;
  total_long_exposure_usd: number;
  total_short_exposure_usd: number;
  total_unrealized_pnl_usd: number;
  largest_position_pct_of_gross: number;
  concentration_top5_pct_of_gross: number;
  by_asset_class: ByAssetClassExposure[];
};

export type SnapshotApiError = {
  kind: "validation" | "network" | "unknown";
  status?: number;
  reason: string;
  scrub_violations: string[];
};

/**
 * Sanitized sample broker snapshot. Mirrors
 * api/tests/fixtures/sample_broker_snapshot.json. Contains zero account
 * numbers, zero credentials, zero PII.
 */
export const SAMPLE_BROKER_SNAPSHOT = {
  schema_version: "1.0",
  snapshot_ts: "2026-05-24T18:00:00Z",
  account_alias: "paper-main",
  base_currency: "USD",
  positions: [
    {
      symbol: "AAPL",
      asset_class: "equity",
      quantity: 100,
      mark_price: 195.5,
      market_value: 19550.0,
      unrealized_pnl: 312.5,
    },
    {
      symbol: "MSFT",
      asset_class: "equity",
      quantity: 40,
      mark_price: 412.1,
      market_value: 16484.0,
      unrealized_pnl: -84.0,
    },
    {
      symbol: "SPY",
      asset_class: "etf",
      quantity: -20,
      mark_price: 510.0,
      market_value: -10200.0,
      unrealized_pnl: 45.0,
    },
    {
      symbol: "NVDA  240621C00800000",
      asset_class: "option",
      quantity: 2,
      mark_price: 13.5,
      market_value: 2700.0,
      unrealized_pnl: 120.0,
    },
    {
      symbol: "BTCUSD",
      asset_class: "crypto",
      quantity: 0.05,
      mark_price: 68000.0,
      market_value: 3400.0,
      unrealized_pnl: -50.0,
    },
  ],
} as const;

export async function postBrokerSnapshotRiskSummary(
  payload: unknown,
  baseUrl: string = getApiUrl(),
  fetchImpl: typeof fetch = fetch,
): Promise<PortfolioRiskSummary> {
  if (!baseUrl) {
    throw {
      kind: "network",
      reason: "API URL is not configured (set VITE_WAVERVANIR_API_URL).",
      scrub_violations: [],
    } satisfies SnapshotApiError;
  }

  const url = `${baseUrl}/v1/data/broker-snapshot/risk-summary`;

  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      credentials: "omit",
      body: JSON.stringify(payload),
    });
  } catch (e) {
    throw {
      kind: "network",
      reason: `Network failure: ${String((e as Error).message ?? e)}`,
      scrub_violations: [],
    } satisfies SnapshotApiError;
  }

  if (!response.ok) {
    let detailReason = `HTTP ${response.status}`;
    let detailViolations: string[] = [];
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object") {
        const detail = (body as { detail?: unknown }).detail;
        if (detail && typeof detail === "object") {
          const d = detail as { reason?: unknown; scrub_violations?: unknown };
          if (typeof d.reason === "string") detailReason = d.reason;
          if (Array.isArray(d.scrub_violations)) {
            detailViolations = d.scrub_violations.filter(
              (v): v is string => typeof v === "string",
            );
          }
        }
      }
    } catch {
      // body wasn't JSON; keep generic reason
    }
    throw {
      kind: response.status === 422 ? "validation" : "unknown",
      status: response.status,
      reason: detailReason,
      scrub_violations: detailViolations,
    } satisfies SnapshotApiError;
  }

  const body: unknown = await response.json();
  return normalizeSummary(body);
}

function normalizeSummary(payload: unknown): PortfolioRiskSummary {
  if (!payload || typeof payload !== "object") {
    throw {
      kind: "unknown",
      reason: "summary payload is not an object",
      scrub_violations: [],
    } satisfies SnapshotApiError;
  }
  const p = payload as Record<string, unknown>;

  const mustString = (k: string): string => {
    const v = p[k];
    if (typeof v !== "string") {
      throw {
        kind: "unknown",
        reason: `summary.${k} is not a string`,
        scrub_violations: [],
      } satisfies SnapshotApiError;
    }
    return v;
  };
  const mustNumber = (k: string): number => {
    const v = p[k];
    if (typeof v !== "number" || !Number.isFinite(v)) {
      throw {
        kind: "unknown",
        reason: `summary.${k} is not a finite number`,
        scrub_violations: [],
      } satisfies SnapshotApiError;
    }
    return v;
  };

  const rawByClass = p.by_asset_class;
  if (!Array.isArray(rawByClass)) {
    throw {
      kind: "unknown",
      reason: "summary.by_asset_class is not an array",
      scrub_violations: [],
    } satisfies SnapshotApiError;
  }

  const by_asset_class: ByAssetClassExposure[] = rawByClass.map((entry, i) => {
    if (!entry || typeof entry !== "object") {
      throw {
        kind: "unknown",
        reason: `summary.by_asset_class[${i}] is not an object`,
        scrub_violations: [],
      } satisfies SnapshotApiError;
    }
    const e = entry as Record<string, unknown>;
    return {
      asset_class: e.asset_class as AssetClass,
      gross_exposure_usd: Number(e.gross_exposure_usd ?? 0),
      net_exposure_usd: Number(e.net_exposure_usd ?? 0),
      n_positions: Number(e.n_positions ?? 0),
    };
  });

  return {
    account_alias: mustString("account_alias"),
    base_currency: mustString("base_currency"),
    n_positions: mustNumber("n_positions"),
    total_gross_exposure_usd: mustNumber("total_gross_exposure_usd"),
    total_long_exposure_usd: mustNumber("total_long_exposure_usd"),
    total_short_exposure_usd: mustNumber("total_short_exposure_usd"),
    total_unrealized_pnl_usd: mustNumber("total_unrealized_pnl_usd"),
    largest_position_pct_of_gross: mustNumber("largest_position_pct_of_gross"),
    concentration_top5_pct_of_gross: mustNumber("concentration_top5_pct_of_gross"),
    by_asset_class,
  };
}
