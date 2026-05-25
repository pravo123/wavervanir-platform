"""Mint a single API key out-of-band — staging smoke testing only.

Usage (operator-driven, never automated):

    python -m wavervanir_api.tools.bootstrap_key \
        --plan researcher \
        --label "staging-smoke-2026-05-25"

Behavior:
    * Refuses to run if ``WAVERVANIR_ENV`` is ``prod``.
    * Refuses to run if ``WAVERVANIR_API_KEY_PEPPER`` is missing, the default
      sentinel, or shorter than the minimum (see ``config.staging_guard``).
    * Refuses unknown plan names.
    * Calls the existing ``auth.provision_key`` to mint a real, peppered key
      in the configured DB (SQLite locally, Render Postgres in staging).
    * Prints the raw ``wvk_…`` token exactly once on stdout.
    * Writes an ``audit_log`` row with ``route="/tools/bootstrap_key"``,
      ``request_sha256 = sha256(label)``, ``response_sha256 = sha256(key_id)``
      so the bootstrap mint is traceable.

The raw token is never persisted by this tool. The operator is responsible
for copying it into a password manager immediately.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from wavervanir_api.audit import record_audit, sha256_of_obj
from wavervanir_api.auth import generate_raw_token, provision_key
from wavervanir_api.config import get_settings, staging_guard
from wavervanir_api.plans import all_plan_names, get_plan, is_known_plan


EXIT_OK = 0
EXIT_GUARD_FAILED = 2
EXIT_UNKNOWN_PLAN = 3
EXIT_UNEXPECTED = 10


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bootstrap_key",
        description=(
            "Mint a single staging API key out-of-band. "
            "Refuses to run against prod or with a weak/default pepper."
        ),
    )
    p.add_argument(
        "--plan",
        default="researcher",
        choices=list(all_plan_names()),
        help="Plan to assign to the new key. Default: researcher.",
    )
    p.add_argument(
        "--label",
        default="staging-bootstrap",
        help=(
            "Free-form label hashed into the audit row's request_sha256. "
            "Use a date / purpose string."
        ),
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    # 1. Env / pepper sanity.
    guard = staging_guard(settings)
    if not guard.ok:
        print(f"[bootstrap_key] REFUSED — {guard.reason}", file=sys.stderr)
        return EXIT_GUARD_FAILED

    # 2. Plan whitelist (argparse already restricts, but defensive).
    if not is_known_plan(args.plan):
        print(f"[bootstrap_key] REFUSED — unknown plan {args.plan!r}", file=sys.stderr)
        return EXIT_UNKNOWN_PLAN

    plan = get_plan(args.plan)
    tier = "free" if plan.name == "free" else "paid"

    # 3. Mint.
    raw = generate_raw_token()
    try:
        row = provision_key(
            raw_token=raw,
            tier=tier,
            stripe_customer_id=None,
            settings=settings,
            plan=plan.name,
            stripe_subscription_id=None,
        )
    except Exception as exc:  # pragma: no cover — defensive
        print(f"[bootstrap_key] FAILED to provision: {exc!r}", file=sys.stderr)
        return EXIT_UNEXPECTED

    # 4. Audit row (hashes only — raw token never persisted in audit_log).
    record_audit(
        settings=settings,
        key_id=row.id,
        route="/tools/bootstrap_key",
        request_obj={"label": args.label, "plan": plan.name},
        response_obj={"api_key_id": row.id, "plan": plan.name},
        status_code=200,
        latency_ms=0,
    )

    # 5. Disclose exactly once.
    print(
        f"[bootstrap_key] OK\n"
        f"  api_key_id : {row.id}\n"
        f"  plan       : {plan.name}\n"
        f"  daily_cap  : {plan.daily_cap}\n"
        f"  label      : {args.label}\n"
        f"  api_key    : {raw}\n"
        f"\n"
        f"This token will NOT be shown again. Copy it to a password manager now.\n"
        f"Audit fingerprint: request_sha256={sha256_of_obj({'label': args.label, 'plan': plan.name})}"
    )
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover — entry point
    sys.exit(main())
