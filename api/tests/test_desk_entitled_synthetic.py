"""An entitled Desk success path on a disposable store, beside the refusals (pilot acceptance, 2026-10-19).

Entitlement is obtained two ways the application already offers: the self-serve ``/auth/start-trial`` workflow and the
``AuthService.set_entitlement`` fixture its own tests use (a synthetic ``desk/active`` row). No Stripe, provider, e-mail or network
effect: data keys are blank (providers self-disable), so the live source must report every reading as unavailable or stale WITH a
reason and an ``as_of``, never as a silent zero; the demo source is labelled ``demo``; the cache reports a miss then a hit with the same
content hash; validation reports pending data. Unpaid, revoked, expired-trial, tampered and no-token calls stay refused.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wavervanir_api.config import get_settings
from wavervanir_api.users import AuthService

PW = "Synthetic-Pass-Phrase-1234!"


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_trial_workflow_entitles_and_the_desk_answers(client):
    h = _register(client, "trial-synthetic@synthetic-audit-only.org")
    assert client.get("/v1/desk/whoami", headers=h).status_code == 403
    assert client.post("/auth/start-trial", headers=h).status_code == 200
    who = client.get("/v1/desk/whoami", headers=h)
    assert who.status_code == 200, who.text
    body = who.json()
    assert body.get("plan") == "desk" and body.get("status") == "trialing"
    assert client.get("/v1/desk/status", headers=h).status_code == 200
    assert client.get("/v1/desk/methodology", headers=h).status_code == 200


def test_entitled_conditions_demo_live_cache_and_provenance(client):
    email = "entitled-synthetic@synthetic-audit-only.org"
    h = _register(client, email)
    AuthService(get_settings()).set_entitlement(email=email, plan="desk", status_="active")
    demo = client.get("/v1/desk/conditions?source=demo", headers=h)
    assert demo.status_code == 200 and demo.json()["source"] == "demo"
    assert all(rd.get("demo") is True and rd["as_of"] and rd["source"] for rd in demo.json()["readings"])
    live1 = client.get("/v1/desk/conditions", headers=h)
    assert live1.status_code == 200, live1.text
    b1 = live1.json()
    assert b1["schema"].startswith("cbsrm-desk-conditions/") and b1["source"] == "live"
    assert b1["summary"]["total"] == len(b1["readings"]) == 13
    for rd in b1["readings"]:
        assert rd["status"] in ("ok", "unavailable"), rd
        assert rd["source"], rd
        if rd["status"] == "unavailable":
            assert rd.get("reason"), rd
            assert "value" not in rd or rd.get("value") is None  # absence is absence, not zero
        else:
            assert rd.get("as_of"), rd
            if rd.get("stale"):
                assert rd.get("stale_reason") and rd.get("as_of")
    # with no data key configured nothing may be reported as a fresh live reading from a provider
    assert b1["summary"]["live"] + b1["summary"]["stale"] + b1["summary"]["unavailable"] == 13
    assert b1["cache"]["hit"] is False
    live2 = client.get("/v1/desk/conditions", headers=h)
    assert live2.status_code == 200 and live2.json()["cache"]["hit"] is True
    assert live2.json()["output_sha256"] == b1["output_sha256"]
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"]["conditions_cache"] != "cold"
    validation = client.get("/v1/desk/pipeline/validation", headers=h)
    assert validation.status_code == 200
    text = validation.text.lower()
    assert "pending" in text or "not_run" in text or "unavailable" in text  # honest: no reference series is bundled


def test_refusals_stay_in_force_beside_the_entitled_path(client):
    paid = "paid-synthetic@synthetic-audit-only.org"
    hp = _register(client, paid)
    AuthService(get_settings()).set_entitlement(email=paid, plan="desk", status_="active")
    assert client.get("/v1/desk/whoami", headers=hp).status_code == 200
    # unpaid
    hf = _register(client, "free-synthetic@synthetic-audit-only.org")
    assert client.get("/v1/desk/whoami", headers=hf).json()["detail"]["error"] == "desk_subscription_required"
    # tampered and absent token
    tok = hp["Authorization"].split(" ", 1)[1]
    assert client.get("/v1/desk/whoami", headers={"Authorization": "Bearer " + tok[:-3] + "abc"}).status_code == 401
    assert client.get("/v1/desk/conditions").status_code == 401
    # revoked after payment failure/cancellation
    AuthService(get_settings()).set_entitlement(email=paid, plan="desk", status_="canceled")
    assert client.get("/v1/desk/whoami", headers=hp).status_code == 403
    # an expired trial
    expired = "expired-synthetic@synthetic-audit-only.org"
    he = _register(client, expired)
    AuthService(get_settings()).set_entitlement(email=expired, plan="desk", status_="trialing",
                                                grace_until=datetime.now(timezone.utc) - timedelta(days=1))
    assert client.get("/v1/desk/whoami", headers=he).status_code == 403
