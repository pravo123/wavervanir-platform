"""Premium CBSRM Desk routes — gated by an active Desk subscription.

Every route is behind the default-deny ``require_desk`` gate and writes to the
tamper-evident access ledger. The namespace covers identity/status, the live
systemic-risk conditions + per-lens BI analytics, the portfolio risk analyzer,
the self-service audit-trail export, and the **governed PipelineRecords**
(deterministic, content-addressed, reproducible records of the CBSRM
macro-composite pipeline for crisis windows) — the literal "Governed
PipelineRecord + audit-chain access" the Desk tier sells.
"""

from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from wavervanir_api import (
    desk_analytics,
    desk_conditions,
    desk_pipeline,
    desk_riskdesk,
    desk_validation,
)
from wavervanir_api.access_audit import (
    AccessKind,
    append_access_event,
    export_subject,
    verify_access_chain,
)
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
    fresh: bool = Query(False, description="bypass the cache and recompute live"),
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Current systemic-risk readings across CBSRM's lenses.

    ``source=live`` (default) is served from a short-TTL cache so the slow
    multi-upstream build is paid once, not on every load (``?fresh=true`` forces
    a recompute). ``source=demo`` returns deterministic synthetic readings.
    """
    if source == "demo":
        return desk_conditions.build(source="demo", generated_at_utc=_utc_stamp(), settings=settings)
    return desk_conditions.build_cached(
        source="live", settings=settings, force=fresh, generated_at_utc=_utc_stamp()
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


@router.get("/desk/riskdesk")
def risk_desk(
    group: str = Query("us-benchmarks"),
    source: str = Query("live", pattern="^(live|demo)$"),
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Quant Cockpit watchlist grid for ``group`` (any-symbol via the route below).

    Native CBSRM view (no VolanX import) of a global cross-asset watchlist — US &
    world equity indices, FX majors, commodities, mega-caps, crypto — each with
    level, 1d/1m return, 20-day realised vol, 1-day 95% VaR, beta to the S&P,
    drawdown, and trend, plus a composite posture. ``source=demo`` is deterministic.
    """
    return desk_riskdesk.build(group=group, source=source, settings=settings,
                               generated_at_utc=_utc_stamp())


