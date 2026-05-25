"""Macro-composite route tests.

These tests skip if ``cbsrm`` is not installed in the dev environment — the
CI matrix installs it from the pinned v0.9.0 tag.
"""

from __future__ import annotations

import pytest

cbsrm = pytest.importorskip("cbsrm.reporting")

from wavervanir_api.auth import generate_raw_token, provision_key
from wavervanir_api.config import get_settings


def _make_key(tier: str = "paid") -> str:
    raw = generate_raw_token()
    provision_key(raw, tier=tier, stripe_customer_id="cus_test", settings=get_settings())
    return raw


def test_windows_endpoint_lists_supported(client):
    raw = _make_key()
    r = client.get(
        "/v1/cbsrm/macro-composite/windows",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["windows"], list)
    assert len(body["windows"]) > 0


def test_windows_endpoint_requires_auth(client):
    r = client.get("/v1/cbsrm/macro-composite/windows")
    assert r.status_code == 401


def test_macro_composite_happy_path(client):
    raw = _make_key()
    supported = cbsrm.list_macro_composite_windows()
    window = supported[0]
    r = client.post(
        "/v1/cbsrm/macro-composite",
        json={"window_id": window},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_id"] == window
    assert isinstance(body["report"], dict)
    assert isinstance(body["rendered_markdown"], str)
    assert body["rendered_markdown"].strip(), "markdown render must be non-empty"


def test_macro_composite_unknown_window_404(client):
    raw = _make_key()
    r = client.post(
        "/v1/cbsrm/macro-composite",
        json={"window_id": "9999Q9"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["detail"]["error"] == "unknown window_id"
    assert isinstance(body["detail"]["supported"], list)


def test_macro_composite_requires_auth(client):
    r = client.post("/v1/cbsrm/macro-composite", json={"window_id": "2008Q4"})
    assert r.status_code == 401
