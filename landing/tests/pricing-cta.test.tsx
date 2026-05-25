/**
 * Pricing CTA contract:
 *   • Researcher + Pro CTAs use VITE_STRIPE_LINK_* values.
 *   • Institutional + Regulator CTAs fall back to the waitlist anchor.
 *   • External CTAs open in a new tab with noopener+noreferrer.
 *   • The component never emits any sk_*, whsec_*, or other server-secret string.
 */
import { render, screen } from "@testing-library/react";
import PricingCta from "../src/components/PricingCta";
import Pricing from "../src/components/Pricing";

// Mock the env BEFORE component import via vi.stubEnv.
beforeAll(() => {
  vi.stubEnv("VITE_STRIPE_LINK_RESEARCHER", "https://buy.stripe.com/test_fake_researcher");
  vi.stubEnv("VITE_STRIPE_LINK_PRO", "https://buy.stripe.com/test_fake_pro");
  vi.stubEnv("VITE_INSTITUTIONAL_HREF", "#waitlist");
});

describe("PricingCta wiring", () => {
  it("researcher CTA points to VITE_STRIPE_LINK_RESEARCHER and is external", () => {
    render(<PricingCta kind="researcher" />);
    const a = screen.getByTestId("cta-researcher") as HTMLAnchorElement;
    expect(a.getAttribute("href")).toMatch(/^https:\/\/buy\.stripe\.com\/test_/);
    expect(a.getAttribute("target")).toBe("_blank");
    expect(a.getAttribute("rel")).toContain("noopener");
    expect(a.getAttribute("rel")).toContain("noreferrer");
  });

  it("pro CTA points to VITE_STRIPE_LINK_PRO and is external", () => {
    render(<PricingCta kind="pro" />);
    const a = screen.getByTestId("cta-pro") as HTMLAnchorElement;
    expect(a.getAttribute("href")).toMatch(/^https:\/\/buy\.stripe\.com\/test_/);
    expect(a.getAttribute("target")).toBe("_blank");
  });

  it("institutional CTA routes to waitlist anchor (in-page)", () => {
    render(<PricingCta kind="institutional" />);
    const a = screen.getByTestId("cta-institutional") as HTMLAnchorElement;
    expect(a.getAttribute("href")).toBe("#waitlist");
    expect(a.getAttribute("target")).toBeNull();
  });

  it("regulator CTA routes to waitlist anchor (in-page)", () => {
    render(<PricingCta kind="regulator" />);
    const a = screen.getByTestId("cta-regulator") as HTMLAnchorElement;
    expect(a.getAttribute("href")).toBe("#waitlist");
  });
});

describe("Pricing renders one CTA per tier with safe attributes", () => {
  it("renders 4 tiers with CTAs and no leaked server secrets", () => {
    const { container } = render(<Pricing />);
    const ctas = container.querySelectorAll("[data-cta-kind]");
    expect(ctas.length).toBe(4);
    const html = container.innerHTML;
    // Defensive: a server-side secret must never end up in the DOM.
    expect(html).not.toMatch(/sk_(test|live)_/);
    expect(html).not.toMatch(/whsec_/);
  });
});
