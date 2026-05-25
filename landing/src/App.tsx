import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Pricing from "./components/Pricing";
import Waitlist from "./components/Waitlist";
import DataProviderStatus from "./components/DataProviderStatus";
import MarketSnapshotGrid from "./components/MarketSnapshotGrid";
import RiskIntelligencePreview from "./components/RiskIntelligencePreview";
import PortfolioRiskPreview from "./components/PortfolioRiskPreview";
import DemoReportPreview from "./components/DemoReportPreview";
import { DEMO_DATA_DISCLAIMER } from "./data/demoRisk";

export default function App() {
  return (
    <>
      <Nav />
      <Hero />

      <section id="demo" className="section">
        <div className="container">
          <h2 className="section__title">Demo Risk Intelligence Dashboard</h2>
          <p className="section__lead" data-testid="demo-disclaimer">
            {DEMO_DATA_DISCLAIMER}
          </p>

          <h3 className="subhead">Data providers</h3>
          <DataProviderStatus />

          <h3 className="subhead">Market snapshot</h3>
          <MarketSnapshotGrid />

          <h3 className="subhead">Flow / risk intelligence</h3>
          <RiskIntelligencePreview />

          <h3 className="subhead">Portfolio risk summary (sanitized example)</h3>
          <PortfolioRiskPreview />

          <h3 className="subhead">Report</h3>
          <DemoReportPreview />
        </div>
      </section>

      <section id="pricing" className="section">
        <div className="container">
          <h2 className="section__title">Pricing</h2>
          <p className="section__lead">
            Start free with the public methodology. Upgrade for hosted API access, audit-friendly
            reporting, and institutional support.
          </p>
          <Pricing />
        </div>
      </section>
      <section id="waitlist" className="section">
        <div className="container">
          <h2 className="section__title">Institutional Waitlist</h2>
          <p className="section__lead">
            For multi-broker execution-risk, regulator pilots, and bespoke cross-jurisdiction
            reporting — join the waitlist.
          </p>
          <Waitlist />
        </div>
      </section>
      <footer className="footer">
        © 2026 WaverVanir International LLC — Apache-2.0 methodology, hosted SaaS surface.
      </footer>
    </>
  );
}
