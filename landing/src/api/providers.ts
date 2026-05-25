/**
 * Read-only fetcher for the live provider-status endpoint.
 *
 * Contract:
 *   - Returns `null` when `VITE_WAVERVANIR_API_URL` is blank/unset (or the
 *     caller passes a blank base) — callers fall back to fixture data.
 *   - Throws on network failure, non-2xx, or malformed payload — callers
 *     catch and fall back to fixture data.
 *
 * Boundary:
 *   - No `Authorization` header is sent. The provider-status endpoint is a
 *     low-sensitivity discovery surface; a future slice may add a token
 *     flow behind a public reverse proxy.
 *   - `VITE_*` env vars are PUBLIC by definition (they bake into the
 *     browser bundle). Never put secrets here.
 */

import type { ProviderStatus } from "../data/demoRisk";

export type { ProviderStatus };

// Local type cast for import.meta.env — the landing tsconfig doesn't include
// "vite/client" in its `types` allowlist, and adding it is outside this
// slice's allowlist. This is the minimal cast needed for tsc + vitest agreement.
type ImportMetaWithEnv = ImportMeta & {
  env?: { VITE_WAVERVANIR_API_URL?: string };
};

export function getApiUrl(): string {
  // import.meta.env is replaced at build time by Vite. In tests, vitest +
  // vi.stubEnv let us override per-case.
  const meta = import.meta as ImportMetaWithEnv;
  const raw = (meta.env?.VITE_WAVERVANIR_API_URL ?? "") as string;
  return raw.trim().replace(/\/+$/, "");
}

export async function fetchProviders(
  baseUrl: string = getApiUrl(),
  fetchImpl: typeof fetch = fetch,
): Promise<ProviderStatus[] | null> {
  if (!baseUrl) return null;

  const url = `${baseUrl}/v1/data/providers`;
  const response = await fetchImpl(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "omit",
  });

  if (!response.ok) {
    throw new Error(`provider-status fetch failed: HTTP ${response.status}`);
  }

  const payload: unknown = await response.json();
  return normalize(payload);
}

function normalize(payload: unknown): ProviderStatus[] {
  if (!payload || typeof payload !== "object") {
    throw new Error("provider-status payload is not an object");
  }
  const list = (payload as { providers?: unknown }).providers;
  if (!Array.isArray(list)) {
    throw new Error("provider-status payload missing 'providers' array");
  }

  const out: ProviderStatus[] = [];
  for (const item of list) {
    if (!item || typeof item !== "object") {
      throw new Error("provider-status entry is not an object");
    }
    const rec = item as Record<string, unknown>;
    const name = rec.name;
    const kind = rec.kind;
    const enabled = rec.enabled;
    const reason = rec.reason;
    const requires = rec.requires;

    if (typeof name !== "string") throw new Error("provider 'name' missing/invalid");
    if (kind !== "fetch" && kind !== "upload") {
      throw new Error(`provider 'kind' invalid: ${String(kind)}`);
    }
    if (typeof enabled !== "boolean") throw new Error("provider 'enabled' missing/invalid");
    if (typeof reason !== "string") throw new Error("provider 'reason' missing/invalid");
    if (!Array.isArray(requires) || !requires.every((r) => typeof r === "string")) {
      throw new Error("provider 'requires' must be an array of strings");
    }

    out.push({
      name,
      kind,
      enabled,
      reason,
      requires: requires as string[],
    });
  }
  return out;
}
