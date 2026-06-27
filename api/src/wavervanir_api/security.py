"""Security primitives for the CBSRM Desk sign-in layer — stdlib only.

Two responsibilities, both intentionally dependency-free so the authentication
path carries no third-party crypto and builds on any interpreter (including
bleeding-edge CPython, where native wheels routinely lag a new release):

1. **Password hashing** — salted, memory-hard :func:`hashlib.scrypt`
   (argon2id-class), with a PBKDF2-HMAC-SHA256 fallback for the rare build whose
   OpenSSL lacks scrypt. Hashes are *self-describing* strings, so
   :func:`verify_password` dispatches on the stored algorithm and parameters.
   Verification is constant-time.

2. **JSON Web Tokens** — a minimal, auditable HS256 implementation: base64url
   header + payload + HMAC-SHA256 signature, with ``typ``/``exp`` validation and
   a constant-time signature compare. Shaped like a standard JWT so a library
   (PyJWT, python-jose) can be swapped in later without changing callers.

Design notes
------------
* The signature is verified *before* any untrusted JSON is parsed.
* ``alg`` confusion / "alg=none" is impossible: we always HMAC-verify with
  HS256 and additionally require the (signature-covered) header to say HS256.
* No raw password or token secret is ever logged or returned.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional


# ── base64url helpers (no padding, URL-safe) ────────────────────────────────


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# ── password hashing ────────────────────────────────────────────────────────

_SCRYPT_N = 1 << 14   # 16384 — CPU/memory cost (≈16 MiB working set)
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32
_PBKDF2_ITERS = 600_000   # OWASP floor for PBKDF2-HMAC-SHA256
_SALT_BYTES = 16


def _scrypt_available() -> bool:
    """True iff this build's OpenSSL exposes scrypt (almost always)."""
    try:
        hashlib.scrypt(b"probe", salt=b"x" * 16, n=2, r=8, p=1, dklen=16)
        return True
    except Exception:  # pragma: no cover - exotic OpenSSL builds only
        return False


def hash_password(password: str) -> str:
    """Return a self-describing, salted hash of ``password``.

    Format (preferred): ``scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>``
    Format (fallback):  ``pbkdf2$<iters>$<salt_b64>$<hash_b64>``
    """
    if not isinstance(password, str) or password == "":
        raise ValueError("password must be a non-empty string")
    salt = os.urandom(_SALT_BYTES)
    if _scrypt_available():
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_DKLEN,
        )
        return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(dk)}"
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS, dklen=_DKLEN
    )
    return f"pbkdf2${_PBKDF2_ITERS}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify ``password`` against ``stored``. Never raises."""
    try:
        if not password or not stored:
            return False
        parts = stored.split("$")
        algo = parts[0]
        if algo == "scrypt":
            _, n, r, p, salt_b64, hash_b64 = parts
            expected = _b64d(hash_b64)
            dk = hashlib.scrypt(
                password.encode("utf-8"),
                salt=_b64d(salt_b64),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(expected),
            )
            return hmac.compare_digest(dk, expected)
        if algo == "pbkdf2":
            _, iters, salt_b64, hash_b64 = parts
            expected = _b64d(hash_b64)
            dk = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), _b64d(salt_b64), int(iters), dklen=len(expected)
            )
            return hmac.compare_digest(dk, expected)
        return False
    except Exception:
        return False


# ── JSON Web Tokens (HS256, stdlib) ─────────────────────────────────────────


class TokenError(Exception):
    """Raised when a token is missing, malformed, mis-typed, or expired."""


_JWT_HEADER = {"alg": "HS256", "typ": "JWT"}


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _sign(signing_input: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _b64e(sig)


def _encode(claims: dict[str, Any], secret: str) -> str:
    header_b64 = _b64e(
        json.dumps(_JWT_HEADER, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_b64 = _b64e(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    return f"{header_b64}.{payload_b64}.{_sign(signing_input, secret)}"


def create_token(
    *,
    subject: Any,
    token_type: str,
    secret: str,
    ttl_seconds: int,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """Mint a signed token. ``token_type`` is the enforced ``typ`` claim."""
    iat = _now_ts()
    claims: dict[str, Any] = {
        "sub": str(subject),
        "typ": token_type,
        "iat": iat,
        "exp": iat + int(ttl_seconds),
        "jti": secrets.token_urlsafe(8),
    }
    if extra:
        claims.update(extra)
    return _encode(claims, secret)


def create_access_token(
    subject: Any, secret: str, *, ttl_minutes: int = 15, extra: Optional[dict[str, Any]] = None
) -> str:
    return create_token(
        subject=subject, token_type="access", secret=secret,
        ttl_seconds=ttl_minutes * 60, extra=extra,
    )


def create_refresh_token(
    subject: Any, secret: str, *, ttl_days: int = 7, extra: Optional[dict[str, Any]] = None
) -> str:
    return create_token(
        subject=subject, token_type="refresh", secret=secret,
        ttl_seconds=ttl_days * 86_400, extra=extra,
    )


def decode_token(
    token: str, secret: str, *, expected_type: Optional[str] = None
) -> dict[str, Any]:
    """Verify signature + expiry (+ optional ``typ``); return the claims.

    Raises :class:`TokenError` on any failure. Signature is checked before the
    payload JSON is parsed.
    """
    if not token or not isinstance(token, str):
        raise TokenError("missing token")
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("malformed token")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    if not hmac.compare_digest(_sign(signing_input, secret), sig_b64):
        raise TokenError("bad signature")
    try:
        header = json.loads(_b64d(header_b64))
        claims = json.loads(_b64d(payload_b64))
    except Exception as exc:  # pragma: no cover - corrupt token
        raise TokenError(f"undecodable token: {exc!r}")
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise TokenError("unexpected token alg")
    if not isinstance(claims, dict):
        raise TokenError("bad claims")
    exp = claims.get("exp")
    if not isinstance(exp, int) or _now_ts() >= exp:
        raise TokenError("expired token")
    if expected_type is not None and claims.get("typ") != expected_type:
        raise TokenError(f"expected {expected_type} token, got {claims.get('typ')!r}")
    return claims
