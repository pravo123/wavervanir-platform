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


# ── last-good fallback (the "unavailable card" fix) ─────────────────────────

def test_apply_last_good_backfills_unavailable():
    prev = [{"id": "ECB-CISS-US", "status": "ok", "value": 0.011, "as_of": "2026-06-25",
             "label": "ECB CISS — United States", "source": "ECB SDMX", "unit": "index 0-1"}]
    cur = [{"id": "ECB-CISS-US", "status": "unavailable", "reason": "upstream timeout",
            "label": "ECB CISS — United States", "source": "ECB SDMX", "unit": "index 0-1"}]
    out = desk_conditions._apply_last_good(cur, prev)
    assert out[0]["status"] == "ok"          # card no longer blanks
    assert out[0]["value"] == 0.011          # last good value carried forward
    assert out[0]["as_of"] == "2026-06-25"   # original date preserved (age visible)
    assert out[0]["stale"] is True
    assert out[0]["stale_reason"] == "upstream timeout"


def test_apply_last_good_noop_when_current_ok():
    prev = [{"id": "X", "status": "ok", "value": 1}]
    cur = [{"id": "X", "status": "ok", "value": 2}]
    out = desk_conditions._apply_last_good(cur, prev)
    assert out[0]["value"] == 2 and not out[0].get("stale")  # fresh value wins, not stale


def test_apply_last_good_leaves_unavailable_when_no_prior_good():
    cur = [{"id": "X", "status": "unavailable", "reason": "r"}]
    assert desk_conditions._apply_last_good(cur, None)[0]["status"] == "unavailable"
    prev_bad = [{"id": "X", "status": "unavailable"}]
    assert desk_conditions._apply_last_good(cur, prev_bad)[0]["status"] == "unavailable"


def test_build_cached_feeds_prior_snapshot_as_fallback(isolated_settings, monkeypatch):
    """build_cached must hand the prior cached readings to build() as prev_readings,
    even on a forced recompute, so a transient miss can be backfilled."""
    s = get_settings()
    desk_conditions._cache_set(
        s, "conditions:live", "live",
        json.dumps({"readings": [{"id": "ECB-CISS-US", "status": "ok", "value": 0.011}]}),
    )
    captured: dict = {}

    def fake_build(**kw):
        captured.update(kw)
        return {"readings": [], "summary": {}, "output_sha256": "x"}

    monkeypatch.setattr(desk_conditions, "build", fake_build)
    desk_conditions.build_cached(source="live", settings=s, force=True)
    assert captured["prev_readings"] == [{"id": "ECB-CISS-US", "status": "ok", "value": 0.011}]
