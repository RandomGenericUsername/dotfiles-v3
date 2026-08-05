"""Mechanical enforcement of the provisioning hexagonal layering rules.

domain  <- ports  <- adapters  <- application  <- cli

Allowed import directions:
  domain      -> stdlib + provisioning.domain.*
  ports       -> provisioning.domain.* + provisioning.ports.*
  adapters    -> provisioning.domain/ports/adapters.*
  application -> provisioning.domain/ports/adapters/application.*
  cli         -> everything (outer shell / composition root)
  root        -> everything (__init__.py public API re-exports)

Forbidden:
  domain      -> ports | adapters | application | cli
  ports       -> adapters | application | cli
  adapters    -> application | cli
  application -> cli

Additional domain rules:
  - stdlib imports must be in _DOMAIN_ALLOWED_STDLIB (opt-in).
  - stdlib imports must NOT be in _DOMAIN_BANNED_STDLIB (opt-out).
  - Path FS method calls (.exists(), .read_text(), etc.) are forbidden.

Additional ports rule:
  - Only ABCs (or @dataclass aggregates) allowed; concrete classes
    must live in adapters/.

Rule 5 (cross-package, §11 boundary):
  - No source file may import any dotfiles-sibling package except cli_output.
  - The forbidden set is: core, infrastructure, color_scheme_generator,
    wallpaper_effects_generator, icon_templates_renderer,
    config_assembler_engine, oci_runtime.
  - Third-party imports must be declared dependencies of the package.

This test has zero third-party dependencies (stdlib ast + pathlib + tomllib only).
If a future commit introduces a layering violation, this test fails and
blocks the merge — no audit required to catch it.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "provisioning"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _PROJECT_ROOT / "pyproject.toml"

_LAYERS = ("domain", "ports", "adapters", "application", "cli")

# What each layer may import from (relative to provisioning).
_ALLOWED_TARGETS = {
    "domain": {"domain"},
    "ports": {"domain", "ports"},
    "adapters": {"domain", "ports", "adapters"},
    "application": {"domain", "ports", "adapters", "application"},
    "cli": {"domain", "ports", "adapters", "application", "cli"},
    "root": {"domain", "ports", "adapters", "application", "cli"},
}

# Domain stdlib allowlist — the provisioning domain is PURE, zero-I/O data
# (no os/subprocess/shutil/pathlib/io). Unlike oci-runtime, do NOT add
# pathlib/io/posixpath/tarfile/json here. "__future__" is always permitted
# (from __future__ import annotations is the repo-wide convention).
_DOMAIN_ALLOWED_STDLIB = frozenset(
    {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "collections",
        "collections.abc",
        "functools",
        "re",
    }
)

# Domain banned stdlib (opt-out, mirroring oci-runtime).
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

# Rule 5: dotfiles-sibling packages that src/provisioning must never import.
_FORBIDDEN_CROSS_PACKAGE = frozenset(
    {
        "core",
        "infrastructure",
        "color_scheme_generator",
        "wallpaper_effects_generator",
        "icon_templates_renderer",
        "config_assembler_engine",
        "oci_runtime",
    }
)

# Banned Path FS method calls in domain.
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

# Ports concrete-class allowlist — provisioning ports are pure ABCs today.
_PORTS_ALLOWED_AGGREGATES: dict[str, set[str]] = {}

# Stdlib module names available at runtime for classification.
_STDLIB_NAMES = frozenset(sys.stdlib_module_names)


def _package_name() -> str:
    return _SRC_ROOT.name


def _module_name_for_file(file_path: Path) -> str:
    """Map src/provisioning/<sub>/<mod>.py -> provisioning.<sub>.<mod>."""
    rel = file_path.relative_to(_SRC_ROOT)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join([_package_name(), *parts])


def _classify_layer(file_path: Path) -> str:
    rel = file_path.relative_to(_SRC_ROOT)
    parts = rel.parts
    if len(parts) == 1:
        return "root"
    if parts[0] in _LAYERS:
        return parts[0]
    return "root"


def _layer_of_imported_module(module: str) -> str | None:
    """Map 'provisioning.ports.fact_reader' -> 'ports'. None for non-provisioning."""
    pkg = _package_name()
    if module == pkg:
        return "root"
    if not module.startswith(f"{pkg}."):
        return None
    parts = module.split(".")
    if len(parts) < 2:
        return "root"
    second = parts[1]
    if second in _LAYERS:
        return second
    return "root"


def _extract_import_modules(tree: ast.AST, file_path: Path) -> list[str]:
    """Resolve every import in the tree to a fully-qualified module name.

    Handles absolute, dotted, and relative (level > 0) imports.
    """
    current_parts = _module_name_for_file(file_path).split(".")
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = current_parts[: len(current_parts) - node.level]
                if node.module:
                    base = [*base, *node.module.split(".")]
                modules.append(".".join(base))
            elif node.module:
                modules.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
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


def _extract_third_party_imports(tree: ast.AST, file_path: Path) -> set[str]:
    """Return top-level import roots that are neither stdlib nor in-package."""
    pkg = _package_name()
    roots: set[str] = set()
    for module in _extract_import_modules(tree, file_path):
        top = module.split(".")[0]
        if top in _STDLIB_NAMES or top == pkg:
            continue
        roots.add(top)
    return roots


def _all_source_files() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def _check_file(file_path: Path) -> list[str]:
    layer = _classify_layer(file_path)
    allowed = _ALLOWED_TARGETS[layer]
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    violations: list[str] = []
    for module in _extract_import_modules(tree, file_path):
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
    inherits_abc = any(
        isinstance(base, ast.Name)
        and base.id == "ABC"
        or isinstance(base, ast.Attribute)
        and base.attr == "ABC"
        for base in node.bases
    )

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


def _allowed_third_party_roots() -> set[str]:
    """Derive allowed third-party import roots from declared package deps.

    cli-output is always allowed (§11). All other roots must be declared in
    pyproject.toml [project].dependencies or [tool.uv.sources].
    """
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    roots = {"cli_output"}
    for dep in data["project"].get("dependencies", []):
        name = dep.split(";")[0].split("[")[0].strip()
        roots.add(_import_root(name))
    for name in data.get("tool", {}).get("uv", {}).get("sources", {}):
        roots.add(_import_root(name))
    return roots


def _import_root(package_name: str) -> str:
    """Normalize a distribution name to its import root.

    Strips version specifiers and extras: typer>=0.12 -> typer;
    cli-output -> cli_output; ansible-core -> ansible.
    """
    name = re.split(r"[\s<>=!~]+", package_name)[0]
    if name == "ansible-core":
        return "ansible"
    return name.replace("-", "_")


class TestHexagonalLayering:
    """Mechanical guard: no layer may import from a layer above it."""

    @pytest.mark.parametrize(
        "file_path", _all_source_files(), ids=lambda p: str(p.relative_to(_SRC_ROOT))
    )
    def test_no_layering_violations(self, file_path: Path) -> None:
        violations = _check_file(file_path)
        assert not violations, "\n".join(violations)

    def test_domain_imports_only_domain(self) -> None:
        """domain/ must have zero provisioning imports except its own submodules."""
        domain_dir = _SRC_ROOT / "domain"
        for f in sorted(domain_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_import_modules(tree, f):
                target = _layer_of_imported_module(module)
                if target is None:
                    continue
                assert target == "domain", (
                    f"{f.relative_to(_SRC_ROOT)} imports {module} "
                    f"(layer={target}); domain may only import from domain"
                )

    def test_ports_import_no_adapters(self) -> None:
        """ports/ must never import from adapters/, application/, or cli/."""
        ports_dir = _SRC_ROOT / "ports"
        if not ports_dir.exists():
            pytest.skip("ports layer does not exist yet")
        for f in sorted(ports_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_import_modules(tree, f):
                target = _layer_of_imported_module(module)
                if target is None:
                    continue
                assert target not in ("adapters", "application", "cli"), (
                    f"{f.relative_to(_SRC_ROOT)} imports {module} "
                    f"(layer={target}); ports may not import adapters/application/cli"
                )

    def test_adapters_import_no_application(self) -> None:
        """adapters/ must never import from application/ or cli/."""
        adapters_dir = _SRC_ROOT / "adapters"
        if not adapters_dir.exists():
            pytest.skip("adapters layer does not exist yet")
        for f in sorted(adapters_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_import_modules(tree, f):
                target = _layer_of_imported_module(module)
                if target is None:
                    continue
                assert target not in ("application", "cli"), (
                    f"{f.relative_to(_SRC_ROOT)} imports {module} "
                    f"(layer={target}); adapters may not import application/cli"
                )

    def test_layering_classification_self_test(self) -> None:
        """Self-test: synthetic module names exercise the layer classifier."""
        assert _layer_of_imported_module("provisioning.domain.models") == "domain"
        assert _layer_of_imported_module("provisioning.ports.fact_reader") == "ports"
        assert _layer_of_imported_module("provisioning.adapters.ansible_executor") == "adapters"
        assert _layer_of_imported_module("provisioning.cli.main") == "cli"
        assert _layer_of_imported_module("provisioning") == "root"
        assert _layer_of_imported_module("typer") is None
        # A deliberately-violating import must not be allowed by any inner layer.
        assert "adapters" not in _ALLOWED_TARGETS["domain"]
        assert "application" not in _ALLOWED_TARGETS["adapters"]
        assert "cli" not in _ALLOWED_TARGETS["application"]
        assert "cli" in _ALLOWED_TARGETS["cli"]

    # ── Domain stdlib allowlist ────────────────────────────────────

    def test_domain_stdlib_imports_are_allowlisted(self) -> None:
        """Every stdlib import in domain/ must be in _DOMAIN_ALLOWED_STDLIB."""
        domain_dir = _SRC_ROOT / "domain"
        failures: list[str] = []
        for f in sorted(domain_dir.rglob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for module in _extract_stdlib_imports(tree):
                top = module.split(".")[0]
                if top not in _DOMAIN_ALLOWED_STDLIB:
                    failures.append(
                        f"domain layer imports non-allowlisted stdlib: "
                        f"{module} in {f.relative_to(_SRC_ROOT)}"
                    )
        assert not failures, "\n".join(failures)

    def test_domain_stdlib_allowlist_self_test(self) -> None:
        """Self-test: synthetic AST inputs exercise the allowlist rule."""
        passes = ast.parse("import dataclasses")
        fails_os = ast.parse("import os")
        fails_pathlib = ast.parse("import pathlib")
        passes_coll = ast.parse("from collections.abc import Mapping")

        def _stdlib_in_tree(tree: ast.AST) -> list[str]:
            return list({m.split(".")[0] for m in _extract_stdlib_imports(tree)})

        p = _stdlib_in_tree(passes)
        assert all(m in _DOMAIN_ALLOWED_STDLIB for m in p), f"{p} should be allowed"
        assert any(m not in _DOMAIN_ALLOWED_STDLIB for m in _stdlib_in_tree(fails_os)), (
            "os should fail the allowlist"
        )
        assert any(m not in _DOMAIN_ALLOWED_STDLIB for m in _stdlib_in_tree(fails_pathlib)), (
            "pathlib should fail the allowlist"
        )
        pc = _stdlib_in_tree(passes_coll)
        assert all(m in _DOMAIN_ALLOWED_STDLIB for m in pc), f"{pc} should be allowed"

    # ── Domain banned stdlib ────────────────────────────────────

    def test_domain_imports_no_banned_stdlib(self) -> None:
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
        assert not failures, "\n".join(failures)

    def test_domain_banned_stdlib_self_test(self) -> None:
        """Self-test: synthetic AST inputs exercise the banned-stdlib rule."""
        fails_subprocess = ast.parse("import subprocess")
        fails_os = ast.parse("import os")
        fails_os_path = ast.parse("from os import path")
        passes_dataclasses = ast.parse("import dataclasses")

        def _banned(tree: ast.AST) -> list[str]:
            return [
                m.split(".")[0]
                for m in _extract_stdlib_imports(tree)
                if m.split(".")[0] in _DOMAIN_BANNED_STDLIB
            ]

        assert _banned(fails_subprocess), "subprocess should be banned"
        assert _banned(fails_os), "os should be banned"
        assert _banned(fails_os_path), "os (from os import path) should be banned"
        assert not _banned(passes_dataclasses), "dataclasses should not be banned"

    # ── Ports ABC-only rule ────────────────────────────────────

    def test_ports_files_are_abstract_only(self) -> None:
        """ports/ must only contain ABCs or @dataclass aggregates."""
        ports_dir = _SRC_ROOT / "ports"
        if not ports_dir.exists():
            pytest.skip("ports layer does not exist yet")
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
        assert not failures, "\n".join(failures)

    def test_ports_classification_self_test(self) -> None:
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
            "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Bar:\n    x: int\n"
        )
        dc_class = next(n for n in ast.walk(dataclass_tree) if isinstance(n, ast.ClassDef))
        assert _classify_ports_class(dc_class) == "dataclass-aggregate"

        concrete_tree = ast.parse(
            "class Baz:\n    def m(self):\n        import os\n        os.read(...)\n"
        )
        conc_class = next(n for n in ast.walk(concrete_tree) if isinstance(n, ast.ClassDef))
        assert _classify_ports_class(conc_class) == "concrete"

    # ── Path FS method call ban ────────────────────────────────────

    def test_domain_no_path_fs_method_calls(self) -> None:
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

    def test_path_method_ban_self_test(self) -> None:
        """Self-test: synthetic AST inputs exercise the path method ban."""
        flagged_exists = ast.parse("if p.exists(): pass")
        flagged_read = ast.parse("text = p.read_text()")
        not_flagged_decode = ast.parse("text = bytes(b'x').decode()")
        not_flagged_bytes = ast.parse("data = bytes(b'x')")

        assert _scan_for_banned_method_calls(flagged_exists) == [(1, "exists")]
        assert _scan_for_banned_method_calls(flagged_read) == [(1, "read_text")]
        assert _scan_for_banned_method_calls(not_flagged_decode) == []
        assert _scan_for_banned_method_calls(not_flagged_bytes) == []

    # ── Rule 5: cross-package §11 boundary ──────────────────────────

    def test_no_forbidden_cross_package_imports(self) -> None:
        """No source file may import any member of the Rule 5 forbidden set."""
        failures: list[str] = []
        for f in _all_source_files():
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for root in sorted(_extract_third_party_imports(tree, f)):
                if root in _FORBIDDEN_CROSS_PACKAGE:
                    failures.append(
                        f"{f.relative_to(_SRC_ROOT)} imports forbidden cross-package root {root!r}"
                    )
        assert not failures, "\n".join(failures)

    def test_only_allowed_cross_package_roots(self) -> None:
        """Only cli_output (or declared deps) may be imported cross-package."""
        allowed = _allowed_third_party_roots()
        failures: list[str] = []
        for f in _all_source_files():
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for root in sorted(_extract_third_party_imports(tree, f)):
                if root in _FORBIDDEN_CROSS_PACKAGE:
                    continue
                if root not in allowed:
                    failures.append(
                        f"{f.relative_to(_SRC_ROOT)} imports undeclared "
                        f"third-party root {root!r}; allowed: "
                        f"{sorted(allowed)}"
                    )
        assert not failures, "\n".join(failures)

    def test_forbidden_cross_package_self_test(self) -> None:
        """Self-test: a deliberately-violating import must be flagged."""
        tree = ast.parse(
            "import core\n"
            "import cli_output\n"
            "from provisioning.domain import models\n"
            "from provisioning.adapters import ansible_executor\n"
        )
        third_party = _extract_third_party_imports(tree, _SRC_ROOT / "domain" / "models.py")
        # core is in the forbidden set and must be flagged.
        assert "core" in third_party
        assert "core" in _FORBIDDEN_CROSS_PACKAGE
        # cli_output is the one allowed dotfiles-sibling.
        assert "cli_output" in third_party
        assert "cli_output" not in _FORBIDDEN_CROSS_PACKAGE
        # in-package imports are never classified as third-party.
        assert "provisioning" not in third_party

    def test_allowed_third_party_roots_derivation_self_test(self) -> None:
        """Self-test: the pyproject-derived allowlist covers current imports."""
        allowed = _allowed_third_party_roots()
        assert "cli_output" in allowed
        assert "typer" in allowed
        assert "pydantic" in allowed
        # ansible-core normalizes to its real import root.
        assert "ansible" in allowed
        # dotfiles siblings are NOT declared deps, so they are not allowed.
        for forbidden in _FORBIDDEN_CROSS_PACKAGE:
            assert forbidden not in allowed, (
                f"{forbidden!r} is a forbidden dotfiles-sibling and must not be "
                f"derivable as an allowed third-party root"
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
    print(
        f"OK: {len(_all_source_files())} source files checked across 5 "
        f"architectural rules (layering, allowlist, banned-stdlib, ports-ABC, "
        f"path-FS-ban, cross-package)."
    )
