"""The bare root redirects to the terminal SPA."""

from __future__ import annotations


def test_root_redirects_to_app(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307, 308)
    assert r.headers["location"] == "/app/"


def test_root_follows_to_terminal(client):
    r = client.get("/", follow_redirects=True)
    assert r.status_code == 200
    assert "CBSRM Desk" in r.text
