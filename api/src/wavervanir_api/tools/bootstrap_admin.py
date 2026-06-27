"""Create or promote the owner/admin account — operator-run, never automated.

Usage (interactive — the password is typed at a HIDDEN prompt, never shown,
never passed as an argument, never written to disk):

    python -m wavervanir_api.tools.bootstrap_admin --email prabhawa@wavervanir.com

Or non-interactively (e.g. a one-shot Render job), with the password supplied
ONLY via an environment variable the shell never echoes:

    CBSRM_ADMIN_PASSWORD=... python -m wavervanir_api.tools.bootstrap_admin \
        --email prabhawa@wavervanir.com --name "Prabhawa"

Behavior:
    * Defaults ``--email`` to the first configured owner email
      (``WAVERVANIR_ADMIN_EMAILS`` / ``config.admin_emails``).
    * New account → registers it with the typed password, then flags admin.
    * Existing account → promotes to admin; the password is changed only with
      ``--reset-password``.
    * Grants full access (admins bypass the subscription gate).
    * Writes an ``audit_log`` row (hashes only — the password is never stored).
    * Prints a summary WITHOUT the password.

The raw password is never logged, returned, or persisted.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import Optional, Sequence

from wavervanir_api.audit import record_audit
from wavervanir_api.config import admin_email_set, get_settings
from wavervanir_api.users import AuthService, AuthError, MIN_PASSWORD_LEN

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_FAILED = 10


def _default_email(settings) -> Optional[str]:
    emails = sorted(admin_email_set(settings))
    return emails[0] if emails else None


def _read_password(reset: bool) -> Optional[str]:
    """Password from CBSRM_ADMIN_PASSWORD env, else a hidden double prompt."""
    env = os.environ.get("CBSRM_ADMIN_PASSWORD")
    if env:
        return env
    if not sys.stdin.isatty():
        print("[bootstrap_admin] no TTY and CBSRM_ADMIN_PASSWORD unset — aborting.",
              file=sys.stderr)
        return None
    prompt = "New admin password: " if not reset else "New (reset) admin password: "
    p1 = getpass.getpass(prompt)
    p2 = getpass.getpass("Confirm password: ")
    if p1 != p2:
        print("[bootstrap_admin] passwords did not match.", file=sys.stderr)
        return None
    return p1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bootstrap_admin",
        description="Create/promote the owner admin account. Password via hidden prompt or CBSRM_ADMIN_PASSWORD.",
    )
    p.add_argument("--email", default=None, help="Admin email (default: first configured owner email).")
    p.add_argument("--name", default="", help="Display name.")
    p.add_argument("--reset-password", action="store_true",
                   help="If the account exists, also reset its password.")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    email = (args.email or _default_email(settings) or "").strip()
    if not email or "@" not in email:
        print("[bootstrap_admin] no valid --email and no configured owner email.", file=sys.stderr)
        return EXIT_BAD_INPUT

    password = _read_password(args.reset_password)
    if not password:
        return EXIT_BAD_INPUT
    if len(password) < MIN_PASSWORD_LEN:
        print(f"[bootstrap_admin] password too short (min {MIN_PASSWORD_LEN}).", file=sys.stderr)
        return EXIT_BAD_INPUT

    try:
        user = AuthService(settings).provision_admin(
            email=email, password=password, name=args.name, reset_password=args.reset_password
        )
    except AuthError as exc:
        print(f"[bootstrap_admin] FAILED: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[bootstrap_admin] UNEXPECTED: {exc!r}", file=sys.stderr)
        return EXIT_FAILED

    # Audit (hashes only; password never recorded).
    record_audit(
        settings=settings,
        key_id=user.id,
        route="/tools/bootstrap_admin",
        request_obj={"email": email, "reset_password": bool(args.reset_password)},
        response_obj={"user_id": user.id, "is_admin": True},
        status_code=200,
        latency_ms=0,
    )

    print(
        "[bootstrap_admin] OK\n"
        f"  user_id   : {user.id}\n"
        f"  email     : {user.email}\n"
        f"  is_admin  : {user.is_admin}\n"
        f"  full access: admins bypass the subscription gate.\n"
        "Sign in at /app with this email and the password you just set."
    )
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - entry point
    sys.exit(main())
