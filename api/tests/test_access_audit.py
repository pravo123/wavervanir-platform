"""Tamper-evidence contract for the hash-linked access ledger."""

from __future__ import annotations

from sqlmodel import Session, select

from wavervanir_api.access_audit import (
    AccessKind,
    append_access_event,
    export_subject,
    verify_access_chain,
)
from wavervanir_api.config import get_settings
from wavervanir_api.db import AccessEvent, get_engine


def _seed(n: int = 3):
    settings = get_settings()
    ids = []
    for i in range(n):
        ids.append(
            append_access_event(
                settings=settings,
                subject=f"user:{i % 2}",
                kind=AccessKind.SIGNIN,
                route="/auth/login",
                payload={"i": i, "email": "alice@example.com"},
            )
        )
    return settings, ids


def test_append_then_verify_ok(isolated_settings):
    settings, ids = _seed(4)
    assert ids == sorted(ids)
    ok, broken = verify_access_chain(settings)
    assert ok is True
    assert broken == []


def test_rows_are_hash_linked(isolated_settings):
    settings, _ = _seed(3)
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(select(AccessEvent).order_by(AccessEvent.id.asc())).all()
    assert rows[0].prev_hash is None
    for prev, cur in zip(rows, rows[1:]):
        assert cur.prev_hash == prev.entry_hash
        assert len(cur.entry_hash) == 64


def test_payload_is_hashed_not_stored_raw(isolated_settings):
    settings, _ = _seed(1)
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(select(AccessEvent)).first()
    assert row is not None
    assert len(row.payload_sha256) == 64
    for attr in ("subject", "kind", "route", "payload_sha256", "entry_hash"):
        assert "alice@example.com" not in getattr(row, attr)


def test_tamper_is_detected(isolated_settings):
    settings, ids = _seed(3)
    engine = get_engine(settings.db_url)
    # Mutate a hashed field on the middle row out of band.
    with Session(engine) as session:
        row = session.get(AccessEvent, ids[1])
        row.kind = AccessKind.ACCESS_GRANTED  # was SIGNIN
        session.add(row)
        session.commit()
    ok, broken = verify_access_chain(settings)
    assert ok is False
    assert ids[1] in broken


def test_deletion_is_detected(isolated_settings):
    settings, ids = _seed(3)
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.get(AccessEvent, ids[1])
        session.delete(row)
        session.commit()
    ok, broken = verify_access_chain(settings)
    assert ok is False
    # The row after the hole no longer links to its recorded predecessor.
    assert ids[2] in broken


def test_export_subject_filters(isolated_settings):
    settings, _ = _seed(4)  # subjects user:0 and user:1
    rows0 = export_subject(settings, "user:0")
    assert rows0
    assert all(r["subject"] == "user:0" for r in rows0)
