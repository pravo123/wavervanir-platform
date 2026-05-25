"""Auth dependency contract tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from wavervanir_api.auth import (
    AuthContext,
    generate_raw_token,
    hash_token,
    provision_key,
    require_api_key,
    revoke_key_by_stripe_customer,
)
from wavervanir_api.config import get_settings


def _mini_app() -> FastAPI:
    """Smallest possible app that exercises the auth dependency."""
    app = FastAPI()

    @app.get("/protected")
    def protected(ctx: AuthContext = Depends(require_api_key)):
        return {"key_id": ctx.key_id, "tier": ctx.tier}

    return app


def test_hash_token_is_deterministic():
    h1 = hash_token("wvk_abc", "pepper")
    h2 = hash_token("wvk_abc", "pepper")
    assert h1 == h2
    assert h1 != hash_token("wvk_abc", "different-pepper")


def test_generate_raw_token_has_prefix():
    t = generate_raw_token()
    assert t.startswith("wvk_")
    assert len(t) > 16


def test_missing_authorization_header_returns_401(isolated_settings):
    with TestClient(_mini_app()) as c:
        r = c.get("/protected")
        assert r.status_code == 401
        assert "missing" in r.json()["detail"].lower()


def test_malformed_authorization_returns_401(isolated_settings):
    with TestClient(_mini_app()) as c:
        r = c.get("/protected", headers={"Authorization": "Token xyz"})
        assert r.status_code == 401


def test_empty_bearer_returns_401(isolated_settings):
    with TestClient(_mini_app()) as c:
        r = c.get("/protected", headers={"Authorization": "Bearer "})
        assert r.status_code == 401


def test_unknown_token_returns_401(isolated_settings):
    with TestClient(_mini_app()) as c:
        r = c.get("/protected", headers={"Authorization": "Bearer wvk_never_issued"})
        assert r.status_code == 401


def test_valid_token_succeeds(isolated_settings):
    raw = generate_raw_token()
    row = provision_key(raw, tier="paid", stripe_customer_id="cus_test", settings=get_settings())
    with TestClient(_mini_app()) as c:
        r = c.get("/protected", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 200
        body = r.json()
        assert body["key_id"] == row.id
        assert body["tier"] == "paid"


def test_revoked_token_returns_401(isolated_settings):
    raw = generate_raw_token()
    provision_key(raw, tier="paid", stripe_customer_id="cus_test", settings=get_settings())
    count = revoke_key_by_stripe_customer("cus_test", get_settings())
    assert count == 1
    with TestClient(_mini_app()) as c:
        r = c.get("/protected", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 401
