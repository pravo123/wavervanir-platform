/**
 * PricingCta — single CTA button used by each pricing tile.
 *
 * Self-serve plans (researcher, pro) link to the Stripe Payment Link
 * configured via VITE_STRIPE_LINK_* env vars. Sales-assisted plans
 * (institutional, regulator) link to the in-page waitlist anchor.
 *
 * The env vars are PUBLIC by design — Vite inlines them into the bundle.
 * Never put server-side secrets in VITE_*.
 */

type CtaKind = "researcher" | "pro" | "institutional" | "regulator";

function readEnv(): Record<string, string | undefined> {
  // Read at call time so vi.stubEnv() works in tests and runtime overrides apply.
  // The literal ``import.meta.env`` access is required so Vite's compile-time
  // substitution (and vitest's stubEnv) sees it. We do not add `vite/client`
  // to tsconfig.types in this slice — silence the missing-type error narrowly.
  // @ts-expect-error vite/client types are not registered in tsconfig.types
  return import.meta.env as Record<string, string | undefined>;
}

export function ctaHrefFor(kind: CtaKind): string {
  const env = readEnv();
  const researcherLink = env.VITE_STRIPE_LINK_RESEARCHER ?? "";
  const proLink = env.VITE_STRIPE_LINK_PRO ?? "";
  const institutionalHref = env.VITE_INSTITUTIONAL_HREF ?? "#waitlist";
  switch (kind) {
    case "researcher":
      return researcherLink || "#waitlist";
    case "pro":
      return proLink || "#waitlist";
    case "institutional":
    case "regulator":
      return institutionalHref;
  }
}

export function ctaLabelFor(kind: CtaKind): string {
  switch (kind) {
    case "researcher":
    case "pro":
      return "Start in test mode";
    case "institutional":
    case "regulator":
      return "Contact sales";
  }
}

export function ctaIsExternal(kind: CtaKind): boolean {
  const href = ctaHrefFor(kind);
  return href.startsWith("http://") || href.startsWith("https://");
}

export default function PricingCta({ kind }: { kind: CtaKind }) {
  const href = ctaHrefFor(kind);
  const label = ctaLabelFor(kind);
  const external = ctaIsExternal(kind);
  return (
    <a
      className="btn btn--primary"
      href={href}
      data-testid={`cta-${kind}`}
      data-cta-kind={kind}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
    >
      {label}
    </a>
  );
}
