"""Stripe webhook — TEST MODE ONLY in MVP.

Handled events:
  * ``checkout.session.completed``     → mint key, stash raw token in
    ``onboard_sessions`` keyed by Stripe ``session_id``. Idempotent on replay.
  * ``customer.subscription.created``  → no-op (mint already happened on checkout)
  * ``customer.subscription.updated``  → if ``metadata.plan`` changed, update
    ``ApiKey.plan`` on every key tied to the subscription.
  * ``customer.subscription.deleted``  → revoke all keys for the customer.
  * ``invoice.payment_failed``         → mark a 3-day grace window; key stays
    active during grace (Stripe dunning handles the rest).

``livemode=true`` events are refused (403). Real Stripe Products are NOT
required for tests; the test suite signs fake payloads with the configured
webhook secret.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session, select

from wavervanir_api.auth import (
    generate_raw_token,
    mark_grace_by_subscription,
    provision_key,
    revoke_key_by_stripe_customer,
    update_key_plan_by_subscription,
)
from wavervanir_api.config import Settings, get_settings
from wavervanir_api.db import OnboardSession, get_engine
from wavervanir_api.plans import is_known_plan

router = APIRouter()


# Grace window applied on ``invoice.payment_failed``.
DEFAULT_GRACE_DAYS = 3


def _verify_signature(payload: bytes, sig_header: str, secret: str) -> dict[str, Any]:
    """Verify Stripe-Signature header. Returns the parsed event dict on success."""
    try:
        import stripe  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"stripe sdk unavailable: {exc!r}",
        )
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid stripe signature: {exc!r}",
        )
    if hasattr(event, "to_dict_recursive"):
        return event.to_dict_recursive()
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return json.loads(str(event))


def _existing_onboard(settings: Settings, stripe_session_id: str) -> OnboardSession | None:
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        return session.exec(
            select(OnboardSession).where(OnboardSession.stripe_session_id == stripe_session_id)
        ).first()


def _handle_checkout_completed(event: dict, settings: Settings) -> dict:
    data_obj = (event.get("data") or {}).get("object", {}) or {}
    customer_id = data_obj.get("customer") or data_obj.get("customer_id")
    subscription_id = data_obj.get("subscription")
    session_id = data_obj.get("id") or event.get("id", "")
    meta = data_obj.get("metadata") or {}

    plan = meta.get("plan") if isinstance(meta, dict) else None
    if not plan or not is_known_plan(plan):
        plan = "researcher"
    tier = "paid" if plan != "free" else "free"

    # Idempotency: replay on same Stripe session id must NOT mint a new key.
    existing = _existing_onboard(settings, session_id) if session_id else None
    if existing is not None:
        return {
            "handled": "checkout.session.completed",
            "idempotent": True,
            "api_key_id": existing.api_key_id,
            "plan": existing.plan,
            "stripe_session_id": session_id,
        }

    raw = generate_raw_token()
    row = provision_key(
        raw_token=raw,
        tier=tier,
        stripe_customer_id=customer_id,
        settings=settings,
        plan=plan,
        stripe_subscription_id=subscription_id,
    )

    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        onboard = OnboardSession(
            stripe_session_id=session_id or f"_synth_{row.id}",
            api_key_id=row.id or 0,
            raw_token=raw,
            plan=plan,
        )
        session.add(onboard)
        session.commit()
        session.refresh(onboard)

    return {
        "handled": "checkout.session.completed",
        "idempotent": False,
        "api_key_id": row.id,
        "plan": row.plan,
        "tier": row.tier,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_session_id": session_id,
    }


def _handle_subscription_updated(event: dict, settings: Settings) -> dict:
    data_obj = (event.get("data") or {}).get("object", {}) or {}
    subscription_id = data_obj.get("id") or data_obj.get("subscription")
    meta = data_obj.get("metadata") or {}
    plan = meta.get("plan") if isinstance(meta, dict) else None
    if not subscription_id or not plan or not is_known_plan(plan):
        return {
            "handled": "customer.subscription.updated",
            "no_op_reason": "missing subscription id or unknown plan",
        }
    updated = update_key_plan_by_subscription(
        stripe_subscription_id=subscription_id,
        plan=plan,
        settings=settings,
    )
    return {
        "handled": "customer.subscription.updated",
        "updated_rows": updated,
        "plan": plan,
        "stripe_subscription_id": subscription_id,
    }


def _handle_subscription_deleted(event: dict, settings: Settings) -> dict:
    data_obj = (event.get("data") or {}).get("object", {}) or {}
    customer_id = data_obj.get("customer") or data_obj.get("customer_id")
    if not customer_id:
        return {"handled": event.get("type", ""), "revoked": 0}
    revoked = revoke_key_by_stripe_customer(customer_id, settings)
    return {"handled": event.get("type", ""), "revoked": revoked}


def _handle_payment_failed(event: dict, settings: Settings) -> dict:
    data_obj = (event.get("data") or {}).get("object", {}) or {}
    subscription_id = data_obj.get("subscription") or data_obj.get("id")
    if not subscription_id:
        return {"handled": "invoice.payment_failed", "no_op_reason": "no subscription"}
    deadline = datetime.now(timezone.utc) + timedelta(days=DEFAULT_GRACE_DAYS)
    updated = mark_grace_by_subscription(
        stripe_subscription_id=subscription_id,
        grace_until=deadline,
        settings=settings,
    )
    return {
        "handled": "invoice.payment_failed",
        "updated_rows": updated,
        "grace_until": deadline.isoformat(),
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="stripe webhook secret not configured",
        )
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing Stripe-Signature header",
        )

    payload = await request.body()
    event = _verify_signature(payload, stripe_signature, settings.stripe_webhook_secret)

    if event.get("livemode") is True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="live-mode events are disabled in MVP",
        )

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(event, settings)

    if event_type == "customer.subscription.created":
        return {"handled": event_type, "no_op_reason": "mint occurs on checkout.session.completed"}

    if event_type == "customer.subscription.updated":
        return _handle_subscription_updated(event, settings)

    if event_type in ("customer.subscription.deleted", "customer.deleted"):
        return _handle_subscription_deleted(event, settings)

    if event_type == "invoice.payment_failed":
        return _handle_payment_failed(event, settings)

    return {"handled": False, "type": event_type}
