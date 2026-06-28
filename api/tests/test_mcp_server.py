"""CBSRM MCP server — boundary + tool-surface checks.

The AST test runs always (no MCP SDK needed); the import smoke-test skips when the
optional ``mcp`` extra isn't installed.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_SRC = (pathlib.Path(__file__).resolve().parent.parent
        / "src" / "wavervanir_api" / "mcp_server.py")


def test_mcp_module_is_boundary_clean_and_exposes_the_tools():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    imported = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            imported.append(n.module)
        elif isinstance(n, ast.Import):
            imported += [a.name for a in n.names]
    # never imports an internal VolanX module
    assert not any("VOLAN" in (m or "").upper() for m in imported), imported
    # imports the public cbsrm-backed desk modules + the MCP SDK
    assert any(m == "mcp.server.fastmcp" for m in imported)
    # the governed tools are present
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {
        "systemic_conditions", "lens_detail", "methodology", "risk_profile",
        "cockpit_group", "crisis_dossier", "systemic_capital_shortfall",
        "model_validation", "main",
    } <= funcs


def test_mcp_server_imports_when_sdk_present():
    pytest.importorskip("mcp")
    from wavervanir_api import mcp_server

    assert callable(mcp_server.main)
    assert mcp_server.mcp is not None
