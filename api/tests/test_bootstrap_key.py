"""Tests for the ``wavervanir_api.tools.bootstrap_key`` ops CLI."""

from __future__ import annotations

import re

import pytest
from sqlmodel import Session, select

from wavervanir_api.auth import AuthContext, hash_token, require_api_key
from wavervanir_api.config import (
    DEFAULT_PEPPER_SENTINEL,
    Settings,
    get_settings,
)
from wavervanir_api.db import ApiKey, AuditLog, get_engine
from wavervanir_api.tools.bootstrap_key import (
    EXIT_GUARD_FAILED,
    EXIT_OK,
    EXIT_UNKNOWN_PLAN,
    main as bootstrap_main,
)


# `isolated_settings` (autouse from conftest) gives each test a fresh SQLite
# file. The conftest's default pepper is short, so happy-path tests override
# it via the ``strong_pepper`` helper below to satisfy ``staging_guard``.

_STRONG_PEPPER = "x" * 64


def _use_strong_pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", _STRONG_PEPPER)
    monkeypatch.setenv("WAVERVANIR_ENV", "staging")
    get_settings.cache_clear()


def _last_audit_for_route(settings: Settings, route: str) -> AuditLog | None:
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        return session.exec(
            select(AuditLog).where(AuditLog.route == route).order_by(AuditLog.id.desc())
        ).first()


def test_happy_path_mints_researcher_key(capsys, monkeypatch, isolated_settings):
    _use_strong_pepper(monkeypatch)
    rc = bootstrap_main(["--plan", "researcher", "--label", "happy-path"])
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    # Raw token disclosed exactly once on stdout with the wvk_ prefix.
    match = re.search(r"api_key\s*:\s*(wvk_\S+)", out)
    assert match is not None, out
    raw = match.group(1)
    assert raw.startswith("wvk_")

    # The peppered hash of the disclosed token must exist as an active row.
    settings = get_settings()
    digest = hash_token(raw, settings.api_key_pepper)
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(select(ApiKey).where(ApiKey.key_hash == digest)).first()
        assert row is not None
        assert row.plan == "researcher"
        assert row.tier == "paid"
        assert row.status == "active"


def test_unknown_plan_rejected(capsys, isolated_settings):
    # argparse rejects unknown choices with SystemExit; map to EXIT_UNKNOWN_PLAN
    # semantically by asserting we never reach EXIT_OK and the exit is non-zero.
    with pytest.raises(SystemExit) as exc_info:
        bootstrap_main(["--plan", "hedge_fund", "--label", "x"])
    # argparse uses exit code 2 by default for usage errors.
    assert exc_info.value.code != EXIT_OK
    # EXIT_UNKNOWN_PLAN is reserved for the defensive branch; keep the constant
    # exported so callers can rely on it even though argparse short-circuits.
    assert EXIT_UNKNOWN_PLAN == 3


def test_default_pepper_refused(capsys, monkeypatch, isolated_settings):
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", DEFAULT_PEPPER_SENTINEL)
    get_settings.cache_clear()
    rc = bootstrap_main(["--plan", "researcher"])
    err = capsys.readouterr().err
    assert rc == EXIT_GUARD_FAILED
    assert "default sentinel" in err


def test_empty_pepper_refused(capsys, monkeypatch, isolated_settings):
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", "")
    get_settings.cache_clear()
    rc = bootstrap_main(["--plan", "researcher"])
    err = capsys.readouterr().err
    assert rc == EXIT_GUARD_FAILED
    assert "empty" in err.lower()


def test_short_pepper_refused(capsys, monkeypatch, isolated_settings):
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", "short")
    get_settings.cache_clear()
    rc = bootstrap_main(["--plan", "researcher"])
    err = capsys.readouterr().err
    assert rc == EXIT_GUARD_FAILED
    assert "too short" in err.lower()


def test_prod_env_refused(capsys, monkeypatch, isolated_settings):
    # Strong pepper, but ENV=prod should still refuse.
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", "a" * 64)
    monkeypatch.setenv("WAVERVANIR_ENV", "prod")
    get_settings.cache_clear()
    rc = bootstrap_main(["--plan", "researcher"])
    err = capsys.readouterr().err
    assert rc == EXIT_GUARD_FAILED
    assert "prod" in err


def test_audit_row_written_with_hashed_label(isolated_settings, monkeypatch, capsys):
    _use_strong_pepper(monkeypatch)
    rc = bootstrap_main(["--plan", "pro", "--label", "audit-trail-check"])
    assert rc == EXIT_OK
    settings = get_settings()
    row = _last_audit_for_route(settings, "/tools/bootstrap_key")
    assert row is not None
    assert row.status_code == 200
    assert row.route == "/tools/bootstrap_key"
    # Hashes only — raw label must not appear in any column.
    for attr in ("request_sha256", "response_sha256", "route"):
        v = getattr(row, attr)
        assert "audit-trail-check" not in v


def test_minted_key_validates_against_auth(isolated_settings, monkeypatch, capsys):
    _use_strong_pepper(monkeypatch)
    rc = bootstrap_main(["--plan", "researcher", "--label", "auth-roundtrip"])
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    raw = re.search(r"api_key\s*:\s*(wvk_\S+)", out).group(1)

    # Drive the FastAPI auth dependency directly with the disclosed token.
    settings = get_settings()
    ctx: AuthContext = require_api_key(
        authorization=f"Bearer {raw}",
        settings=settings,
    )
    assert isinstance(ctx, AuthContext)
    assert ctx.plan == "researcher"
    assert ctx.tier == "paid"
