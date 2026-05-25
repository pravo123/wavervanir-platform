const LOGO_SRC = "/brand/wavervanir-logo.png";
const LOGO_ALT = "WaverVanir — Process Over Prediction";

export default function Nav() {
  return (
    <nav className="nav" aria-label="Primary">
      <div className="nav__brand">
        <img
          className="nav__logo"
          src={LOGO_SRC}
          alt={LOGO_ALT}
          width={40}
          height={40}
          loading="eager"
          decoding="async"
        />
        <span className="nav__name">WaverVanir</span>
        <span className="nav__tagline">Process Over Prediction</span>
      </div>
      <div className="nav__links">
        <a href="#pricing">Pricing</a>
        <a href="#waitlist">Institutional</a>
        <a href="https://github.com/pravo123/cbsrm" target="_blank" rel="noreferrer">
          CBSRM
        </a>
        <a
          href="https://github.com/pravo123/derivatives-risk-framework"
          target="_blank"
          rel="noreferrer"
        >
          Framework
        </a>
      </div>
    </nav>
  );
}
