"""Shared pytest fixtures for wavervanir-api tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Give every test its own SQLite file + cleared settings cache."""
    db_file = tmp_path / "test.sqlite"
    monkeypatch.setenv("WAVERVANIR_DB_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("WAVERVANIR_API_KEY_PEPPER", "test-pepper")
    monkeypatch.setenv("WAVERVANIR_ENV", "test")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_only")
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_only")
    monkeypatch.setenv("WAVERVANIR_RATE_LIMIT_FREE", "5")
    monkeypatch.setenv("WAVERVANIR_RATE_LIMIT_PAID", "20")

    from wavervanir_api.config import get_settings
    from wavervanir_api import db as db_module

    get_settings.cache_clear()
    db_module.reset_engine()
    yield
    get_settings.cache_clear()
    db_module.reset_engine()


@pytest.fixture
def client(isolated_settings) -> Iterator[TestClient]:
    from wavervanir_api.app import create_app

    with TestClient(create_app()) as c:
        yield c
