"""Unit contract for the stdlib security primitives (scrypt + HS256 JWT)."""

from __future__ import annotations

import pytest

from wavervanir_api.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-please-rotate-32chars"


# ── passwords ────────────────────────────────────────────────────────────────


def test_hash_password_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong password", h) is False


def test_hash_password_is_salted_and_self_describing():
    h1 = hash_password("same-password-123")
    h2 = hash_password("same-password-123")
    assert h1 != h2  # random per-password salt
    assert verify_password("same-password-123", h1)
    assert verify_password("same-password-123", h2)
    assert h1.split("$")[0] in ("scrypt", "pbkdf2")


def test_hash_password_rejects_empty():
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_password_never_raises_on_garbage():
    assert verify_password("x", "not-a-valid-hash") is False
    assert verify_password("", "scrypt$1$2$3$zzz$zzz") is False
    assert verify_password("x", "") is False


# ── JWT ──────────────────────────────────────────────────────────────────────


def test_access_token_roundtrip():
    token = create_access_token(42, SECRET, ttl_minutes=15)
    claims = decode_token(token, SECRET, expected_type="access")
    assert claims["sub"] == "42"
    assert claims["typ"] == "access"
    assert claims["exp"] > claims["iat"]


def test_wrong_secret_rejected():
    token = create_access_token(1, SECRET)
    with pytest.raises(TokenError):
        decode_token(token, "a-different-secret")


def test_token_type_enforced():
    refresh = create_refresh_token(7, SECRET)
    # A refresh token must not pass where an access token is required.
    with pytest.raises(TokenError):
        decode_token(refresh, SECRET, expected_type="access")
    # ... but it validates as a refresh token.
    claims = decode_token(refresh, SECRET, expected_type="refresh")
    assert claims["typ"] == "refresh"


def test_expired_token_rejected():
    token = create_token(subject=1, token_type="access", secret=SECRET, ttl_seconds=-5)
    with pytest.raises(TokenError):
        decode_token(token, SECRET)


def test_tampered_payload_rejected():
    token = create_access_token(1, SECRET)
    head, payload, sig = token.split(".")
    # Flip a character in the payload segment; signature must no longer match.
    forged_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    forged = f"{head}.{forged_payload}.{sig}"
    with pytest.raises(TokenError):
        decode_token(forged, SECRET)


def test_malformed_token_rejected():
    for bad in ("", "x", "a.b", "a.b.c.d"):
        with pytest.raises(TokenError):
            decode_token(bad, SECRET)
