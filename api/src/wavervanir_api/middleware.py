"""Security-headers, request-logging, and error-handling for the API + SPA.

Installed once by the app factory. Three concerns, one place:

* **Security headers** on every response (API and the same-origin terminal SPA).
  The CSP mirrors the public site's ``site/_headers``: a same-origin app that
  uses inline script/style, ``data:`` images, and talks only to its own
  ``/v1/desk/*`` API. Stripe checkout is a top-level link (navigation), not an
  XHR, so ``connect-src 'self'`` does not block it. HSTS is gated behind an env
  flag so local ``http`` dev is not broken.
* **Request logging** — one structured line per request (health chatter muted).
* **Unhandled-exception handler** — logs the stack, returns a sanitised 500 (no
  traceback to the client) *with* the security headers, and optionally fires a
  best-effort alert webhook.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from wavervanir_api.logging_config import get_logger

_log = get_logger("http")

# Mirrors site/_headers on the public site. 'unsafe-inline' is required because
# the SPA (like the public site) ships inline <script>/<style>.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'"
)

# Paths whose per-request access log is muted (health probes hit constantly).
_QUIET_PATHS = frozenset({"/health"})


def security_headers(settings: Any) -> dict[str, str]:
    """The security headers to stamp on every response for this deployment."""
    if not getattr(settings, "security_headers_enabled", True):
        return {}
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": _CSP,
    }
    if getattr(settings, "hsts_enabled", False):
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


def _maybe_alert(settings: Any, request: Request, exc: BaseException) -> None:
    """Best-effort POST to an ops webhook on a 5xx. Never raises. Default-off."""
    url = getattr(settings, "alert_webhook_url", "") or ""
    if not url:
        return
    try:  # httpx is already a dep (upstream fetches); guard anyway.
        import httpx

        httpx.post(
            url,
            json={
                "service": "wavervanir-api",
                "level": "error",
                "path": request.url.path,
                "method": request.method,
                "error": f"{type(exc).__name__}: {exc}",
            },
            timeout=3.0,
        )
    except Exception:  # noqa: BLE001 — alerting must never break the response
        _log.warning("alert_webhook_failed", extra={"kv": {"url": url}})


def install_security_and_logging(app: FastAPI, settings: Any) -> None:
    """Wire the header/logging middleware and the unhandled-exception handler."""
    headers = security_headers(settings)

    @app.middleware("http")
    async def _headers_and_logging(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)  # handled errors already became responses
        for key, value in headers.items():
            response.headers.setdefault(key, value)
        if request.url.path not in _QUIET_PATHS:
            _log.info(
                "request",
                extra={"kv": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": int((time.perf_counter() - start) * 1000),
                }},
            )
        return response

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # A generic Exception handler runs at the outermost layer, so its
        # response does NOT pass back through the middleware above — stamp the
        # headers here too so even a 500 is hardened.
        _log.error(
            "unhandled_exception",
            extra={"kv": {"method": request.method, "path": request.url.path}},
            exc_info=exc,
        )
        _maybe_alert(settings, request, exc)
        resp = JSONResponse(status_code=500, content={"detail": "internal server error"})
        for key, value in headers.items():
            resp.headers.setdefault(key, value)
        return resp
