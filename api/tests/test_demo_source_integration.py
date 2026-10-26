"""Regression and authenticated HTTP journeys; synthetic fixtures, no provider I/O."""
from datetime import date, timedelta
from urllib.parse import quote

import pytest

from wavervanir_api import desk_conditions, desk_lenses, desk_riskdesk
from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService


@pytest.fixture
def entitled(client):
    email = "demo-v5@synthetic.example"
    response = client.post("/auth/register", json={"email": email, "password": "synthetic-test-only-473"})
    assert response.status_code == 201, response.text
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_demo_http_grid_drilldown_all_groups(client, entitled, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("synthetic demo attempted a provider call")
    monkeypatch.setattr(desk_riskdesk, "_safe_fetch", refuse)
    monkeypatch.setattr(desk_riskdesk, "_fetch_bars_any", refuse)
    for group in desk_riskdesk.available_groups():
        response = client.get("/v1/desk/riskdesk", params={"group": group["id"], "source": "demo"}, headers=entitled)
        assert response.status_code == 200, response.text
        grid = response.json()
        assert grid["summary"]["live"] == 0
        assert grid["summary"]["demo"] == len(grid["rows"])
        for row in grid["rows"]:
            detail = client.get("/v1/desk/riskdesk/symbol/" + quote(row["symbol"], safe=""), params={"source": "demo"}, headers=entitled)
            assert detail.status_code == 200, detail.text
            doc = detail.json()
            assert doc["demo"] is True and doc["source"] == "demo"
            assert doc["price"] == row["spot"] and doc["as_of"] == row["as_of"]
            assert doc["chart"]["bars"] and doc["var_table"]
            again = client.get("/v1/desk/riskdesk/symbol/" + quote(row["symbol"], safe=""), params={"source": "demo"}, headers=entitled)
            assert again.json()["output_sha256"] == doc["output_sha256"]


def test_conditions_demo_is_never_counted_live(client, entitled):
    response = client.get("/v1/desk/conditions?source=demo", headers=entitled)
    assert response.status_code == 200
    assert response.json()["summary"] == {"total": 13, "available": 13, "demo": 13, "live": 0, "stale": 0, "unavailable": 0}


def test_detail_auth_and_bad_source(client, entitled):
    path = "/v1/desk/riskdesk/symbol/SPY?source=demo"
    assert client.get(path).status_code == 401
    assert client.get("/v1/desk/riskdesk/symbol/SPY?source=invalid", headers=entitled).status_code == 422
    assert client.get("/v1/desk/riskdesk/symbol/UNKNOWN_SYNTHETIC?source=demo", headers=entitled).status_code == 404


def option_feed(monkeypatch, *, dated=True, malformed=False):
    from wavervanir_api.providers import financialdata
    observed = (date.today() - timedelta(days=3)).isoformat()
    expiry = (date.today() + timedelta(days=60)).isoformat()
    rows = [{"expiration_date": expiry, "put_or_call": side, "strike_price": strike, "contract_name": name}
            for side, strike, name in [("Put", 95, "P1"), ("Put", 90, "P2"), ("Call", 105, "C1"), ("Call", 110, "C2")]]
    if malformed:
        rows = [{"expiration_date": "not-a-date"}, {"expiration_date": "2000-01-01"}]
    def feed(settings, endpoint, *, params, client):
        if endpoint == "stock-prices":
            return [{"close": 100, "date": observed}]
        if endpoint == "option-chain":
            return rows
        if endpoint == "option-greeks":
            record = {"vega": 2 if params["identifier"].startswith("P") else 1}
            if dated:
                record["date"] = (date.today() - timedelta(days=1)).isoformat()
            return [record]
        raise AssertionError(endpoint)
    monkeypatch.setattr(financialdata, "get_json", feed)
    return observed, expiry


def test_expiration_is_not_observation_date(monkeypatch):
    observed, expiry = option_feed(monkeypatch)
    result = desk_lenses._options_reading_live(None)
    assert result["as_of"] == observed and result["as_of"] != expiry
    assert result["option_expiration"] == expiry
    assert result["value"] == 2.0


def test_undated_greeks_do_not_invent_observation_date(monkeypatch):
    _, expiry = option_feed(monkeypatch, dated=False)
    result = desk_lenses._options_reading_live(None)
    assert result["as_of"] is None
    assert result["observation_date_status"] == "unavailable"
    assert result["option_expiration"] == expiry


def test_invalid_or_expired_contract_has_clear_absence(monkeypatch):
    option_feed(monkeypatch, malformed=True)
    result = desk_lenses._options_reading_live(None)
    assert result["status"] == "unavailable" and "expiration" in result["reason"]


def test_observation_date_rejects_future_and_expiration_only():
    assert desk_lenses._observation_date({"date": "2099-01-01", "expiration_date": "2099-03-01"}) is None
    assert desk_lenses._observation_date({"expiration_date": "2099-03-01"}) is None


def test_cached_reading_counts_and_provenance(monkeypatch):
    previous = desk_conditions.build(source="demo")["readings"]
    failed = [{**r, "status": "unavailable", "reason": "synthetic provider timeout"} for r in previous]
    result = desk_conditions._apply_last_good(failed, previous)
    assert all(r["stale"] and r["as_of"] == old["as_of"] for r, old in zip(result, previous))
