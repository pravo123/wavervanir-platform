"""Conditions snapshot cache — TTL, hit/miss, force-refresh (offline via demo)."""

from __future__ import annotations

import datetime as dt
import json

from sqlmodel import Session, select

from wavervanir_api import desk_conditions
from wavervanir_api.config import get_settings
from wavervanir_api.db import SnapshotCache, get_engine


def test_cache_roundtrip(isolated_settings):
    s = get_settings()
    desk_conditions._cache_set(s, "conditions:test", "live", json.dumps({"x": 1}))
    got = desk_conditions._cache_get(s, "conditions:test")
    assert got is not None
    assert json.loads(got[1]) == {"x": 1}


def test_build_cached_miss_then_hit(isolated_settings):
    s = get_settings()
    a = desk_conditions.build_cached(source="demo", settings=s)
    assert a["cache"]["hit"] is False
    b = desk_conditions.build_cached(source="demo", settings=s)
    assert b["cache"]["hit"] is True
    assert b["cache"]["age_s"] >= 0
    assert a["output_sha256"] == b["output_sha256"]


def test_build_cached_force_recomputes(isolated_settings):
    s = get_settings()
    desk_conditions.build_cached(source="demo", settings=s)
    c = desk_conditions.build_cached(source="demo", settings=s, force=True)
    assert c["cache"]["hit"] is False


def test_build_cached_respects_ttl(isolated_settings):
    s = get_settings()
    desk_conditions.build_cached(source="demo", settings=s)
    # Backdate the cached row well beyond the default TTL.
    engine = get_engine(s.db_url)
    with Session(engine) as sess:
        row = sess.exec(
            select(SnapshotCache).where(SnapshotCache.cache_key == "conditions:demo")
        ).first()
        row.generated_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)
        sess.add(row)
        sess.commit()
    stale = desk_conditions.build_cached(source="demo", settings=s)  # 5h old > 1h TTL
    assert stale["cache"]["hit"] is False
