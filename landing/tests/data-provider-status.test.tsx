/**
 * DataProviderStatus contract:
 *
 *   1. env blank          → renders DEMO_PROVIDERS, fetch NOT called.
 *   2. env set + ok       → renders the live provider list.
 *   3. env set + reject   → renders DEMO_PROVIDERS + a "Fixture fallback active." note.
 *   4. prop override      → renders the passed providers, fetch NOT called.
 *   5. env set + malformed→ renders DEMO_PROVIDERS + fallback note, no crash.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DataProviderStatus from "../src/components/DataProviderStatus";
import { DEMO_PROVIDERS, type ProviderStatus } from "../src/data/demoRisk";

const LIVE_PROVIDERS: ProviderStatus[] = [
  { name: "demo", kind: "fetch", enabled: true, reason: "live demo", requires: [] },
  { name: "fmp", kind: "fetch", enabled: true, reason: "FMP_API_KEY present", requires: ["env: FMP_API_KEY"] },
  {
    name: "bullflow",
    kind: "fetch",
    enabled: false,
    reason: "no key/file",
    requires: ["env: BULLFLOW_API_KEY OR BULLFLOW_DATA_FILE"],
  },
  {
    name: "broker_snapshot",
    kind: "upload",
    enabled: true,
    reason: "always",
    requires: ["uploaded JSON or CSV payload"],
  },
];

function makeFetchResolving(body: unknown, status = 200) {
  return vi.fn(async (_url: string) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })) as unknown as typeof fetch;
}

function makeFetchRejecting() {
  return vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  vi.stubEnv("VITE_WAVERVANIR_API_URL", "");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("DataProviderStatus — live + fixture-fallback", () => {
  it("env blank: renders DEMO_PROVIDERS and does not call fetch", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(<DataProviderStatus />);
    const grid = screen.getByTestId("provider-grid");
    for (const p of DEMO_PROVIDERS) {
      expect(within(grid).getByTestId(`provider-${p.name}`)).toBeInTheDocument();
    }
    expect(screen.queryByTestId("provider-fallback-note")).toBeNull();
    // give any spurious effect a turn to run; assert no fetch
    await Promise.resolve();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("env set + fetch resolves: renders the live provider list", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const fetchSpy = makeFetchResolving({ providers: LIVE_PROVIDERS });
    vi.stubGlobal("fetch", fetchSpy);

    render(<DataProviderStatus />);

    // immediate render is still DEMO_PROVIDERS (no layout shift on entry)
    expect(screen.getByTestId(`provider-demo`)).toBeInTheDocument();

    // after fetch resolves, FMP tile flips to enabled because LIVE_PROVIDERS says so
    await waitFor(() => {
      const fmp = screen.getByTestId("provider-fmp");
      expect(fmp.className).toMatch(/provider--on/);
    });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = (fetchSpy as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(String(calledUrl)).toBe("http://127.0.0.1:8000/v1/data/providers");
    expect(screen.queryByTestId("provider-fallback-note")).toBeNull();
  });

  it("env set + fetch rejects: keeps DEMO_PROVIDERS and shows fallback note", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const fetchSpy = makeFetchRejecting();
    vi.stubGlobal("fetch", fetchSpy);

    render(<DataProviderStatus />);
    await waitFor(() => {
      expect(screen.getByTestId("provider-fallback-note")).toBeInTheDocument();
    });
    expect(screen.getByTestId("provider-fallback-note").textContent).toMatch(
      /fixture fallback active/i,
    );
    // FMP still rendered as disabled (DEMO_PROVIDERS state)
    expect(screen.getByTestId("provider-fmp").className).toMatch(/provider--off/);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("prop override: renders passed providers and does not call fetch", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const custom: ProviderStatus[] = [
      { name: "custom-only", kind: "fetch", enabled: true, reason: "test", requires: [] },
    ];
    render(<DataProviderStatus providers={custom} />);
    expect(screen.getByTestId("provider-custom-only")).toBeInTheDocument();
    expect(screen.queryByTestId("provider-demo")).toBeNull();
    await Promise.resolve();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("env set + malformed payload: falls back without crashing", async () => {
    vi.stubEnv("VITE_WAVERVANIR_API_URL", "http://127.0.0.1:8000");
    // missing 'providers' key — normalizer will throw, component will catch
    const fetchSpy = makeFetchResolving({ wrong_key: [] });
    vi.stubGlobal("fetch", fetchSpy);

    render(<DataProviderStatus />);
    await waitFor(() => {
      expect(screen.getByTestId("provider-fallback-note")).toBeInTheDocument();
    });
    // grid still rendered with the fixture
    for (const p of DEMO_PROVIDERS) {
      expect(screen.getByTestId(`provider-${p.name}`)).toBeInTheDocument();
    }
  });
});
