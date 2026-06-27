"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from wavervanir_api import __version__
from wavervanir_api.config import get_settings
from wavervanir_api.db import get_engine
from wavervanir_api.routes import admin as admin_routes
from wavervanir_api.routes import broker_snapshot as broker_snapshot_routes
from wavervanir_api.routes import cbsrm as cbsrm_routes
from wavervanir_api.routes import data as data_routes
from wavervanir_api.routes import desk as desk_routes
from wavervanir_api.routes import health as health_routes
from wavervanir_api.routes import onboard as onboard_routes
from wavervanir_api.routes import stripe as stripe_routes
from wavervanir_api.routes import users as users_routes
from wavervanir_api.routes import waitlist as waitlist_routes


def create_app() -> FastAPI:
    """Construct and return the FastAPI app.

    The factory is pure — no network I/O, no filesystem writes besides
    initialising the SQLite tables on first call (idempotent).
    """
    settings = get_settings()
    # Initialise tables eagerly so the first request doesn't pay the cost.
    get_engine(settings.db_url)

    app = FastAPI(
        title="wavervanir-api",
        version=__version__,
        description=(
            "Hosted CBSRM research API by WaverVanir International. "
            "Public methodology, authenticated SaaS surface."
        ),
        docs_url="/docs",
        redoc_url=None,
    )

    app.include_router(health_routes.router, tags=["meta"])
    app.include_router(cbsrm_routes.router, prefix="/v1/cbsrm", tags=["cbsrm"])
    app.include_router(waitlist_routes.router, prefix="/v1", tags=["waitlist"])
    app.include_router(stripe_routes.router, prefix="/stripe", tags=["stripe"])
    app.include_router(onboard_routes.router, tags=["onboard"])
    app.include_router(data_routes.router, prefix="/v1", tags=["data"])
    app.include_router(broker_snapshot_routes.router, prefix="/v1", tags=["broker-snapshot"])
    # CBSRM Desk paid terminal: user sign-in + entitlement-gated routes.
    app.include_router(users_routes.router, tags=["auth"])
    app.include_router(desk_routes.router, prefix="/v1", tags=["desk"])
    app.include_router(admin_routes.router, prefix="/v1", tags=["admin"])

    # The authenticated terminal SPA (same-origin, so no CORS needed). Served at
    # /app; calls /auth/* and /v1/desk/* with the bearer JWT it holds in memory.
    web_dir = Path(__file__).resolve().parent / "web"
    if web_dir.is_dir():
        app.mount("/app", StaticFiles(directory=str(web_dir), html=True), name="terminal")

    return app
