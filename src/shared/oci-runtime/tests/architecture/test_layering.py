"""Mechanical enforcement of the hexagonal layering rules.

domain  <- ports  <- adapters  <- factory (composition root)

Allowed import directions:
  domain   -> stdlib + oci_runtime.domain.*
  ports    -> oci_runtime.domain.* + oci_runtime.ports.*
  adapters -> oci_runtime.domain.* + oci_runtime.ports.* + oci_runtime.adapters.*
  factory  -> everything  (composition root wires adapters to ports)
  root     -> everything  (__init__.py public API re-exports)

Forbidden:
  domain   -> ports | adapters | factory
  ports    -> adapters | factory
  adapters -> factory

This test has zero third-party dependencies (stdlib ast + pathlib only).
If a future commit introduces a layering violation, this test fails and
blocks the merge — no audit required to catch it.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "oci_runtime"

_LAYERS = ("domain", "ports", "adapters")

# What each layer may import from (relative to oci_runtime).
_ALLOWED_TARGETS = {
    "domain": {"domain"},
    "ports": {"domain", "ports"},
    "adapters": {"domain", "ports"},
    "factory": {"domain", "ports", "adapters", "factory"},
    "root": {"domain", "ports", "adapters", "factory"},
}


def _classify_layer(file_path: Path) -> str:
    rel = file_path.relative_to(_SRC_ROOT)
    parts = rel.parts
    if len(parts) == 1:
        if parts[0] == "__init__.py":
            return "root"
        if parts[0] == "factory.py":
            return "factory"
        return "root"
    if parts[0] in _LAYERS:
        return parts[0]
    return "root"


def _layer_of_imported_module(module: str) -> str | None:
    """Map 'oci_runtime.ports.managers' -> 'ports'. Returns None for non-oci_runtime."""
    if not module.startswith("oci_runtime."):
        return None
    parts = module.split(".")
    if len(parts) < 2:
        return "root"
    second = parts[1]
    if second in _LAYERS:
        return second
    if second == "factory":
        return "factory"
    return "root"


def _extract_oci_runtime_imports(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("oci_runtime"):
                modules.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("oci_runtime"):
                    modules.append(alias.name)
    return modules


def _all_source_files() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def _check_file(file_path: Path) -> list[str]:
    layer = _classify_layer(file_path)
    allowed = _ALLOWED_TARGETS[layer]
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    violations: list[str] = []
    for module in _extract_oci_runtime_imports(tree):
        target_layer = _layer_of_imported_module(module)
        if target_layer is None:
            continue
        if target_layer not in allowed:
            violations.append(
                f"{layer} layer imports {target_layer} layer: "
                f"{file_path.relative_to(_SRC_ROOT)} -> {module}"
            )
    return violations


class TestHexagonalLayering:
    """Mechanical guard: no layer may import from a layer above it."""

    @pytest.mark.parametrize(
        "file_path", _all_source_files(), ids=lambda p: str(p.relative_to(_SRC_ROOT))
    )
    def test_no_layering_violations(self, file_path: Path):
        violations = _check_file(file_path)
        assert not violations, "\n".join(violations)

    def test_domain_imports_only_stdlib(self):
        """domain/ must have zero oci_runtime imports except its own submodules."""
        domain_dir = _SRC_ROOT / "domain"
        for f in sorted(domain_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_oci_runtime_imports(tree):
                target = _layer_of_imported_module(module)
                assert target == "domain", (
                    f"{f.relative_to(_SRC_ROOT)} imports {module} "
                    f"(layer={target}); domain may only import from domain"
                )

    def test_ports_imports_no_adapters(self):
        """ports/ must never import from adapters/ or factory."""
        ports_dir = _SRC_ROOT / "ports"
        for f in sorted(ports_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_oci_runtime_imports(tree):
                target = _layer_of_imported_module(module)
                assert target not in ("adapters", "factory"), (
                    f"{f.relative_to(_SRC_ROOT)} imports {module} "
                    f"(layer={target}); ports may not import adapters or factory"
                )

    def test_adapters_import_no_factory(self):
        """adapters/ must never import from factory (composition root)."""
        adapters_dir = _SRC_ROOT / "adapters"
        for f in sorted(adapters_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_oci_runtime_imports(tree):
                target = _layer_of_imported_module(module)
                assert target != "factory", (
                    f"{f.relative_to(_SRC_ROOT)} imports {module} "
                    f"(layer={target}); adapters may not import factory"
                )


if __name__ == "__main__":
    # Runnable standalone: python tests/architecture/test_layering.py
    failures = 0
    for f in _all_source_files():
        v = _check_file(f)
        for line in v:
            print(f"FAIL: {line}")
            failures += 1
    if failures:
        print(f"\n{failures} layering violation(s) found.")
        sys.exit(1)
    print(f"OK: {len(_all_source_files())} source files, no layering violations.")
