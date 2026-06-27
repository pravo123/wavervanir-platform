"""Governed PipelineRecord for the Desk terminal — the "verify" promise.

The Desk pricing card promises **"Governed PipelineRecord + audit-chain access"**.
This module delivers the PipelineRecord half by wrapping cbsrm's *installed*
governed-report machinery (``cbsrm.reporting``) — no unpublished ``cbsrm.composer``
needed.

For a crisis window (2008Q4 / 2020Q1 / 2023Q1) it builds a **deterministic,
content-addressed, version-stamped** record of the CBSRM macro-composite pipeline:
the phase classification + driver features, the rendered governed report, and a
manifest carrying ``output_sha256`` / ``payload_sha256`` plus the cbsrm / registry
/ renderer versions. The record is *reproducible* — rebuilding the same window
yields the same hashes — which is exactly the governance guarantee the Desk sells.
The terminal can therefore pull a record and **verify** it reproduces, and every
access is written to the tamper-evident ledger (the "audit-chain access" half).
"""

from __future__ import annotations

from typing import Optional

REPORT_ID = "macro_composite"
RECORD_SCHEMA = "cbsrm-desk-pipeline-record/1.0.0"

# Human-readable context for each governed window (the crisis the snapshot captures).
_WINDOW_LABELS = {
    "2008Q4": "Global Financial Crisis — Lehman aftermath",
    "2020Q1": "COVID-19 crash — March 2020 liquidity shock",
    "2023Q1": "Regional-bank stress — SVB / Credit Suisse",
}


def _reporting():
    import cbsrm.reporting as R  # public, AST-boundary-allowed

    return R


def _cbsrm_version() -> str:
    import cbsrm

    return getattr(cbsrm, "__version__", "?")


def available_windows() -> list[str]:
    """The governed windows that can be reproduced, or ``[]`` if unavailable."""
    try:
        return list(_reporting().list_macro_composite_windows())
    except Exception:
        return []


def catalog() -> dict:
    """The governed-record catalog: which windows, which versions govern them."""
    R = _reporting()
    windows = available_windows()
    return {
        "schema": RECORD_SCHEMA,
        "product": "CBSRM Desk",
        "record_type": "governed_pipeline_record",
        "report_id": REPORT_ID,
        "windows": [
            {"window_id": w, "label": _WINDOW_LABELS.get(w, w)} for w in windows
        ],
        "versions": {
            "cbsrm": _cbsrm_version(),
            "manifest": getattr(R, "MANIFEST_VERSION", "?"),
            "registry": getattr(R, "REPORT_REGISTRY_VERSION", "?"),
            "renderer": getattr(R, "REPORT_RENDERER_VERSION", "?"),
        },
        "note": ("Each window builds a deterministic, content-addressed record. "
                 "Rebuild any record to verify it reproduces to the same SHA-256 — "
                 "that reproducibility, plus the audit-chained access, is the "
                 "governance guarantee."),
    }


def build_record(window_id: str, *, generated_at_utc: Optional[str] = None) -> dict:
    """Build the governed PipelineRecord for ``window_id``.

    Raises ``KeyError`` if the window is not a governed window. The returned
    ``manifest.hashes`` are reproducible: they hash the rendered report and the
    payload, not the wall-clock, so a rebuild yields identical hashes.
    """
    if window_id not in available_windows():
        raise KeyError(window_id)
    R = _reporting()
    report = R.build_macro_composite_report(window_id)
    markdown = R.render_macro_composite_markdown(report)
    manifest = R.build_report_manifest(
        report_id=REPORT_ID,
        output_text=markdown,
        output_format="markdown",
        window_id=window_id,
        payload=report,
        generated_at_utc=generated_at_utc,
    )
    phase = report.get("phase_classification", {}) or {}
    return {
        "schema": RECORD_SCHEMA,
        "window_id": window_id,
        "window_label": _WINDOW_LABELS.get(window_id, window_id),
        "title": report.get("title"),
        "phase": phase.get("phase"),
        "phase_score": phase.get("score"),
        "risk_posture": phase.get("risk_posture"),
        "dominant_drivers": phase.get("dominant_drivers", []),
        "phase_features": report.get("phase_features", {}),
        "research_notes": report.get("research_notes"),
        "disclaimer": report.get("disclaimer"),
        "markdown": markdown,
        "manifest": manifest,
        "generated_at_utc": generated_at_utc,
    }


def verify_record(
    window_id: str, expected_output_sha256: Optional[str] = None
) -> dict:
    """Rebuild ``window_id`` and check reproducibility.

    Always reports ``deterministic`` (a second independent rebuild matches the
    first). If ``expected_output_sha256`` is supplied (e.g. a hash the customer
    recorded earlier), ``reproduced`` is whether the current build matches it —
    proof the governed record has not drifted.
    """
    if window_id not in available_windows():
        raise KeyError(window_id)
    a = build_record(window_id)["manifest"]["hashes"]
    b = build_record(window_id)["manifest"]["hashes"]  # independent rebuild
    deterministic = (
        a["output_sha256"] == b["output_sha256"]
        and a["payload_sha256"] == b["payload_sha256"]
    )
    out = {
        "schema": RECORD_SCHEMA,
        "window_id": window_id,
        "output_sha256": a["output_sha256"],
        "payload_sha256": a["payload_sha256"],
        "deterministic": deterministic,
        "versions": {"cbsrm": _cbsrm_version()},
    }
    if expected_output_sha256 is not None:
        out["expected_output_sha256"] = expected_output_sha256
        out["reproduced"] = expected_output_sha256 == a["output_sha256"]
    else:
        out["reproduced"] = deterministic
    return out
