const LOGO_SRC = "/brand/wavervanir-logo.png";
const LOGO_ALT = "WaverVanir — Process Over Prediction";

export default function Hero() {
  return (
    <header className="hero">
      <div className="container">
        <img
          className="hero__logo"
          src={LOGO_SRC}
          alt={LOGO_ALT}
          width={220}
          height={220}
          loading="eager"
          decoding="async"
        />
        <h1 className="hero__h1">
          Audit-friendly <span>systemic-risk intelligence</span>
        </h1>
        <p className="hero__sub">
          WaverVanir Risk Intelligence Platform combines the open CBSRM methodology with a hosted,
          authenticated research API and an institutional-grade audit chain. Process over
          prediction.
        </p>
        <div className="hero__cta">
          <a className="btn btn--primary" href="#pricing">
            View pricing
          </a>
          <a className="btn btn--ghost" href="#waitlist">
            Join institutional waitlist
          </a>
        </div>
      </div>
    </header>
  );
}
