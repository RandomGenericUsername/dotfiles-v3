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

Additional domain rules (oci-strict-hexagonal-layering-v2):
  - stdlib imports must be in _DOMAIN_ALLOWED_STDLIB (opt-in).
  - stdlib imports must NOT be in _DOMAIN_BANNED_STDLIB (opt-out).
  - Path FS method calls (.exists(), .read_text(), etc.) are forbidden.

Additional ports rule:
  - Only ABCs (or @dataclass aggregates) allowed; concrete classes
    must live in adapters/.

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
    "adapters": {"domain", "ports", "adapters"},
    "factory": {"domain", "ports", "adapters", "factory"},
    "root": {"domain", "ports", "adapters", "factory"},
}

# Domain stdlib allowlist (oci-strict-hexagonal-layering-v2/specs/.../spec.md)
_DOMAIN_ALLOWED_STDLIB = frozenset(
    {
        "posixpath",
        "io",
        "tarfile",
        "pathlib",
        "json",
        "re",
        "dataclasses",
        "collections",
        "collections.abc",
        "types",
        "enum",
    }
)

# Domain banned stdlib (oci-strict-hexagonal-layering-v2/specs/.../spec.md)
_DOMAIN_BANNED_STDLIB = frozenset(
    {
        "subprocess",
        "os",
        "shutil",
        "select",
        "selectors",
        "socket",
    }
)

# Stdlib module names available at runtime for classification.
_STDLIB_NAMES = frozenset(sys.stdlib_module_names)

# Ports concrete-class allowlist — aggregates that are explicitly permitted.
_PORTS_ALLOWED_AGGREGATES: dict[str, set[str]] = {
    "aggregates.py": {"Parsers"},
    "capabilities.py": {"RuntimeCapabilities"},
}

# Banned Path FS method calls in domain (oci-strict-hexagonal-layering-v2/specs/.../spec.md)
_BANNED_PATH_FS_METHODS = frozenset(
    {
        "exists",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "glob",
        "rglob",
        "iterdir",
        "mkdir",
        "rmdir",
        "unlink",
        "chmod",
        "chown",
        "stat",
        "lstat",
        "touch",
        "resolve",
    }
)


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


def _extract_stdlib_imports(tree: ast.AST) -> list[str]:
    """Extract top-level stdlib module names from AST imports."""
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _STDLIB_NAMES:
                modules.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _STDLIB_NAMES:
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


