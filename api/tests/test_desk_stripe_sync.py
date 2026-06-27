"""Stripe webhook -> CBSRM Desk user entitlement sync (increment 2).

Drives the handler functions directly with crafted event dicts (signature
verification is exercised separately) and asserts the ``users`` row tracks the
subscription lifecycle: checkout -> active, payment_failed -> grace (access
retained), subscription.deleted -> revoked.
"""

from __future__ import annotations

from sqlmodel import Session, select

from wavervanir_api.config import get_settings
from wavervanir_api.db import User, get_engine
from wavervanir_api.routes.stripe import (
    _handle_checkout_completed,
    _handle_payment_failed,
    _handle_subscription_deleted,
    _handle_subscription_updated,
)
from wavervanir_api.users import AuthService, UserContext


def _make_user(email="buyer@fund.example"):
    user = AuthService(get_settings()).register(email=email, password="strong-pass-123")
    return user


def _reload(user_id):
    engine = get_engine(get_settings().db_url)
    with Session(engine) as session:
        return session.get(User, user_id)


def _checkout_event(user_id, *, plan="desk", session_id="cs_1", cust="cus_1", sub="sub_1"):
    return {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id,
            "customer": cust,
            "subscription": sub,
            "client_reference_id": str(user_id),
            "metadata": {"plan": plan},
        }},
    }


def test_checkout_entitles_user_to_desk(isolated_settings):
    user = _make_user()
    assert user.status == "inactive" and user.plan == "free"

    res = _handle_checkout_completed(_checkout_event(user.id), get_settings())
    assert res["user_entitled_id"] == user.id

    u = _reload(user.id)
    assert u.plan == "desk"
    assert u.status == "active"
    assert u.stripe_customer_id == "cus_1"
    assert u.stripe_subscription_id == "sub_1"
    assert UserContext.from_user(u).has_terminal is True


def test_checkout_is_idempotent_on_replay(isolated_settings):
    user = _make_user()
    _handle_checkout_completed(_checkout_event(user.id), get_settings())
    # Replay the exact same session id — must not error and entitlement holds.
    res = _handle_checkout_completed(_checkout_event(user.id), get_settings())
    assert res.get("idempotent") is True
    assert res["user_entitled_id"] == user.id
    assert _reload(user.id).status == "active"


def test_checkout_with_unknown_reference_is_noop(isolated_settings):
    res = _handle_checkout_completed(_checkout_event(99999), get_settings())
    assert res["user_entitled_id"] is None  # no such user; nothing entitled


def test_payment_failed_sets_grace_but_keeps_access(isolated_settings):
    user = _make_user()
    _handle_checkout_completed(_checkout_event(user.id), get_settings())

    event = {"type": "invoice.payment_failed",
             "data": {"object": {"subscription": "sub_1"}}}
    res = _handle_payment_failed(event, get_settings())
    assert res["users_grace"] == 1

    u = _reload(user.id)
    assert u.status == "grace"
    assert u.grace_until is not None
    # Grace retains terminal access (dunning window).
    assert UserContext.from_user(u).has_terminal is True


def test_subscription_deleted_revokes_user(isolated_settings):
    user = _make_user()
    _handle_checkout_completed(_checkout_event(user.id), get_settings())

    event = {"type": "customer.subscription.deleted",
             "data": {"object": {"customer": "cus_1"}}}
    res = _handle_subscription_deleted(event, get_settings())
    assert res["users_revoked"] == 1

    u = _reload(user.id)
    assert u.status == "revoked"
    assert UserContext.from_user(u).has_terminal is False


def test_subscription_updated_syncs_plan(isolated_settings):
    user = _make_user()
    _handle_checkout_completed(_checkout_event(user.id), get_settings())

    event = {"type": "customer.subscription.updated",
             "data": {"object": {"id": "sub_1", "metadata": {"plan": "institutional"}}}}
    res = _handle_subscription_updated(event, get_settings())
    assert res["users_synced"] == 1

    u = _reload(user.id)
    assert u.plan == "institutional"
    assert u.status == "active"
