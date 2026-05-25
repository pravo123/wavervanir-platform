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
    # Suffix a unique id so multiple events of the same type in a single
    # test don't collide on the inner ``data.object.id`` defaults.
    return {
        "id": f"evt_test_{event_type}_{int(time.time()*1000)}",
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
        id="cs_test_session_111",
        customer="cus_test_123",
        subscription="sub_test_111",
        metadata={"plan": "researcher"},
    )
    payload = json.dumps(ev).encode("utf-8")
    sig = _sign(payload, settings.stripe_webhook_secret)
    r = client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": sig})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["handled"] == "checkout.session.completed"
    assert body["idempotent"] is False
    assert body["plan"] == "researcher"
    assert body["tier"] == "paid"
    assert body["stripe_customer_id"] == "cus_test_123"
    assert body["stripe_subscription_id"] == "sub_test_111"
    assert body["stripe_session_id"] == "cs_test_session_111"
    # Raw key is NOT returned in webhook response — only via /onboard.
    assert "api_key" not in body

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(select(ApiKey)).all()
        assert len(rows) == 1
        assert rows[0].stripe_customer_id == "cus_test_123"
        assert rows[0].stripe_subscription_id == "sub_test_111"
        assert rows[0].plan == "researcher"
        assert rows[0].status == "active"


def test_checkout_completed_is_idempotent_on_replay(client):
    settings = get_settings()
    ev = _event(
        "checkout.session.completed",
        id="cs_test_session_dup",
        customer="cus_dup",
        subscription="sub_dup",
        metadata={"plan": "pro"},
    )
    payload = json.dumps(ev).encode("utf-8")
    sig = _sign(payload, settings.stripe_webhook_secret)

    r1 = client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": sig})
    r2 = client.post(
        "/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": _sign(payload, settings.stripe_webhook_secret)},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["idempotent"] is False
    assert r2.json()["idempotent"] is True
    assert r1.json()["api_key_id"] == r2.json()["api_key_id"]

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(select(ApiKey)).all()
        assert len(rows) == 1


def test_subscription_updated_changes_plan(client):
    settings = get_settings()
    # First, mint via checkout.
    ev_open = _event(
        "checkout.session.completed",
        id="cs_upgrade_target",
        customer="cus_upgrade",
        subscription="sub_upgrade",
        metadata={"plan": "researcher"},
    )
    payload = json.dumps(ev_open).encode("utf-8")
    client.post(
        "/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": _sign(payload, settings.stripe_webhook_secret)},
    )

    # Now Stripe sends subscription.updated with plan=pro.
    ev_upd = _event(
        "customer.subscription.updated",
        id="sub_upgrade",
        customer="cus_upgrade",
        metadata={"plan": "pro"},
    )
    p_upd = json.dumps(ev_upd).encode("utf-8")
    r = client.post(
        "/stripe/webhook",
        content=p_upd,
        headers={"Stripe-Signature": _sign(p_upd, settings.stripe_webhook_secret)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["handled"] == "customer.subscription.updated"
    assert body["plan"] == "pro"
    assert body["updated_rows"] == 1

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(
            select(ApiKey).where(ApiKey.stripe_subscription_id == "sub_upgrade")
        ).first()
        assert row is not None
        assert row.plan == "pro"


def test_payment_failed_sets_grace_window(client):
    settings = get_settings()
    ev_open = _event(
        "checkout.session.completed",
        id="cs_dunning",
        customer="cus_dunning",
        subscription="sub_dunning",
        metadata={"plan": "researcher"},
    )
    p_open = json.dumps(ev_open).encode("utf-8")
    client.post(
        "/stripe/webhook",
        content=p_open,
        headers={"Stripe-Signature": _sign(p_open, settings.stripe_webhook_secret)},
    )

    ev_fail = _event(
        "invoice.payment_failed",
        id="in_dunning",
        customer="cus_dunning",
        subscription="sub_dunning",
    )
    p_fail = json.dumps(ev_fail).encode("utf-8")
    r = client.post(
        "/stripe/webhook",
        content=p_fail,
        headers={"Stripe-Signature": _sign(p_fail, settings.stripe_webhook_secret)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["handled"] == "invoice.payment_failed"
    assert body["updated_rows"] == 1
    assert "grace_until" in body

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(
            select(ApiKey).where(ApiKey.stripe_subscription_id == "sub_dunning")
        ).first()
        assert row is not None
        assert row.grace_until is not None
        # Key stays active during grace.
        assert row.status == "active"


def test_subscription_created_is_no_op(client):
    settings = get_settings()
    ev = _event(
        "customer.subscription.created",
        id="sub_created_x",
        customer="cus_created_x",
        metadata={"plan": "researcher"},
    )
    payload = json.dumps(ev).encode("utf-8")
    r = client.post(
        "/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": _sign(payload, settings.stripe_webhook_secret)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["handled"] == "customer.subscription.created"
    assert "no_op_reason" in body


def test_subscription_deleted_revokes_keys(client):
    settings = get_settings()
    # First, provision via checkout-completed.
    ev_open = _event(
        "checkout.session.completed",
        id="cs_to_revoke",
        customer="cus_to_revoke",
        subscription="sub_to_revoke",
        metadata={"plan": "researcher"},
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
