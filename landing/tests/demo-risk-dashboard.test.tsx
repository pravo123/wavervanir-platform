/**
 * Demo Risk Intelligence dashboard contract:
 *
 *   • Provider status panel renders all four providers with correct on/off state.
 *   • All six market snapshot cards render.
 *   • Flow / risk intelligence panel renders the demo flow signals.
 *   • Portfolio risk preview renders without exposing an account number.
 *   • A "no account numbers / no live brokerage connection" warning is visible.
 *   • The demo-data disclaimer is visible at the top of the section.
 *   • A "Generate demo risk report" CTA is present and toggles a report body.
 *   • Forbidden marketing copy ("guaranteed returns", "live trading", "trading bot")
 *     must not appear anywhere in the dashboard markup.
 *   • No account-number-shaped numeric strings (8–12 digits) appear in the markup.
 */
import { render, screen, within, fireEvent } from "@testing-library/react";
import App from "../src/App";
import DataProviderStatus from "../src/components/DataProviderStatus";
import MarketSnapshotGrid from "../src/components/MarketSnapshotGrid";
import RiskIntelligencePreview from "../src/components/RiskIntelligencePreview";
import PortfolioRiskPreview from "../src/components/PortfolioRiskPreview";
import DemoReportPreview from "../src/components/DemoReportPreview";

describe("Demo Risk Intelligence dashboard", () => {
  it("renders all four provider tiles with correct enabled/disabled states", () => {
    render(<DataProviderStatus />);
    const grid = screen.getByTestId("provider-grid");
    expect(within(grid).getByTestId("provider-demo")).toBeInTheDocument();
    expect(within(grid).getByTestId("provider-fmp")).toBeInTheDocument();
    expect(within(grid).getByTestId("provider-bullflow")).toBeInTheDocument();
    expect(within(grid).getByTestId("provider-broker_snapshot")).toBeInTheDocument();
    // demo + broker_snapshot are always-on; fmp + bullflow are planned/off.
    expect(within(grid).getByTestId("provider-demo").className).toMatch(/provider--on/);
    expect(within(grid).getByTestId("provider-broker_snapshot").className).toMatch(
      /provider--on/,
    );
    expect(within(grid).getByTestId("provider-fmp").className).toMatch(/provider--off/);
    expect(within(grid).getByTestId("provider-bullflow").className).toMatch(/provider--off/);
  });

  it("renders all six market snapshot symbols", () => {
    render(<MarketSnapshotGrid />);
    const grid = screen.getByTestId("market-grid");
    for (const sym of ["SPY", "QQQ", "IWM", "GLD", "TLT", "BTCUSD"]) {
      expect(within(grid).getByTestId(`mkt-${sym}`)).toBeInTheDocument();
    }
  });

  it("renders flow signals with bias labels", () => {
    render(<RiskIntelligencePreview />);
    const grid = screen.getByTestId("flow-grid");
    expect(within(grid).getByTestId("flow-SPY")).toBeInTheDocument();
    expect(within(grid).getByTestId("flow-NVDA")).toBeInTheDocument();
    expect(within(grid).getByTestId("flow-IWM")).toBeInTheDocument();
  });

  it("renders portfolio risk preview without account numbers + with explicit warning", () => {
    const { container } = render(<PortfolioRiskPreview />);
    const preview = screen.getByTestId("risk-preview");
    expect(preview).toBeInTheDocument();
    // The "no account numbers, no live brokerage connection" warning must be visible.
    const warning = screen.getByTestId("no-account-warning");
    expect(warning).toBeInTheDocument();
    expect(warning.textContent || "").toMatch(/no account numbers/i);
    expect(warning.textContent || "").toMatch(/no live brokerage connection/i);

    // No bare 8–12 digit numeric strings (account-number shape) anywhere in markup.
    const html = container.innerHTML;
    expect(html).not.toMatch(/\b\d{8,12}\b/);
  });

  it("renders the demo report CTA and toggles the report body on click", () => {
    render(<DemoReportPreview />);
    const btn = screen.getByTestId("demo-report-btn");
    expect(btn).toBeInTheDocument();
    expect(screen.queryByTestId("demo-report-body")).toBeNull();
    fireEvent.click(btn);
    const body = screen.getByTestId("demo-report-body");
    expect(body).toBeInTheDocument();
    expect(body.textContent || "").toMatch(/WaverVanir Risk Intelligence/);
    expect(body.textContent || "").toMatch(/Fixture-data preview/);
  });

  it("App renders the demo-data disclaimer at the top of the dashboard section", () => {
    render(<App />);
    const dis = screen.getByTestId("demo-disclaimer");
    expect(dis.textContent || "").toMatch(/demo uses fixture\/sample data/i);
    expect(dis.textContent || "").toMatch(/provider-ready but not active/i);
  });

  it("App does not advertise live trading, trading bots, or guaranteed returns", () => {
    const { container } = render(<App />);
    const html = container.innerHTML.toLowerCase();
    expect(html).not.toMatch(/guaranteed returns/);
    expect(html).not.toMatch(/live trading/);
    expect(html).not.toMatch(/trading bot/);
    expect(html).not.toMatch(/live execution/);
  });
});
