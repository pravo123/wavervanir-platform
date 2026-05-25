"""Stripe webhook — TEST MODE ONLY in MVP.

The endpoint:
  * verifies Stripe-Signature using the configured webhook secret
  * on ``checkout.session.completed`` → provisions a new API key for the
    customer's email/customer_id and returns it (for now, in the response;
    in production this would be emailed to the customer instead)
  * on ``customer.subscription.deleted`` → revokes all keys for that customer

In MVP we never accept live-mode events. Operator flips this manually after
all paths are validated against Stripe test-mode dashboard.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from wavervanir_api.auth import generate_raw_token, provision_key, revoke_key_by_stripe_customer
from wavervanir_api.config import Settings, get_settings

router = APIRouter()


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
    # ``construct_event`` returns a stripe.Event; convert to plain dict.
    if hasattr(event, "to_dict_recursive"):
        return event.to_dict_recursive()
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return json.loads(str(event))


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

    # MVP guardrail: refuse live-mode events.
    if event.get("livemode") is True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="live-mode events are disabled in MVP",
        )

    event_type = event.get("type", "")
    data_obj = (event.get("data") or {}).get("object", {}) or {}
    customer_id = data_obj.get("customer") or data_obj.get("customer_id")

    if event_type == "checkout.session.completed":
        tier = "paid"
        # Stripe metadata can specify tier explicitly.
        meta = data_obj.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("tier") in ("free", "paid"):
            tier = meta["tier"]
        raw = generate_raw_token()
        row = provision_key(
            raw_token=raw,
            tier=tier,
            stripe_customer_id=customer_id,
            settings=settings,
        )
        # NB: in production we email this token; for MVP we return it.
        return {
            "handled": event_type,
            "key_id": row.id,
            "tier": row.tier,
            "api_key": raw,
            "stripe_customer_id": customer_id,
        }

    if event_type in ("customer.subscription.deleted", "customer.deleted"):
        if not customer_id:
            return {"handled": event_type, "revoked": 0}
        revoked = revoke_key_by_stripe_customer(customer_id, settings)
        return {"handled": event_type, "revoked": revoked}

    # Unhandled events are accepted with 200 so Stripe doesn't retry forever.
    return {"handled": False, "type": event_type}
