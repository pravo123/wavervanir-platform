"""``/health/ready`` — the outage-triage surface.

When the database is down every writeable route returns an opaque
``{"detail": "internal server error"}``, so readiness is the only thing that
says *why* from outside the host. It has to name the cause without handing an
unauthenticated caller the database host, IP or role name.
"""

from __future__ import annotations

import sqlalchemy

from wavervanir_api.routes.health import _failure_reason


def _operational_error(server_message: str) -> sqlalchemy.exc.OperationalError:
    """An OperationalError shaped like the ones psycopg2 raises."""
    return sqlalchemy.exc.OperationalError(
        "SELECT 1", {}, Exception(server_message)
    )


def test_ready_when_the_database_answers(client):
    body = client.get("/health/ready").json()

    assert body["status"] == "ready"
    assert body["checks"]["db"] == "ok"


def test_connection_exhaustion_is_named(client, monkeypatch):
    """The failure mode that took the Desk down: no free connection slots."""
    from wavervanir_api.routes import health as health_route

    def boom(_url):
        raise _operational_error(
            'connection to server at "dpg-abc.oregon-postgres.render.com" '
            '(10.0.0.7), port 5432 failed: FATAL:  too many connections for '
            'role "wavervanir"'
        )

    monkeypatch.setattr(health_route, "get_engine", boom, raising=False)
    monkeypatch.setattr("wavervanir_api.db.get_engine", boom)

    response = client.get("/health/ready")
    body = response.json()

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert "too many connections" in body["checks"]["db"]


def test_reason_never_leaks_host_ip_or_role():
    reason = _failure_reason(
        _operational_error(
            'connection to server at "dpg-abc.oregon-postgres.render.com" '
            '(10.0.0.7), port 5432 failed: FATAL:  password authentication '
            'failed for user "wavervanir"'
        )
    )

    assert reason == "error: OperationalError (authentication failed)"
    for secret in ("dpg-abc", "oregon-postgres", "10.0.0.7", "wavervanir", "5432"):
        assert secret not in reason


def test_unrecognised_failure_falls_back_to_the_exception_type():
    reason = _failure_reason(_operational_error("something nobody predicted"))

    assert reason == "error: OperationalError"
    assert "something nobody predicted" not in reason
