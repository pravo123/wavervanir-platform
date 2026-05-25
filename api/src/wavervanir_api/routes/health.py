"""Public unauthenticated health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from wavervanir_api import __version__

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "wavervanir-api", "version": __version__}
