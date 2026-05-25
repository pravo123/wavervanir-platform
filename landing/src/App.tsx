import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Pricing from "./components/Pricing";
import Waitlist from "./components/Waitlist";

export default function App() {
  return (
    <>
      <Nav />
      <Hero />
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
