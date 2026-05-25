"""Rate-limit contract tests."""

from __future__ import annotations

import pytest

cbsrm = pytest.importorskip("cbsrm.reporting")

from wavervanir_api.auth import generate_raw_token, provision_key
from wavervanir_api.config import get_settings
from wavervanir_api.rate_limit import reset_counters


@pytest.fixture(autouse=True)
def _clear_rate_buckets():
    reset_counters()
    yield
    reset_counters()


def _make_key(tier: str) -> str:
    raw = generate_raw_token()
    provision_key(raw, tier=tier, stripe_customer_id="cus_test", settings=get_settings())
    return raw


def test_under_cap_succeeds(client):
    raw = _make_key("free")
    for _ in range(3):
        r = client.get(
            "/v1/cbsrm/macro-composite/windows",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200


def test_at_cap_returns_429(client):
    # Free tier limit is 5 in test config.
    raw = _make_key("free")
    for _ in range(5):
        r = client.get(
            "/v1/cbsrm/macro-composite/windows",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200
    r = client.get(
        "/v1/cbsrm/macro-composite/windows",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 429
    body = r.json()
    assert body["detail"]["error"] == "rate_limit_exceeded"
    assert body["detail"]["tier"] == "free"
    assert body["detail"]["limit_per_day"] == 5


def test_paid_tier_has_higher_cap(client):
    raw = _make_key("paid")
    for _ in range(10):  # higher than free limit of 5
        r = client.get(
            "/v1/cbsrm/macro-composite/windows",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200
