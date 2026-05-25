"""Waitlist endpoint tests."""

from __future__ import annotations


def test_waitlist_accepts_valid_submission(client):
    r = client.post(
        "/v1/waitlist",
        json={"email": "alice@example.com", "tier_interest": "institutional"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["deduplicated"] is False
    assert body["id"] > 0


def test_waitlist_dedups_email(client):
    payload = {"email": "bob@example.com", "tier_interest": "pro"}
    r1 = client.post("/v1/waitlist", json=payload)
    r2 = client.post("/v1/waitlist", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["deduplicated"] is True


def test_waitlist_rejects_malformed_email(client):
    r = client.post(
        "/v1/waitlist",
        json={"email": "not-an-email", "tier_interest": "researcher"},
    )
    assert r.status_code == 422


def test_waitlist_rejects_unknown_tier(client):
    r = client.post(
        "/v1/waitlist",
        json={"email": "carol@example.com", "tier_interest": "hedge_fund"},
    )
    assert r.status_code == 422
    assert "unknown tier_interest" in r.text
