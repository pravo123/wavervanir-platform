"""App-factory + health-endpoint smoke tests."""

from __future__ import annotations


def test_health_ok(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "wavervanir-api"
    assert "version" in body


def test_app_factory_is_pure() -> None:
    """create_app must be callable twice without error (idempotent table create)."""
    from wavervanir_api.app import create_app

    app1 = create_app()
    app2 = create_app()
    assert app1.title == app2.title == "wavervanir-api"
