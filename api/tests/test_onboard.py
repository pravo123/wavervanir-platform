"""One-shot ``/onboard`` disclosure contract tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest

pytest.importorskip("stripe")

from sqlmodel import Session, select

from wavervanir_api.auth import hash_token
from wavervanir_api.config import get_settings
from wavervanir_api.db import ApiKey, OnboardSession, get_engine


def _sign(payload: bytes, secret: str, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    signed = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _checkout_event(session_id: str, plan: str = "researcher") -> dict:
    return {
        "id": f"evt_test_{session_id}",
        "object": "event",
        "api_version": "2024-04-10",
        "created": int(time.time()),
        "livemode": False,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "customer": f"cus_{session_id}",
                "subscription": f"sub_{session_id}",
                "metadata": {"plan": plan},
            }
        },
    }


def _mint_via_webhook(client, session_id: str, plan: str = "researcher") -> None:
    settings = get_settings()
    payload = json.dumps(_checkout_event(session_id, plan)).encode("utf-8")
    sig = _sign(payload, settings.stripe_webhook_secret)
    r = client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": sig})
    assert r.status_code == 200, r.text


def test_onboard_unknown_session_returns_404(client):
    r = client.get("/onboard", params={"session_id": "cs_test_unknown"})
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "unknown session_id"


def test_onboard_first_hit_returns_key(client):
    _mint_via_webhook(client, "cs_test_first_hit", plan="researcher")
    r = client.get("/onboard", params={"session_id": "cs_test_first_hit"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["api_key"].startswith("wvk_")
    assert body["plan"] == "researcher"
    assert body["disclosed_at"]
    assert "warning" in body


def test_onboard_second_hit_returns_410(client):
    _mint_via_webhook(client, "cs_test_dup", plan="pro")
    r1 = client.get("/onboard", params={"session_id": "cs_test_dup"})
    r2 = client.get("/onboard", params={"session_id": "cs_test_dup"})
    assert r1.status_code == 200
    assert r2.status_code == 410
    assert "already disclosed" in r2.json()["detail"]["error"]


def test_onboard_wipes_raw_token_from_row(client):
    _mint_via_webhook(client, "cs_test_wipe", plan="researcher")
    r = client.get("/onboard", params={"session_id": "cs_test_wipe"})
    assert r.status_code == 200
    settings = get_settings()
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(
            select(OnboardSession).where(OnboardSession.stripe_session_id == "cs_test_wipe")
        ).first()
        assert row is not None
        assert row.raw_token is None  # wiped on disclosure
        assert row.disclosed_at is not None


def test_disclosed_key_works_against_protected_endpoint(client):
    _mint_via_webhook(client, "cs_test_e2e", plan="researcher")
    raw = client.get("/onboard", params={"session_id": "cs_test_e2e"}).json()["api_key"]
    r = client.get(
        "/v1/cbsrm/macro-composite/windows",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200
    # And the stored row's hash should match.
    settings = get_settings()
    digest = hash_token(raw, settings.api_key_pepper)
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(select(ApiKey).where(ApiKey.key_hash == digest)).first()
        assert row is not None
        assert row.plan == "researcher"
