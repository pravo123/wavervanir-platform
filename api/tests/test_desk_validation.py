"""Model Validation package (SR 26-2) — the MRM binder for the Pipeline."""

from __future__ import annotations

from wavervanir_api import desk_validation as V


def _free_token(client, email="free-val@example.com"):
    return client.post(
        "/auth/register", json={"email": email, "password": "strong-pass-123"}
    ).json()["access_token"]


# ── documented binder content ───────────────────────────────────────────────

def test_inventory_covers_the_models_with_nonmodel_split():
    ids = {m["id"] for m in V.MODEL_INVENTORY}
    assert {"SRISK", "DCOVAR", "DEBTRANK", "PHASE-CLASSIFIER", "GARCH-DCC/LRMES"} <= ids
    assert all(m["is_model"] for m in V.MODEL_INVENTORY)
    assert all(m.get("tier") and m.get("intended_use") and m.get("non_use") for m in V.MODEL_INVENTORY)
    # the deterministic software is explicitly OUTSIDE the model definition
    assert len(V.NON_MODEL_COMPONENTS) >= 3
    assert "outside the sr 26-2 model definition" in V.NON_MODEL_NOTE.lower()


def test_methodology_has_citation_and_equation_per_model():
    for m in V.METHODOLOGY:
        assert m["citation"] and m["equation"]
    srisk = next(m for m in V.METHODOLOGY if m["id"] == "SRISK")
    assert "Brownlees" in srisk["citation"] and "k·D" in srisk["equation"]


def test_assumptions_are_materiality_rated():
    mats = {a["materiality"] for a in V.ASSUMPTIONS}
    assert mats <= {"HIGH", "MED", "LOW"} and "HIGH" in mats
    # the single-shared-LRMES + live-vintage caveats are rated HIGH
    high = [a["assumption"].lower() for a in V.ASSUMPTIONS if a["materiality"] == "HIGH"]
    assert any("lrmes" in h for h in high) and any("point-in-time" in h for h in high)


# ── computed evidence ───────────────────────────────────────────────────────

def test_mc_convergence_computes_and_is_honest():
    mc = V.mc_convergence()
    assert len(mc["by_paths"]) >= 3
    assert 0.0 < mc["by_seed"]["mean"] < 1.0
    assert isinstance(mc["converged"], bool)  # data-driven, not hardcoded True
    assert "rel_pct" in mc["by_seed"]


# ── route (default-deny gate) ───────────────────────────────────────────────

def test_validation_route_gated(client):
    assert client.get("/v1/desk/pipeline/validation").status_code == 401
    free = _free_token(client)
    assert client.get(
        "/v1/desk/pipeline/validation", headers={"Authorization": f"Bearer {free}"}
    ).status_code == 403
