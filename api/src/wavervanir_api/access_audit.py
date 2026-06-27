"""Tamper-evident access ledger for the CBSRM Desk.

Every sign-in, refresh, and premium access is appended as one hash-linked row in
``access_events`` (see :class:`wavervanir_api.db.AccessEvent`). Each row's
``entry_hash`` is SHA-256 over::

    prev_hash || ts || subject || kind || route || payload_sha256

(each field followed by a 0x1e record separator). Re-hashing the chain
top-to-bottom must reproduce every stored hash; otherwise a row was altered,
deleted, or inserted out of band — :func:`verify_access_chain` reports the
break. Payloads are hashed via :func:`wavervanir_api.audit.sha256_of_obj`, never
stored raw, so the ledger holds no PII.

This is the same chain *design* as ``cbsrm.audit.chain``, but it persists on the
SQLModel engine so it is byte-identical on SQLite (dev) and Postgres (prod) —
``cbsrm.audit.chain`` is SQLite-only. Appends are serialized with a process
lock so concurrent requests can't read the same ``prev`` and fork the chain.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from sqlmodel import Session, select

from wavervanir_api.audit import sha256_of_obj
from wavervanir_api.config import Settings
from wavervanir_api.db import AccessEvent, get_engine


class AccessKind:
    """Canonical ``kind`` values for ledger rows."""

    REGISTERED = "REGISTERED"
    SIGNIN = "SIGNIN"
    SIGNIN_FAILED = "SIGNIN_FAILED"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"


_LOCK = Lock()
_SEP = b"\x1e"


def _canon_ts(dt: datetime) -> str:
    """UTC, second-precision ISO string — stable across SQLite/Postgres readback.

    We always normalise to UTC and format only to whole seconds, so the hashed
    timestamp is reproducible whether the backend returns an aware (Postgres) or
    naive (SQLite) datetime for the same stored instant.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _entry_hash(
    prev_hash: Optional[str],
    ts_iso: str,
    subject: str,
    kind: str,
    route: str,
    payload_sha256: str,
) -> str:
    h = hashlib.sha256()
    for part in (prev_hash or "", ts_iso, subject, kind, route, payload_sha256):
        h.update(part.encode("utf-8"))
        h.update(_SEP)
    return h.hexdigest()


def append_access_event(
    *,
    settings: Settings,
    subject: str,
    kind: str,
    route: str = "",
    payload: Any = None,
) -> int:
    """Append one hash-linked event. Returns the row id."""
    engine = get_engine(settings.db_url)
    payload_sha = sha256_of_obj(payload)
    with _LOCK:
        with Session(engine) as session:
            last = session.exec(
                select(AccessEvent).order_by(AccessEvent.id.desc())  # type: ignore[attr-defined]
            ).first()
            prev = last.entry_hash if last else None
            ts = datetime.now(timezone.utc).replace(microsecond=0)
            entry = _entry_hash(prev, _canon_ts(ts), subject, kind, route, payload_sha)
            row = AccessEvent(
                ts=ts,
                subject=subject,
                kind=kind,
                route=route,
                payload_sha256=payload_sha,
                prev_hash=prev,
                entry_hash=entry,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id or 0


def verify_access_chain(settings: Settings, start_id: int = 1) -> tuple[bool, list[int]]:
    """Re-hash rows from ``start_id`` and compare. Returns ``(ok, broken_ids)``."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(
            select(AccessEvent)
            .where(AccessEvent.id >= start_id)  # type: ignore[operator]
            .order_by(AccessEvent.id.asc())  # type: ignore[attr-defined]
        ).all()

    broken: list[int] = []
    prev_actual: Optional[str] = None
    first = True
    for r in rows:
        rid = r.id or 0
        if first:
            if start_id == 1 and r.prev_hash is not None:
                broken.append(rid)
            prev_actual = r.prev_hash
            first = False
        else:
            if r.prev_hash != prev_actual:
                broken.append(rid)
        h = _entry_hash(
            prev_actual, _canon_ts(r.ts), r.subject, r.kind, r.route, r.payload_sha256
        )
        if h != r.entry_hash and rid not in broken:
            broken.append(rid)
        prev_actual = r.entry_hash

    return (len(broken) == 0, broken)


def export_subject(
    settings: Settings, subject: str, *, limit: Optional[int] = None
) -> list[dict[str, Any]]:
    """Full (or most-recent ``limit``) chain for one subject, earliest-first."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(
            select(AccessEvent)
            .where(AccessEvent.subject == subject)
            .order_by(AccessEvent.id.asc())  # type: ignore[attr-defined]
        ).all()
    if limit is not None:
        rows = rows[-int(limit):]
    return [
        {
            "id": r.id,
            "ts": _canon_ts(r.ts),
            "subject": r.subject,
            "kind": r.kind,
            "route": r.route,
            "payload_sha256": r.payload_sha256,
            "prev_hash": r.prev_hash,
            "entry_hash": r.entry_hash,
        }
        for r in rows
    ]
