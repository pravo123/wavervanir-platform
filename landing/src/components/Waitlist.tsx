import { useState } from "react";

const TIERS = ["researcher", "pro", "institutional", "exec_risk", "regulator"];

type Status =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "ok"; deduped: boolean }
  | { kind: "error"; message: string };

export default function Waitlist() {
  const [email, setEmail] = useState("");
  const [tier, setTier] = useState("institutional");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus({ kind: "submitting" });
    try {
      const r = await fetch("/v1/waitlist", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, tier_interest: tier, source: "landing" }),
      });
      if (!r.ok) {
        setStatus({ kind: "error", message: `HTTP ${r.status}` });
        return;
      }
      const body = await r.json();
      setStatus({ kind: "ok", deduped: Boolean(body.deduplicated) });
    } catch (err) {
      setStatus({ kind: "error", message: String(err) });
    }
  }

  return (
    <form className="waitlist" onSubmit={handleSubmit} aria-label="Institutional waitlist signup">
      <div className="waitlist__row">
        <input
          type="email"
          required
          placeholder="you@institution.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-label="Work email"
        />
        <select
          value={tier}
          onChange={(e) => setTier(e.target.value)}
          aria-label="Tier interest"
        >
          {TIERS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button className="btn btn--primary" type="submit" disabled={status.kind === "submitting"}>
          {status.kind === "submitting" ? "Submitting…" : "Request access"}
        </button>
      </div>
      <div className="waitlist__status" role="status" aria-live="polite">
        {status.kind === "ok" &&
          (status.deduped
            ? "You're already on the waitlist — we'll be in touch."
            : "Thanks — you're on the waitlist.")}
        {status.kind === "error" && `Something went wrong: ${status.message}`}
      </div>
    </form>
  );
}
