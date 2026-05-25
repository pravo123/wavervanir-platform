"""Per-request audit chain.

Each authenticated request writes exactly one row to ``audit_log`` capturing:

    (key_id, route, request_sha256, response_sha256, status_code, latency_ms, ts)

Raw payloads are never persisted — only SHA-256 hashes. This is the same
provenance pattern used in CBSRM/VolanX internally, lifted to the public surface.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping

from sqlmodel import Session

from wavervanir_api.config import Settings
from wavervanir_api.db import AuditLog, get_engine


def sha256_of_obj(obj: Any) -> str:
    """Deterministic SHA-256 over any JSON-serialisable object."""
    if obj is None:
        return hashlib.sha256(b"").hexdigest()
    if isinstance(obj, (bytes, bytearray)):
        return hashlib.sha256(bytes(obj)).hexdigest()
    if isinstance(obj, str):
        return hashlib.sha256(obj.encode("utf-8")).hexdigest()
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_audit(
    *,
    settings: Settings,
    key_id: int | None,
    route: str,
    request_obj: Any,
    response_obj: Any,
    status_code: int,
    latency_ms: int,
) -> int:
    """Insert one audit row. Returns the row id."""
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = AuditLog(
            key_id=key_id,
            route=route,
            request_sha256=sha256_of_obj(request_obj),
            response_sha256=sha256_of_obj(response_obj),
            status_code=int(status_code),
            latency_ms=int(latency_ms),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id or 0


class _Timer:
    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_exc):
        self.ms = int((time.perf_counter() - self._t0) * 1000)


def timer() -> _Timer:
    """Context manager exposing .ms after exit."""
    return _Timer()
