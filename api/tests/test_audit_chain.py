"""Audit-chain invariants.

We confirm:
  1. record_audit writes one row per call
  2. hashes are deterministic
  3. raw payloads never appear on the row
  4. an authenticated CBSRM call produces an audit row
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

cbsrm = pytest.importorskip("cbsrm.reporting")

from wavervanir_api.audit import record_audit, sha256_of_obj
from wavervanir_api.auth import generate_raw_token, provision_key
from wavervanir_api.config import get_settings
from wavervanir_api.db import AuditLog, get_engine


def test_sha256_of_obj_deterministic():
    h1 = sha256_of_obj({"window_id": "2008Q4", "x": 1})
    h2 = sha256_of_obj({"x": 1, "window_id": "2008Q4"})  # key reorder
    assert h1 == h2


def test_record_audit_persists_hashes_only(isolated_settings):
    settings = get_settings()
    request_obj = {"secret_field": "alice@example.com"}
    response_obj = {"some_pii": "carol@example.com"}
    row_id = record_audit(
        settings=settings,
        key_id=None,
        route="/test",
        request_obj=request_obj,
        response_obj=response_obj,
        status_code=200,
        latency_ms=12,
    )
    assert row_id > 0
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        row = session.exec(select(AuditLog)).first()
        assert row is not None
        assert row.request_sha256 == sha256_of_obj(request_obj)
        assert row.response_sha256 == sha256_of_obj(response_obj)
        # Belt-and-braces: raw strings must not appear anywhere on the row.
        for attr in ("request_sha256", "response_sha256", "route"):
            v = getattr(row, attr)
            assert "alice@example.com" not in v
            assert "carol@example.com" not in v


def test_macro_composite_writes_audit_row(client, isolated_settings):
    raw = generate_raw_token()
    provision_key(raw, tier="paid", stripe_customer_id="cus_test", settings=get_settings())

    supported = cbsrm.list_macro_composite_windows()
    r = client.post(
        "/v1/cbsrm/macro-composite",
        json={"window_id": supported[0]},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200

    settings = get_settings()
    engine = get_engine(settings.db_url)
    with Session(engine) as session:
        rows = session.exec(select(AuditLog)).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.route == "/v1/cbsrm/macro-composite"
        assert row.status_code == 200
        assert row.latency_ms >= 0
        assert len(row.request_sha256) == 64
        assert len(row.response_sha256) == 64
