"""The user-login signing secret fails closed (CBSRM Desk pilot guard, 2026-10-19).

``WAVERVANIR_JWT_SECRET`` left at the local-dev sentinel, empty, or shorter than ``MIN_JWT_SECRET_LENGTH`` refuses settings
construction in every environment except the explicit synthetic ``WAVERVANIR_ENV=test``; a supplied non-default secret starts the
app, signs and verifies tokens, and every auth/entitlement refusal is unchanged. No secret value is ever printed: the assertions
check the reason text names the variable, not the value.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from wavervanir_api.config import DEFAULT_JWT_SENTINEL, MIN_JWT_SECRET_LENGTH, get_settings

STRONG = "synthetic-test-only-signing-secret-0123456789"  # >= MIN_JWT_SECRET_LENGTH, never a real key
EMAIL, PW = "guard-synthetic@synthetic-audit-only.org", "Synthetic-Pass-Phrase-1234!"


def _settings_with(monkeypatch: pytest.MonkeyPatch, env: str, secret: str | None):
    monkeypatch.setenv("WAVERVANIR_ENV", env)
    if secret is None:
        monkeypatch.delenv("WAVERVANIR_JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("WAVERVANIR_JWT_SECRET", secret)
    get_settings.cache_clear()
    return get_settings()


@pytest.mark.parametrize("env", ["dev", "staging", "prod", "production", "DEV"])
def test_sentinel_secret_refuses_outside_test(monkeypatch, env):
    with pytest.raises(ValueError, match="WAVERVANIR_JWT_SECRET is the local-dev sentinel"):
        _settings_with(monkeypatch, env, DEFAULT_JWT_SENTINEL)


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_unset_secret_is_the_sentinel_and_refuses(monkeypatch, env):
    with pytest.raises(ValueError, match="sentinel"):
        _settings_with(monkeypatch, env, None)


@pytest.mark.parametrize("secret", ["", "short", "x" * (MIN_JWT_SECRET_LENGTH - 1)])
def test_short_or_empty_secret_refuses(monkeypatch, secret):
    with pytest.raises(ValueError, match="WAVERVANIR_JWT_SECRET is"):
        _settings_with(monkeypatch, "staging", secret)


def test_the_refusal_never_echoes_the_secret_value(monkeypatch):
    leaky = "leak-me-" + "q" * 10  # short on purpose, so it is refused
    with pytest.raises(ValueError) as caught:
        _settings_with(monkeypatch, "staging", leaky)
    assert leaky not in str(caught.value) and "leak-me" not in str(caught.value)


def test_create_app_refuses_with_the_sentinel_outside_test(monkeypatch):
    monkeypatch.setenv("WAVERVANIR_ENV", "staging")
    monkeypatch.setenv("WAVERVANIR_JWT_SECRET", DEFAULT_JWT_SENTINEL)
    get_settings.cache_clear()
    from wavervanir_api.app import create_app

    with pytest.raises(ValueError, match="sentinel"):
        create_app()


def test_explicit_test_environment_keeps_the_synthetic_default(monkeypatch):
    s = _settings_with(monkeypatch, "test", None)
    assert s.jwt_secret == DEFAULT_JWT_SENTINEL  # the suite's own configuration stays usable


def test_a_supplied_secret_starts_signs_verifies_and_keeps_every_refusal(monkeypatch):
    monkeypatch.setenv("WAVERVANIR_ENV", "staging")
    monkeypatch.setenv("WAVERVANIR_JWT_SECRET", STRONG)
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", "p" * 48)
    get_settings.cache_clear()
    from wavervanir_api import db as db_module
    from wavervanir_api.app import create_app

    db_module.reset_engine()
    with TestClient(create_app()) as c:
        assert c.get("/health").status_code == 200
        assert c.post("/auth/register", json={"email": EMAIL, "password": PW}).status_code == 201
        assert c.post("/auth/login", json={"email": EMAIL, "password": "wrong-" + PW}).status_code == 401
        login = c.post("/auth/login", json={"email": EMAIL, "password": PW})
        assert login.status_code == 200
        tokens = login.json()
        auth = {"Authorization": "Bearer " + tokens["access_token"]}
        me = c.get("/auth/me", headers=auth)
        assert me.status_code == 200 and me.json()["plan"] == "free"
        # entitlement refusals unchanged under the supplied secret
        who = c.get("/v1/desk/whoami", headers=auth)
        assert who.status_code == 403 and who.json()["detail"]["error"] == "desk_subscription_required"
        assert c.get("/v1/desk/whoami").status_code == 401
        assert c.get("/auth/me", headers={"Authorization": "Bearer " + tokens["access_token"][:-2] + "xx"}).status_code == 401
        refreshed = c.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refreshed.status_code == 200 and refreshed.json()["refresh_token"] != tokens["refresh_token"]
        # a token signed under a DIFFERENT secret is not accepted here
        from wavervanir_api.security import create_access_token

        foreign = create_access_token(1, "another-synthetic-secret-0123456789abcdef", ttl_minutes=5, extra={"email": EMAIL, "plan": "free"})
        assert c.get("/auth/me", headers={"Authorization": "Bearer " + foreign}).status_code == 401
