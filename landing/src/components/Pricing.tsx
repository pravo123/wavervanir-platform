import PricingCta from "./PricingCta";

type Tier = {
  kind: "researcher" | "pro" | "institutional" | "regulator";
  name: string;
  price: string;
  suffix?: string;
  features: string[];
  featured?: boolean;
};

const TIERS: Tier[] = [
  {
    kind: "researcher",
    name: "Researcher",
    price: "$49",
    suffix: "/mo",
    features: [
      "5,000 hosted-API calls / day",
      "Macro-composite endpoint",
      "Public CBSRM library",
      "Community support",
    ],
  },
  {
    kind: "pro",
    name: "Pro",
    price: "$499",
    suffix: "/mo",
    features: [
      "15,000 hosted-API calls / day",
      "All CBSRM endpoints (roadmap)",
      "Audit-chain access",
      "Email support, SLA-lite",
    ],
    featured: true,
  },
  {
    kind: "institutional",
    name: "Institutional",
    price: "From $4,999",
    suffix: "/mo",
    features: [
      "SLA + dedicated rate-tier",
      "On-prem / VPC deployment option",
      "Cross-jurisdiction reporting",
      "Solution-engineer hours",
    ],
  },
  {
    kind: "regulator",
    name: "Regulator / Central Bank",
    price: "Bespoke",
    features: [
      "Pilot engagement",
      "Custom indicators",
      "Audit-log export",
      "Procurement-friendly",
    ],
  },
];

export default function Pricing() {
  return (
    <div className="pricing">
      {TIERS.map((t) => (
        <div key={t.name} className={`tier${t.featured ? " tier--featured" : ""}`}>
          <div className="tier__name">{t.name}</div>
          <div className="tier__price">
            {t.price}
            {t.suffix && <small>{t.suffix}</small>}
          </div>
          <ul>
            {t.features.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <div style={{ marginTop: 18 }}>
            <PricingCta kind={t.kind} />
          </div>
        </div>
      ))}
    </div>
  );
}
