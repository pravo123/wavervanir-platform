"""Stripe webhook tests.

We construct test-mode signatures locally using the same secret the app reads.
No real HTTP calls to Stripe.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest

stripe = pytest.importorskip("stripe")

from sqlmodel import Session, select

from wavervanir_api.config import get_settings
from wavervanir_api.db import ApiKey, get_engine


def _sign(payload: bytes, secret: str, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    signed = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _event(event_type: str, **data: Any) -> dict:
    return {
        "id": "evt_test_" + event_type,
        "object": "event",
        "api_version": "2024-04-10",
        "created": int(time.time()),
        "livemode": False,
        "type": event_type,
        "data": {"object": data},
    }


def test_missing_signature_returns_400(client):
    r = client.post("/stripe/webhook", content=b"{}")
    assert r.status_code == 400


def test_bad_signature_returns_400(client):
    payload = json.dumps(_event("checkout.session.completed")).encode("utf-8")
    r = client.post(
        "/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400


def test_live_mode_event_rejected(client):
    settings = get_settings()
    ev = _event("checkout.session.completed", customer="cus_x")
    ev["livemode"] = True
    payload = json.dumps(ev).encode("utf-8")
    sig = _sign(payload, settings.stripe_webhook_secret)
    r = client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": sig})
    assert r.status_code == 403


def test_checkout_completed_provisions_key(client):
    settings = get_settings()
    ev = _event(
        "checkout.session.completed",
        customer="cus_test_123",
        metadata={"tier": "paid"},
    )
    payload = json.dumps(ev).encode("utf-8")
    sig = _sign(payload, settings.stripe_webhook_secret)
    r = client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": sig})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["handled"] == "checkout.session.completed"
    assert body["tier"] == "paid"
    assert body["stripe_customer_id"] == "cus_test_123"
    assert body["api_key"].startswith("wvk_")

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(select(ApiKey)).all()
        assert len(rows) == 1
        assert rows[0].stripe_customer_id == "cus_test_123"
        assert rows[0].status == "active"


def test_subscription_deleted_revokes_keys(client):
    settings = get_settings()
    # First, provision via checkout-completed.
    ev_open = _event(
        "checkout.session.completed",
        customer="cus_to_revoke",
        metadata={"tier": "paid"},
    )
    p_open = json.dumps(ev_open).encode("utf-8")
    client.post(
        "/stripe/webhook",
        content=p_open,
        headers={"Stripe-Signature": _sign(p_open, settings.stripe_webhook_secret)},
    )

    ev_del = _event("customer.subscription.deleted", customer="cus_to_revoke")
    p_del = json.dumps(ev_del).encode("utf-8")
    r = client.post(
        "/stripe/webhook",
        content=p_del,
        headers={"Stripe-Signature": _sign(p_del, settings.stripe_webhook_secret)},
    )
    assert r.status_code == 200
    assert r.json()["revoked"] == 1

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(
            select(ApiKey).where(ApiKey.stripe_customer_id == "cus_to_revoke")
        ).first()
        assert row is not None
        assert row.status == "revoked"


def test_unhandled_event_returns_200(client):
    settings = get_settings()
    ev = _event("invoice.paid", customer="cus_x")
    payload = json.dumps(ev).encode("utf-8")
    sig = _sign(payload, settings.stripe_webhook_secret)
    r = client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": sig})
    assert r.status_code == 200
    assert r.json()["handled"] is False
