import { useEffect, useState } from "react";

import { DEMO_PROVIDERS, type ProviderStatus } from "../data/demoRisk";
import { fetchProviders, getApiUrl } from "../api/providers";

export type Props = {
  /**
   * When provided, the component renders these providers verbatim and skips
   * the live fetch entirely. Used by tests and by callers who want to inject
   * a specific state (e.g. a Storybook example).
   */
  providers?: ProviderStatus[];
};

export default function DataProviderStatus({ providers }: Props) {
  const explicitOverride = providers !== undefined;

  // null means "no live response yet". On success we swap to the live list.
  // On failure we leave it null and set fellBackToFixture = true.
  const [live, setLive] = useState<ProviderStatus[] | null>(null);
  const [fellBackToFixture, setFellBackToFixture] = useState(false);

  useEffect(() => {
    if (explicitOverride) return;
    const apiUrl = getApiUrl();
    if (!apiUrl) return; // unconfigured: stay on fixtures silently
    let cancelled = false;
    fetchProviders(apiUrl)
      .then((list) => {
        if (cancelled) return;
        if (list && list.length > 0) {
          setLive(list);
          setFellBackToFixture(false);
        } else {
          setFellBackToFixture(true);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setFellBackToFixture(true);
      });
    return () => {
      cancelled = true;
    };
  }, [explicitOverride]);

  const rendered = providers ?? live ?? DEMO_PROVIDERS;

  return (
    <>
      <div className="provider-grid" data-testid="provider-grid">
        {rendered.map((p) => (
          <div
            key={p.name}
            className={`provider provider--${p.enabled ? "on" : "off"}`}
            data-testid={`provider-${p.name}`}
          >
            <div className="provider__head">
              <span className="provider__name">{p.name}</span>
              <span className={`provider__pill provider__pill--${p.enabled ? "on" : "off"}`}>
                {p.enabled ? "available" : "planned"}
              </span>
            </div>
            <div className="provider__kind">{p.kind === "upload" ? "Upload-only" : "Fetch"}</div>
            <p className="provider__reason">{p.reason}</p>
            {p.requires.length > 0 && (
              <ul className="provider__requires">
                {p.requires.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
      {fellBackToFixture && (
        <p
          data-testid="provider-fallback-note"
          style={{
            margin: "10px 0 0",
            fontSize: "11px",
            color: "var(--fg-muted)",
            fontStyle: "italic",
          }}
        >
          Fixture fallback active.
        </p>
      )}
    </>
  );
}
