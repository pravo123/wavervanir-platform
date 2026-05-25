import { DEMO_PROVIDERS, type ProviderStatus } from "../data/demoRisk";

export type Props = { providers?: ProviderStatus[] };

export default function DataProviderStatus({ providers = DEMO_PROVIDERS }: Props) {
  return (
    <div className="provider-grid" data-testid="provider-grid">
      {providers.map((p) => (
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
  );
}