@router.get("/desk/riskdesk/symbol/{symbol}")
def risk_desk_symbol(
    symbol: str,
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Institutional cockpit read for ANY symbol the feed supports.

    Returns multi-horizon returns, the risk-desk panel (Sharpe/Sortino/ann &
    EWMA vol/beta/max-drawdown), a horizon VaR/CVaR table, beta-driven macro
    stress scenarios, a quant read, and reproducible SHA-256 provenance.
    """
    profile = desk_riskdesk.risk_profile(settings, symbol, generated_at_utc=_utc_stamp())
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "symbol_unavailable", "symbol": symbol.upper(),
                    "hint": "try an index (^GSPC), FX pair (EURUSD), commodity (GC), "
                            "crypto (BTCUSD), or a US stock/ETF ticker"},
        )
    return profile


# ── Governed PipelineRecord ─────────────────────────────────────────────────
# Delivers the pricing promise "Governed PipelineRecord + audit-chain access":
# deterministic, content-addressed, version-stamped records of the CBSRM
# macro-composite pipeline for crisis windows. Rebuild any record to verify it
# reproduces to the same SHA-256 — that, plus the audit-chained access, is the
# governance guarantee. (catalog/verify are declared before /{window_id} so the
# static paths win over the parameterised route.)

@router.get("/desk/pipeline/catalog")
def pipeline_catalog(ctx: UserContext = Depends(require_desk)) -> dict:
    """Which governed windows can be reproduced, and the versions that govern them."""
    return desk_pipeline.catalog()


@router.post("/desk/pipeline/verify")
async def pipeline_verify(
    request: Request,
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Rebuild a governed record and check it reproduces (optionally vs an expected hash).

    The verification result — including the manifest's ``output_sha256`` — is
    written to the caller's tamper-evident access ledger, so the governed record
    and the audit chain are linked end to end.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    window_id = (body or {}).get("window_id", "")
    expected = (body or {}).get("expected_output_sha256")
    try:
        result = desk_pipeline.verify_record(window_id, expected)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown_window", "window_id": window_id,
                    "supported": desk_pipeline.available_windows()},
        )
    append_access_event(
        settings=settings,
        subject=f"user:{ctx.user_id}",
        kind=AccessKind.ACCESS_GRANTED,
        route=f"desk/pipeline/verify:{window_id}",
        payload={"output_sha256": result["output_sha256"],
                 "reproduced": result["reproduced"]},
    )
    return result


@router.get("/desk/pipeline/systemic")
def pipeline_systemic(
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Live systemic capital-shortfall panel: SRISK Σ + per-firm + ΔCoVaR across
    the major-US-bank panel (NYU V-Lab / Adrian-Brunnermeier engines in cbsrm.risk).

    A live read on current balance sheets (not a point-in-time crisis vintage), so
    it is not part of the governed record hash — it carries its own timestamp.
    """
    return desk_pipeline.systemic_panel(settings, generated_at_utc=_utc_stamp())


@router.get("/desk/pipeline/validation")
def pipeline_validation(
    ctx: UserContext = Depends(require_desk),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Model Validation package (SR 26-2): the MRM binder for the systemic models.

    Documented inventory / conceptual-soundness / assumptions / dependency graph /
    attestation, plus COMPUTED evidence — an SRISK parameter-sensitivity sweep
    (k × crisis threshold, rank stability) and a Monte-Carlo convergence check on
    LRMES. Benchmarking + backtest declare an honest 'pending data connection'
    state rather than a fabricated score. Content-addressed (SHA-256).
    """
    return desk_validation.validation_package(settings, generated_at_utc=_utc_stamp())


@router.get("/desk/pipeline/{window_id}")
def pipeline_record(
    window_id: str,
    ctx: UserContext = Depends(require_desk),
) -> dict:
    """The governed PipelineRecord for one crisis window — report + manifest +
    deterministic crisis dossier (system-stress channels, DebtRank, cross-crisis)."""
    try:
        return desk_pipeline.build_record(window_id, generated_at_utc=_utc_stamp())
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown_window", "window_id": window_id,
                    "supported": desk_pipeline.available_windows()},
        )


# A sanitized sample portfolio (no account numbers/tokens) for the terminal's
# "Load sample" button — positions only, signed market values.
_SAMPLE_SNAPSHOT = {
    "schema_version": "1.0",
    "snapshot_ts": "2026-06-26T20:00:00Z",
    "account_alias": "desk-demo",
    "base_currency": "USD",
    "positions": [
        {"symbol": "AAPL", "asset_class": "equity", "quantity": 1200, "mark_price": 238.0,
         "market_value": 285600.0, "unrealized_pnl": 18400.0},
        {"symbol": "MSFT", "asset_class": "equity", "quantity": 600, "mark_price": 437.0,
         "market_value": 262200.0, "unrealized_pnl": -5200.0},
        {"symbol": "SPY", "asset_class": "etf", "quantity": -400, "mark_price": 735.0,
         "market_value": -294000.0, "unrealized_pnl": 3100.0},
        {"symbol": "NVDA 280C", "asset_class": "option", "quantity": 50, "mark_price": 12.5,
         "market_value": 62500.0, "unrealized_pnl": -8200.0},
        {"symbol": "BTC", "asset_class": "crypto", "quantity": 3.5, "mark_price": 111000.0,
         "market_value": 388500.0, "unrealized_pnl": 42000.0},
        {"symbol": "EURUSD", "asset_class": "fx", "quantity": 500000, "mark_price": 1.08,
         "market_value": 540000.0, "unrealized_pnl": -1500.0},
    ],
}


@router.get("/desk/portfolio/sample")
def portfolio_sample(ctx: UserContext = Depends(require_desk)) -> dict:
    """A sanitized example snapshot for the terminal's portfolio analyzer."""
    return _SAMPLE_SNAPSHOT


@router.post("/desk/portfolio")
async def portfolio_risk(
    request: Request,
    ctx: UserContext = Depends(require_desk),
) -> dict:
    """Portfolio risk summary from a sanitized broker snapshot.

    Reuses the file-only ``broker_snapshot`` engine: strict schema validation +
    a sanitization scrub (rejects any leaked account numbers / tokens) +
    aggregate exposure / concentration / per-asset-class metrics. No broker
    connectivity; positions in, risk out.
    """
    from wavervanir_api.providers.broker_snapshot import (
        SnapshotValidationError,
        risk_summary,
        scrub_check,
        validate_snapshot,
    )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid JSON body")
    try:
        snap = validate_snapshot(payload)
    except SnapshotValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "snapshot_validation_failed", "reason": str(exc),
                    "scrub_violations": scrub_check(payload)},
        )
    return risk_summary(snap).model_dump(mode="json")


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
