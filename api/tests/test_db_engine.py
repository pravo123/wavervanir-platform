"""Engine caching, pooling, and schema-init behaviour.

The bug these cover: the engine cache compared ``str(engine.url)`` against the
URL it was asked for. SQLAlchemy renders a URL's password as ``***``, so for
Postgres the two never matched and every call built a fresh engine, re-ran
``create_all``, and abandoned a connection pool — exhausting the server's
connection slots and turning every database-backed route into a 500. SQLite
URLs carry no password, which is why the tests and local dev never saw it.
"""

from __future__ import annotations

import pytest
import sqlalchemy
from sqlalchemy.engine import make_url

from wavervanir_api import db as db_module
from wavervanir_api.config import get_settings


PG_URL = "postgresql://wavervanir:s3cr3tpw@db.example.invalid:5432/wavervanir"


@pytest.fixture
def count_engine_builds(monkeypatch: pytest.MonkeyPatch):
    """Count how many engines ``get_engine`` actually constructs."""
    built: list[str] = []
    real = db_module.create_engine

    def spy(url, **kwargs):
        built.append(str(url))
        return real(url, **kwargs)

    monkeypatch.setattr(db_module, "create_engine", spy)
    return built


def test_repeat_calls_reuse_one_engine_for_sqlite(count_engine_builds):
    db_module.reset_engine()
    url = get_settings().db_url

    engines = [db_module.get_engine(url) for _ in range(5)]

    assert len(count_engine_builds) == 1
    assert all(e is engines[0] for e in engines)


def test_repeat_calls_reuse_one_engine_for_password_bearing_url(
    count_engine_builds, monkeypatch: pytest.MonkeyPatch
):
    """The regression: a Postgres URL must be cached, not rebuilt every call.

    ``create_all`` is stubbed out because the host is unreachable by design —
    the assertion is about the cache, not about connecting.
    """
    monkeypatch.setattr(db_module.SQLModel.metadata, "create_all", lambda *a, **k: None)
    db_module.reset_engine()

    engines = [db_module.get_engine(PG_URL) for _ in range(5)]

    assert len(count_engine_builds) == 1, (
        f"engine rebuilt {len(count_engine_builds)}x for one URL — "
        "the cache key is masking the password"
    )
    assert all(e is engines[0] for e in engines)


def test_masked_url_is_not_used_as_the_cache_key():
    """Guards the specific trap: str(url) hides the password."""
    assert str(make_url(PG_URL)) != PG_URL
    assert "***" in str(make_url(PG_URL))


def test_switching_url_disposes_the_previous_engine(monkeypatch: pytest.MonkeyPatch):
    disposed: list[object] = []
    real_dispose = sqlalchemy.engine.Engine.dispose

    def spy(self, *a, **k):
        disposed.append(self)
        return real_dispose(self, *a, **k)

    monkeypatch.setattr(sqlalchemy.engine.Engine, "dispose", spy)

    db_module.reset_engine()
    first = db_module.get_engine("sqlite://")
    db_module.get_engine(get_settings().db_url)

    assert first in disposed


def test_postgres_engine_is_pooled_defensively(monkeypatch: pytest.MonkeyPatch):
    """Managed Postgres drops idle connections and caps the slots per role."""
    monkeypatch.setattr(db_module.SQLModel.metadata, "create_all", lambda *a, **k: None)
    db_module.reset_engine()

    engine = db_module.get_engine(PG_URL)

    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 300
    assert engine.pool.size() == 5


def test_legacy_postgres_scheme_is_normalised(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db_module.SQLModel.metadata, "create_all", lambda *a, **k: None)
    db_module.reset_engine()

    engine = db_module.get_engine(PG_URL.replace("postgresql://", "postgres://", 1))

    assert engine.url.drivername.startswith("postgresql")


def test_failed_schema_init_is_retried_not_cached(monkeypatch: pytest.MonkeyPatch):
    """A create_all that fails must not leave the engine marked as ready."""
    db_module.reset_engine()
    calls: list[int] = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise sqlalchemy.exc.OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(db_module.SQLModel.metadata, "create_all", flaky)
    url = get_settings().db_url

    with pytest.raises(sqlalchemy.exc.OperationalError):
        db_module.get_engine(url)

    db_module.get_engine(url)  # must retry, not silently serve a schema-less engine
    assert len(calls) == 2
