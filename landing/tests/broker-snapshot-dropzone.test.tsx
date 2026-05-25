/**
 * BrokerSnapshotDropzone contract:
 *
 *  1. env blank          → Analyze disabled + explanatory unconfigured note.
 *  2. load-sample button → fills the textarea with the bundled sample JSON.
 *  3. invalid JSON       → inline JSON error, fetch NOT called.
 *  4. env set + 2xx      → POSTs to /v1/data/broker-snapshot/risk-summary
 *                          (Content-Type application/json, NO Authorization
 *                          header, credentials omitted) and renders the
 *                          summary inline.
 *  5. env set + 422      → renders "Snapshot rejected." + the scrub_violations.
 *  6. env set + network  → renders "Snapshot API unavailable." fallback.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BrokerSnapshotDropzone from "../src/components/BrokerSnapshotDropzone";

function makeFetchOk(body: unknown) {
  return vi.fn(async () => {
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

function makeFetch422(detailReason: string, scrubViolations: string[]) {
  return vi.fn(async () => {
    return new Response(
      JSON.stringify({
        detail: {
          error: "snapshot_validation_failed",
          reason: detailReason,
          scrub_violations: scrubViolations,
        },
      }),
      { status: 422, headers: { "content-type": "application/json" } },
    );
  }) as unknown as typeof fetch;
}

function makeFetchNetworkError() {
  return vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  }) as unknown as typeof fetch;
}

const HAPPY_SUMMARY = {
  schema_version: "1.0",
  snapshot_ts: "2026-05-24T18:00:00Z",
  account_alias: "paper-main",
  base_currency: "USD",
  n_positions: 5,
  total_gross_exposure_usd: 52_334,
  total_long_exposure_usd: 42_134,
  total_short_exposure_usd: 10_200,
  total_unrealized_pnl_usd: 343.5,
  largest_position_pct_of_gross: 0.3736,
  concentration_top5_pct_of_gross: 1.0,
  by_asset_class: [
    { asset_class: "equity", gross_exposure_usd: 36_034, net_exposure_usd: 36_034, n_positions: 2 },
    { asset_class: "etf", gross_exposure_usd: 10_200, net_exposure_usd: -10_200, n_positions: 1 },
  ],
};

beforeEach(() => {
  vi.stubEnv("VITE_WAVERVANIR_API_URL", "");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BrokerSnapshotDropzone", () => {
  it("env blank: analyze disabled + unconfigured note visible", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(<BrokerSnapshotDropzone />);
    expect(screen.getByTestId("broker-dropzone")).toBeInTheDocument();
    const analyze = screen.getByTestId("broker-analyze-button") as HTMLButtonElement;
    expect(analyze.disabled).toBe(true);
    expect(screen.getByTestId("broker-unconfigured-note").textContent).toMatch(
      /VITE_WAVERVANIR_API_URL/,
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("load-sample button fills the textarea with sample JSON", () => {
    render(<BrokerSnapshotDropzone />);
    const textarea = screen.getByTestId("broker-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe("");
    fireEvent.click(screen.getByTestId("broker-sample-button"));
    expect(textarea.value).toContain('"schema_version": "1.0"');
    expect(textarea.value).toContain('"account_alias": "paper-main"');
    expect(textarea.value).toContain('"AAPL"');
  });

  it("invalid JSON: inline error, fetch NOT called", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(<BrokerSnapshotDropzone />);
    const textarea = screen.getByTestId("broker-textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "{ this is not json" } });
    fireEvent.click(screen.getByTestId("broker-analyze-button"));

    const err = await screen.findByTestId("broker-error");
    expect(err.textContent || "").toMatch(/json error/i);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.queryByTestId("broker-summary")).toBeNull();
  });

  it("env set + 2xx: POSTs to the correct URL with no Authorization header + renders summary", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const fetchSpy = makeFetchOk(HAPPY_SUMMARY);
    vi.stubGlobal("fetch", fetchSpy);

    render(<BrokerSnapshotDropzone />);
    fireEvent.click(screen.getByTestId("broker-sample-button"));
    fireEvent.click(screen.getByTestId("broker-analyze-button"));

    await waitFor(() => {
      expect(screen.getByTestId("broker-summary")).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [calledUrl, init] = (fetchSpy as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(calledUrl)).toBe(
      "http://127.0.0.1:8000/v1/data/broker-snapshot/risk-summary",
    );
    const opts = init as RequestInit;
    expect(opts.method).toBe("POST");
    expect(opts.credentials).toBe("omit");
    const headers = (opts.headers ?? {}) as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Accept"]).toBe("application/json");
    // CRITICAL: no Authorization header in this slice.
    expect(Object.keys(headers).map((h) => h.toLowerCase())).not.toContain("authorization");
    expect(headers["Authorization"]).toBeUndefined();

    // body is the parsed sample payload re-serialized
    expect(typeof opts.body).toBe("string");
    const sent = JSON.parse(opts.body as string);
    expect(sent.account_alias).toBe("paper-main");
    expect(Array.isArray(sent.positions)).toBe(true);

    // summary fields rendered
    expect(screen.getByTestId("broker-bucket-equity")).toBeInTheDocument();
    expect(screen.getByTestId("broker-bucket-etf")).toBeInTheDocument();
  });

  it("env set + 422: renders scrub-violation warning", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const violations = ["forbidden field name at $.account_number"];
    const fetchSpy = makeFetch422(
      "payload tripped sanitization rules: forbidden field name at $.account_number",
      violations,
    );
    vi.stubGlobal("fetch", fetchSpy);

    render(<BrokerSnapshotDropzone />);
    fireEvent.click(screen.getByTestId("broker-sample-button"));
    fireEvent.click(screen.getByTestId("broker-analyze-button"));

    const err = await screen.findByTestId("broker-error");
    expect(err.textContent || "").toMatch(/snapshot rejected/i);
    const list = screen.getByTestId("broker-scrub-violations");
    expect(list.textContent || "").toMatch(/forbidden field name at \$\.account_number/);
    expect(screen.queryByTestId("broker-summary")).toBeNull();
  });

  it("env set + network failure: renders unavailable fallback", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const fetchSpy = makeFetchNetworkError();
    vi.stubGlobal("fetch", fetchSpy);

    render(<BrokerSnapshotDropzone />);
    fireEvent.click(screen.getByTestId("broker-sample-button"));
    fireEvent.click(screen.getByTestId("broker-analyze-button"));

    const err = await screen.findByTestId("broker-error");
    expect(err.textContent || "").toMatch(/snapshot api unavailable/i);
    expect(screen.queryByTestId("broker-summary")).toBeNull();
  });
});
