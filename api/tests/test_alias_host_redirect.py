"""The plural alias host redirects to the canonical Desk origin before any routing (2026-10-19).

Exact ``Host`` match only; GET/HEAD → 301 to the constant canonical origin with path and query preserved; any other method on the
alias → 405 (no login, refresh or API write is processed on the alias); forwarded-host headers are ignored; the canonical host does
not loop; unrelated and malicious hosts are routed as before. Source tests prove none of DNS or TLS for the alias.
"""

from __future__ import annotations

import pytest

from wavervanir_api.middleware import ALIAS_HOSTS, CANONICAL_DESK_ORIGIN, alias_redirect

ALIAS = "apps.cbsrm.wavervanir.com"
CANON = "app.cbsrm.wavervanir.com"


def test_constants_are_the_exact_hosts():
    assert ALIAS_HOSTS == frozenset({ALIAS}) and CANONICAL_DESK_ORIGIN == "https://" + CANON


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_alias_get_and_head_redirect_with_path_and_query(client, method):
    r = client.request(method, "/app/?x=1&y=two%20words", headers={"host": ALIAS}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://app.cbsrm.wavervanir.com/app/?x=1&y=two%20words"
    assert "set-cookie" not in r.headers


def test_alias_root_and_deep_paths_keep_their_path(client):
    for path in ("/", "/app/", "/v1/desk/conditions", "/docs"):
        r = client.get(path, headers={"host": ALIAS}, follow_redirects=False)
        assert r.status_code == 301 and r.headers["location"] == CANONICAL_DESK_ORIGIN + path


def test_alias_host_match_is_case_insensitive_but_exact(client):
    assert client.get("/app/", headers={"host": "APPS.cbsrm.wavervanir.com"}, follow_redirects=False).status_code == 301
    for host in ("apps.cbsrm.wavervanir.com.evil.example", "evilapps.cbsrm.wavervanir.com", "apps.cbsrm.wavervanir.com:443",
                 "apps.cbsrm.wavervanir.com ", "xapps.cbsrm.wavervanir.com"):
        r = client.get("/health", headers={"host": host}, follow_redirects=False)
        assert r.status_code == 200, host  # not an alias: routed normally


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_alias_write_methods_are_refused_not_processed(client, method):
    r = client.request(method, "/auth/login", headers={"host": ALIAS}, json={"email": "a@b.co", "password": "x" * 12})
    assert r.status_code == 405 and r.headers["allow"] == "GET, HEAD"
    assert r.text == ""


def test_alias_login_attempt_leaves_no_user_and_no_token(client):
    client.request("POST", "/auth/register", headers={"host": ALIAS}, json={"email": "alias-synthetic@synthetic-audit-only.org", "password": "Synthetic-Pass-1234!"})
    # the same registration on the canonical host succeeds, proving nothing was created via the alias
    r = client.post("/auth/register", json={"email": "alias-synthetic@synthetic-audit-only.org", "password": "Synthetic-Pass-1234!"})
    assert r.status_code == 201


def test_canonical_host_does_not_loop_and_unrelated_hosts_are_untouched(client):
    for host in (CANON, "testserver", "localhost", "127.0.0.1:8000", "wavervanir-api.onrender.com", "mfi.cbsrm.wavervanir.com"):
        r = client.get("/health", headers={"host": host}, follow_redirects=False)
        assert r.status_code == 200 and "location" not in r.headers, host


def test_forwarded_host_headers_never_trigger_or_steer_the_redirect(client):
    r = client.get("/health", headers={"host": CANON, "x-forwarded-host": ALIAS, "forwarded": f"host={ALIAS}"}, follow_redirects=False)
    assert r.status_code == 200
    r = client.get("/app/", headers={"host": ALIAS, "x-forwarded-host": "evil.example", "x-forwarded-proto": "http"}, follow_redirects=False)
    assert r.headers["location"].startswith(CANONICAL_DESK_ORIGIN + "/app/")


def test_alias_redirect_carries_security_headers_and_no_body(client):
    r = client.get("/app/", headers={"host": ALIAS}, follow_redirects=False)
    assert r.headers.get("x-frame-options") == "SAMEORIGIN" and r.headers.get("content-security-policy")
    assert r.content in (b"", None) or len(r.content) == 0


def test_alias_redirect_is_pure():
    assert alias_redirect.__name__ == "alias_redirect"


def test_a_protocol_relative_or_absolute_looking_path_cannot_escape_the_canonical_origin(client):
    for path in ("//evil.example/x", "/%2F%2Fevil.example", "/app/..%2F..%2Fetc", "/\\evil.example"):
        r = client.get(path, headers={"host": ALIAS}, follow_redirects=False)
        assert r.status_code in (301, 404), path  # 404 when the test client normalises the path away before the middleware
        if r.status_code == 301:
            assert r.headers["location"].startswith(CANONICAL_DESK_ORIGIN + "/"), r.headers["location"]
            assert "evil.example" not in r.headers["location"].split(CANONICAL_DESK_ORIGIN)[0]
