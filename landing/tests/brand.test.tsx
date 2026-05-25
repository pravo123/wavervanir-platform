/**
 * Brand-asset contract:
 *   • Both Nav and Hero must reference /brand/wavervanir-logo.png exactly.
 *   • Alt text must be "WaverVanir — Process Over Prediction".
 *   • The "Process Over Prediction" tagline appears in the header.
 */
import { render, screen } from "@testing-library/react";
import Nav from "../src/components/Nav";
import Hero from "../src/components/Hero";

const LOGO_SRC = "/brand/wavervanir-logo.png";
const LOGO_ALT = "WaverVanir — Process Over Prediction";

describe("brand asset wiring", () => {
  it("Nav renders the logo at the canonical path with required alt text", () => {
    const { container } = render(<Nav />);
    const logo = container.querySelector(".nav__logo") as HTMLImageElement | null;
    expect(logo).not.toBeNull();
    expect(logo!.getAttribute("alt")).toBe(LOGO_ALT);
    expect(logo!.getAttribute("src")).toBe(LOGO_SRC);
    // also assert it's actually findable by its alt text
    expect(screen.getByAltText(LOGO_ALT)).toBeInTheDocument();
  });

  it("Hero renders the logo at the canonical path with required alt text", () => {
    const { container } = render(<Hero />);
    const logo = container.querySelector(".hero__logo") as HTMLImageElement | null;
    expect(logo).not.toBeNull();
    expect(logo!.getAttribute("alt")).toBe(LOGO_ALT);
    expect(logo!.getAttribute("src")).toBe(LOGO_SRC);
  });

  it("Tagline 'Process Over Prediction' is visible in the nav", () => {
    render(<Nav />);
    expect(screen.getByText(/process over prediction/i)).toBeInTheDocument();
  });
});
