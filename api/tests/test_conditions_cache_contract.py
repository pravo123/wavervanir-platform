"""A rolling deployment must not trust the former reading/counter contract."""
import datetime as dt
import json

from wavervanir_api import desk_conditions as conditions


def cached(payload):
    return dt.datetime.now(dt.timezone.utc), json.dumps(payload)


def test_old_demo_cache_cannot_continue_counting_synthetic_as_live(monkeypatch):
    previous = {"source": "demo", "readings": [], "summary": {"live": 13}}
    monkeypatch.setattr(conditions, "_cache_get", lambda *_: cached(previous))
    calls = []
    def rebuild(**kwargs):
        calls.append(kwargs)
        return {"source": "demo", "readings": [], "summary": {"live": 0, "demo": 13}}
    monkeypatch.setattr(conditions, "build", rebuild)
    written = []
    monkeypatch.setattr(conditions, "_cache_set", lambda *args: written.append(args))
    result = conditions.build_cached(source="demo", settings=None)
    assert result["summary"] == {"live": 0, "demo": 13}
    assert result["cache"]["hit"] is False
    assert result["cache_contract"] == conditions.CACHE_CONTRACT
    assert calls[0]["prev_readings"] is None
    assert json.loads(written[0][-1])["cache_contract"] == conditions.CACHE_CONTRACT


def test_old_future_option_date_does_not_seed_last_good(monkeypatch):
    previous = {"source": "live", "readings": [{"id": "OPTIONS", "status": "ok", "as_of": "2099-01-01"}]}
    monkeypatch.setattr(conditions, "_cache_get", lambda *_: cached(previous))
    calls = []
    def rebuild(**kwargs):
        calls.append(kwargs)
        return {"readings": [{"id": "OPTIONS", "status": "unavailable"}]}
    monkeypatch.setattr(conditions, "build", rebuild)
    monkeypatch.setattr(conditions, "_cache_set", lambda *_: None)
    result = conditions.build_cached(source="live", settings=None, force=True)
    assert calls[0]["prev_readings"] is None
    assert result["readings"][0]["status"] == "unavailable"


def test_readiness_does_not_report_legacy_cache_as_current(monkeypatch):
    monkeypatch.setattr(conditions, "_cache_get", lambda *_: cached({"summary": {"live": 13}}))
    assert conditions.cache_peek(None) is None


def test_current_cache_is_reused_without_provider_rebuild(monkeypatch):
    payload = {"cache_contract": conditions.CACHE_CONTRACT, "readings": [], "summary": {"live": 0, "demo": 13}}
    monkeypatch.setattr(conditions, "_cache_get", lambda *_: cached(payload))
    def refuse(**_):
        raise AssertionError("current cache should not rebuild")
    monkeypatch.setattr(conditions, "build", refuse)
    result = conditions.build_cached(source="demo", settings=None)
    assert result["cache"]["hit"] is True
    assert conditions.cache_peek(None, source="demo")["live"] == 0


def test_last_good_requires_a_real_nonfuture_observation_date():
    missing = [{"id": key, "status": "unavailable", "reason": "synthetic provider timeout"} for key in ["past", "future", "undated"]]
    previous = [
        {"id": "past", "status": "ok", "as_of": "2020-01-01", "value": 1},
        {"id": "future", "status": "ok", "as_of": "2099-01-01", "value": 2},
        {"id": "undated", "status": "ok", "value": 3},
    ]
    result = conditions._apply_last_good(missing, previous)
    assert result[0]["stale"] and result[0]["as_of"] == "2020-01-01"
    assert result[1]["status"] == result[2]["status"] == "unavailable"
