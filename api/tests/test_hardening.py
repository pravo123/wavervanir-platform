"""Tests for the Desk-app hardening: security headers, readiness, exception
handling, Stripe-key fallback, and structured logging."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_SEC_HEADERS = {
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Content-Security-Policy",
}


# ── security headers ────────────────────────────────────────────────────────


def test_security_headers_on_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    for h in _SEC_HEADERS:
        assert h in r.headers, f"missing {h}"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    # HSTS is OFF by default (local/test is not TLS-fronted).
    assert "Strict-Transport-Security" not in r.headers


def test_security_headers_on_api_route(client):
    # A gated desk route returns 401 (HTTPException) — still passes through the
    # middleware, so headers must be present on the error response too.
    r = client.get("/v1/desk/conditions")
    assert r.status_code in (401, 403)
    assert "Content-Security-Policy" in r.headers


def test_hsts_present_when_enabled(monkeypatch):
    monkeypatch.setenv("WAVERVANIR_HSTS_ENABLED", "true")
    from wavervanir_api import db as db_module
    from wavervanir_api.app import create_app
    from wavervanir_api.config import get_settings

    get_settings.cache_clear()
    db_module.reset_engine()
    with TestClient(create_app()) as c:
        r = c.get("/health")
        assert r.headers.get("Strict-Transport-Security") == \
            "max-age=31536000; includeSubDomains"


def test_security_headers_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WAVERVANIR_SECURITY_HEADERS", "false")
    from wavervanir_api import db as db_module
    from wavervanir_api.app import create_app
    from wavervanir_api.config import get_settings

    get_settings.cache_clear()
    db_module.reset_engine()
    with TestClient(create_app()) as c:
        r = c.get("/health")
        assert "Content-Security-Policy" not in r.headers


# ── readiness ───────────────────────────────────────────────────────────────


def test_readiness_ok_when_db_up(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"] == "ok"
    # cold cache in a fresh test DB
    assert body["checks"]["conditions_cache"] in ("cold", None) or isinstance(
        body["checks"]["conditions_cache"], dict
    )
    assert body["checks"]["fred_key"] in ("set", "unset")


def test_readiness_reports_warm_cache(client):
    # Seed the conditions cache, then confirm readiness surfaces age + live count.
    from wavervanir_api import desk_conditions
    from wavervanir_api.config import get_settings

    settings = get_settings()
    desk_conditions._cache_set(
        settings, "conditions:live", "live",
        '{"summary": {"live": 11, "total": 13}}',
    )
    r = client.get("/health/ready")
    cache = r.json()["checks"]["conditions_cache"]
    assert isinstance(cache, dict)
    assert cache["live"] == 11
    assert cache["age_s"] >= 0


# ── unhandled-exception handler ─────────────────────────────────────────────


def test_unhandled_exception_is_sanitised_and_hardened():
    from wavervanir_api.config import get_settings
    from wavervanir_api.middleware import install_security_and_logging

    app = FastAPI()
    install_security_and_logging(app, get_settings())

    @app.get("/boom")
    def _boom():
        raise RuntimeError("secret internals should not leak")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    assert r.json() == {"detail": "internal server error"}
    assert "secret internals" not in r.text  # no traceback leak
    assert r.headers.get("X-Content-Type-Options") == "nosniff"  # hardened 500
    assert "Content-Security-Policy" in r.headers


# ── Stripe key fallback ─────────────────────────────────────────────────────


def test_stripe_secret_key_fallback(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_from_misnamed_var")
    from wavervanir_api.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.stripe_api_key == "sk_live_from_misnamed_var"


def test_stripe_api_key_wins_when_both_set(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_primary")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_fallback")
    from wavervanir_api.config import get_settings

    get_settings.cache_clear()
    assert get_settings().stripe_api_key == "sk_primary"


# ── structured logging ──────────────────────────────────────────────────────


def test_logging_formatter_renders_kv():
    import logging

    from wavervanir_api.logging_config import KeyValueFormatter

    rec = logging.LogRecord("wavervanir.http", logging.INFO, __file__, 1,
                            "request", None, None)
    rec.kv = {"method": "GET", "path": "/health", "status": 200}
    out = KeyValueFormatter().format(rec)
    assert "level=INFO" in out
    assert "method=GET" in out
    assert "path=/health" in out
    assert "status=200" in out
