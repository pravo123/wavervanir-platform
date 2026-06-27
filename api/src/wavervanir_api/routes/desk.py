"""Premium CBSRM Desk routes — gated by an active Desk subscription.

Increment 1 ships the entitlement-gated namespace with identity, status, and a
self-service audit-trail export — proving the default-deny gate and the
tamper-evident access ledger end-to-end. The data-rich routes (live conditions,
any-quarter history, verifiable PipelineRecords) land in increment 3 on the same
``require_desk`` gate.
"""

from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, HTTPException, Query, status

from wavervanir_api import desk_analytics, desk_conditions
from wavervanir_api.access_audit import export_subject, verify_access_chain
from wavervanir_api.config import Settings, get_settings
from wavervanir_api.users import UserContext, require_desk

router = APIRouter()


def _utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/desk/whoami")
def whoami(ctx: UserContext = Depends(require_desk)) -> dict:
    """Identity of the authenticated, entitled Desk user."""
    return {
        "user_id": ctx.user_id,
        "email": ctx.email,
        "name": ctx.name,
        "plan": ctx.plan,
        "status": ctx.status,
        "terminal_access": True,
    }


@router.get("/desk/status")
def desk_status(ctx: UserContext = Depends(require_desk)) -> dict:
    """Entitlement summary for the Desk terminal shell."""
    return {
        "product": "CBSRM Desk",
        "version": 1,
        "plan": ctx.plan,
        "status": ctx.status,
        "entitled": True,
    }


@router.get("/desk/methodology")
def methodology(ctx: UserContext = Depends(require_desk)) -> dict:
    """The eight-lens systemic-risk methodology catalog (static, no network)."""
    return desk_conditions.methodology()


@router.get("/desk/conditions")
def conditions(
    source: str = Query("live", pattern="^(live|demo)$"),
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Current systemic-risk readings across CBSRM's lenses.

    ``source=live`` (default) reads current public data via the cbsrm CLI plus
    the financialdata.net equity-volatility lens, each degrading to
    ``status="unavailable"`` if its source can't be reached. ``source=demo``
    returns deterministic synthetic readings for offline preview.
    """
    return desk_conditions.build(
        source=source, generated_at_utc=_utc_stamp(), settings=settings
    )


@router.get("/desk/lens/{lens_id}")
def lens_analytics(
    lens_id: str,
    source: str = Query("live", pattern="^(live|demo)$"),
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """BI analytics for one lens: time series + summary stats + regime bands.

    ``source=live`` pulls real history (VIX via financialdata.net, ECB/FRED via
    the cbsrm indicators); ``source=demo`` returns a deterministic synthetic
    series so the drill-down works fully offline.
    """
    if lens_id not in desk_analytics.LENS_META:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown_lens", "lens_id": lens_id},
        )
    return desk_analytics.lens_analytics(settings, lens_id, source=source)


@router.get("/desk/audit/export")
def audit_export(
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """The caller's own access trail + a live tamper-evidence check of the ledger.

    ``chain_ok`` re-hashes the whole ledger and is ``True`` only if no row was
    altered, deleted, or inserted out of band — the "every access is auditable"
    property institutions buy.
    """
    subject = f"user:{ctx.user_id}"
    events = export_subject(settings, subject)
    ok, broken = verify_access_chain(settings)
    return {
        "subject": subject,
        "count": len(events),
        "events": events,
        "chain_ok": ok,
        "broken_ids": broken,
    }