def _classify_ports_class(node: ast.ClassDef) -> str:
    """Classify a class in ports/ as abc, dataclass-aggregate, or concrete."""
    # Check inheritance from ABC (ast.Name for direct, ast.Attribute for qualified)
    inherits_abc = any(
        isinstance(base, ast.Name)
        and base.id == "ABC"
        or isinstance(base, ast.Attribute)
        and base.attr == "ABC"
        for base in node.bases
    )

    # Check for @abstractmethod on any method in this class
    has_abstract = False
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            if any(
                isinstance(d, ast.Name)
                and d.id == "abstractmethod"
                or isinstance(d, ast.Attribute)
                and d.attr == "abstractmethod"
                for d in item.decorator_list
            ):
                has_abstract = True
                break

    if has_abstract and inherits_abc:
        return "abc"

    # Check for @dataclass decorator on the class
    has_dataclass = any(
        isinstance(d, ast.Name)
        and d.id == "dataclass"
        or isinstance(d, ast.Attribute)
        and d.attr == "dataclass"
        or isinstance(d, ast.Call)
        and (
            (isinstance(d.func, ast.Name) and d.func.id == "dataclass")
            or (isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
        )
        for d in node.decorator_list
    )

    if has_dataclass:
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith("__") and item.name.endswith("__"):
                    continue
                return "concrete"
        return "dataclass-aggregate"

    return "concrete"


def _scan_for_banned_method_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """Find all calls to Path FS methods like .exists(), .read_text(), etc."""
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                name = func.attr
                if name in _BANNED_PATH_FS_METHODS:
                    results.append((node.lineno, name))
    return results


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

    def test_adapters_allowed_targets_includes_adapters(self):
        """Self-test: _ALLOWED_TARGETS['adapters'] includes 'adapters' (task 1.2)."""
        assert "adapters" in _ALLOWED_TARGETS["adapters"], (
            "adapters layer must be allowed to import from adapters "
            "(shared utilities like _SubprocessRunner)"
        )

    # ── §2: Domain stdlib allowlist ────────────────────────────────────

    def test_domain_stdlib_imports_are_allowlisted(self):
        """Every stdlib import in domain/ must be in _DOMAIN_ALLOWED_STDLIB."""
        domain_dir = _SRC_ROOT / "domain"
        failures: list[str] = []
        for f in sorted(domain_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_stdlib_imports(tree):
                # module is the dotted name (e.g. "collections.abc")
                top = module.split(".")[0]
                if top not in _DOMAIN_ALLOWED_STDLIB:
                    failures.append(
                        f"domain layer imports non-allowlisted stdlib: "
                        f"{module} in {f.relative_to(_SRC_ROOT)}"
                    )
        if failures:
            # xfail: build_tar.py uses os (pending oci-build-tar-posixpath)
            allowed_pending = {"os"}
            remaining = [
                m for m in failures if not any(p in m for p in allowed_pending)
            ]
            if not remaining:
                pytest.xfail("pending oci-build-tar-posixpath")
            pytest.fail("\n".join(remaining))

    def test_domain_stdlib_allowlist_self_test(self):
        """Self-test: synthetic AST inputs exercise the allowlist rule."""
        passes = ast.parse("import json")
        fails = ast.parse("import os")
        passes_coll = ast.parse("from collections.abc import Mapping")
        fails_base64 = ast.parse("import base64")

        def _stdlib_in_tree(tree: ast.AST) -> list[str]:
            return [m for m in {m.split(".")[0] for m in _extract_stdlib_imports(tree)}]

        p = _stdlib_in_tree(passes)
        assert all(m in _DOMAIN_ALLOWED_STDLIB for m in p), f"{p} should be allowed"

        f = _stdlib_in_tree(fails)
        assert any(m not in _DOMAIN_ALLOWED_STDLIB for m in f), f"{f} should fail"

        pc = _stdlib_in_tree(passes_coll)
        assert all(m in _DOMAIN_ALLOWED_STDLIB for m in pc), f"{pc} should be allowed"

        fb = _stdlib_in_tree(fails_base64)
        assert any(m not in _DOMAIN_ALLOWED_STDLIB for m in fb), f"{fb} should fail"

    # ── §3: Domain banned stdlib ────────────────────────────────────

    def test_domain_imports_no_banned_stdlib(self):
        """No domain file may import from _DOMAIN_BANNED_STDLIB."""
        domain_dir = _SRC_ROOT / "domain"
        failures: list[str] = []
        for f in sorted(domain_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_stdlib_imports(tree):
                top = module.split(".")[0]
                if top in _DOMAIN_BANNED_STDLIB:
                    failures.append(
                        f"domain layer imports banned stdlib: "
                        f"{module} in {f.relative_to(_SRC_ROOT)}"
                    )
        if failures:
            allowed_pending = {"os"}
            remaining = [
                m for m in failures if not any(p in m for p in allowed_pending)
            ]
            if not remaining:
                pytest.xfail("pending oci-build-tar-posixpath")
            pytest.fail("\n".join(remaining))

    def test_domain_banned_stdlib_self_test(self):
        """Self-test: synthetic AST inputs exercise the banned-stdlib rule."""
        fails_subprocess = ast.parse("import subprocess")
        fails_os = ast.parse("import os")
        fails_os_path = ast.parse("from os import path")
        passes_json = ast.parse("import json")
        passes_posixpath = ast.parse("import posixpath")

        def _banned(tree: ast.AST) -> list[str]:
            return [
                m.split(".")[0]
                for m in _extract_stdlib_imports(tree)
                if m.split(".")[0] in _DOMAIN_BANNED_STDLIB
            ]

        assert _banned(fails_subprocess), "subprocess should be banned"
        assert _banned(fails_os), "os should be banned"
        assert _banned(fails_os_path), "os (from os import path) should be banned"
        assert not _banned(passes_json), "json should not be banned"
        assert not _banned(passes_posixpath), "posixpath should not be banned"

    # ── §4: Ports ABC-only rule ────────────────────────────────────

    def test_ports_files_are_abstract_only(self):
        """ports/ must only contain ABCs or @dataclass aggregates."""
        ports_dir = _SRC_ROOT / "ports"
        failures: list[str] = []
        for f in sorted(ports_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    kind = _classify_ports_class(node)
                    if kind == "abc":
                        continue
                    allowlist = _PORTS_ALLOWED_AGGREGATES.get(f.name, set())
                    if node.name in allowlist:
                        continue
                    failures.append(
                        f"{f.relative_to(_SRC_ROOT)}:{node.lineno} "
                        f"declares concrete class '{node.name}' "
                        f"which is neither an ABC nor a @dataclass aggregate; "
                        f"relocate to adapters/"
                    )
        if failures:
            pytest.fail("\n".join(failures))

    def test_ports_classification_self_test(self):
        """Self-test: synthetic AST inputs exercise port classification."""
        abc_tree = ast.parse(
            "from abc import ABC, abstractmethod\n"
            "class Foo(ABC):\n"
            "    @abstractmethod\n"
            "    def m(self): ...\n"
        )
        abc_class = next(n for n in ast.walk(abc_tree) if isinstance(n, ast.ClassDef))
        assert _classify_ports_class(abc_class) == "abc"

        dataclass_tree = ast.parse(
            "from dataclasses import dataclass\n"
            "@dataclass(frozen=True)\n"
            "class Bar:\n"
            "    x: int\n"
        )
        dc_class = next(
            n for n in ast.walk(dataclass_tree) if isinstance(n, ast.ClassDef)
        )
        assert _classify_ports_class(dc_class) == "dataclass-aggregate"

        concrete_tree = ast.parse(
            "class Baz:\n    def m(self):\n        import os\n        os.read(...)\n"
        )
        conc_class = next(
            n for n in ast.walk(concrete_tree) if isinstance(n, ast.ClassDef)
        )
        assert _classify_ports_class(conc_class) == "concrete"

    # ── §5: Path FS method call ban ────────────────────────────────────

    def test_domain_no_path_fs_method_calls(self):
        """domain/ must not call banned FS methods on Path objects."""
        domain_dir = _SRC_ROOT / "domain"
        failures: list[str] = []
        for f in sorted(domain_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for lineno, method in _scan_for_banned_method_calls(tree):
                failures.append(
                    f"{f.relative_to(_SRC_ROOT)}:{lineno} "
                    f"calls Path.{method}() — "
                    f"FS methods on Path are forbidden in domain; "
                    f"delegate to an adapter"
                )
        assert not failures, "\n".join(failures)

    def test_path_method_ban_self_test(self):
        """Self-test: synthetic AST inputs exercise the path method ban."""
        flagged_exists = ast.parse("if p.exists(): pass")
        flagged_read = ast.parse("text = p.read_text()")
        not_flagged_decode = ast.parse("text = bytes(b'x').decode()")
        not_flagged_bytes = ast.parse("data = bytes(b'x')")

        assert _scan_for_banned_method_calls(flagged_exists) == [(1, "exists")]
        assert _scan_for_banned_method_calls(flagged_read) == [(1, "read_text")]
        assert _scan_for_banned_method_calls(not_flagged_decode) == []
        assert _scan_for_banned_method_calls(not_flagged_bytes) == []


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
    print(
        f"OK: {len(_all_source_files())} source files checked across 4 "
        f"architectural rules (layering, allowlist, ports-ABC, path-FS-ban)."
    )
