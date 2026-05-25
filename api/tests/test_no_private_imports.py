"""AST guard: no private VolanX imports may exist in api/src/.

This protects the public/private boundary documented in
docs/PRIVACY_BOUNDARY.md. If this test fails, *do not* lower the bar —
inspect the offending file and either remove the import or move the file
to a private repo.

The guard:
  * walks every .py under api/src/
  * parses with ``ast``
  * collects every imported dotted name (Import + ImportFrom)
  * fails if any matches a forbidden pattern (substring, case-insensitive)
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


# Forbidden substrings — matched case-insensitively against the *dotted*
# import path. e.g. ``from VOLANX.brokers import ...`` becomes
# ``volanx.brokers`` after normalisation, which matches both ``volanx`` and
# ``volanx.brokers``.
FORBIDDEN_PATTERNS = [
    r"\bvolanx\b",
    r"\bvolanx\.brokers\b",
    r"\bvolanx\.execution\b",
    r"\bvolanx\.routing\b",
    r"\bvolanx\.options_intel\b",
    r"\brisk_army\b",
    r"\bgauntlet\b",
    r"\btruth_ledger\b",
    r"\bbayesian_gate\b",
    r"\bbroker_router\b",
    r"\border_spec\b",
    r"\bplace_order\b",
    # Broker SDKs are forbidden in the public surface — sanitized snapshot
    # files are the ONLY way broker-derived data may enter this service.
    r"\btastytrade\b",
    r"\btastyworks\b",
    r"\bib_insync\b",
    r"\bibapi\b",
    r"\balpaca_trade_api\b",
]

_FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_PATTERNS), flags=re.IGNORECASE)


SRC_ROOT = Path(__file__).resolve().parent.parent / "src"


def _collect_imports(py_file: Path) -> list[str]:
    """Return all dotted import names in the file."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names.append(mod)
            for alias in node.names:
                names.append(f"{mod}.{alias.name}" if mod else alias.name)
    return names


def test_src_tree_contains_no_forbidden_imports() -> None:
    assert SRC_ROOT.is_dir(), f"expected source tree at {SRC_ROOT}"
    violations: list[tuple[str, str]] = []
    for py in SRC_ROOT.rglob("*.py"):
        for imp in _collect_imports(py):
            if _FORBIDDEN_RE.search(imp):
                violations.append((str(py.relative_to(SRC_ROOT)), imp))
    if violations:
        formatted = "\n".join(f"  {f}: {imp}" for f, imp in violations)
        pytest.fail(
            "Forbidden private imports detected — public/private boundary "
            "would be broken:\n" + formatted
        )


def test_guard_detects_planted_volanx_import(tmp_path: Path) -> None:
    """Negative-control: the guard must actually reject a forbidden import."""
    planted = tmp_path / "planted.py"
    planted.write_text("from VOLANX.brokers import BrokerRouter\n", encoding="utf-8")
    imports = _collect_imports(planted)
    assert any(_FORBIDDEN_RE.search(i) for i in imports), (
        f"AST guard regression — did not flag planted VolanX import: {imports!r}"
    )


def test_guard_allows_cbsrm() -> None:
    """Positive-control: cbsrm-style imports must pass."""
    import io

    code = "from cbsrm.reporting import build_macro_composite_report\n"
    tree = ast.parse(code)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append(mod)
            for a in node.names:
                imports.append(f"{mod}.{a.name}")
    assert not any(_FORBIDDEN_RE.search(i) for i in imports), imports
