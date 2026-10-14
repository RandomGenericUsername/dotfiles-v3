#!/usr/bin/env python3
"""deploy-coverage -- every AGS source reachable from app.tsx must be deployed.

WHY THIS GATE EXISTS. The AGS bar is deployed PER FILE: the `compositor_configs`
role loops over `compositor_configs_skeleton_files` and copies each listed file
into the install spine (`<install>/config/ags/...`). A file that the bar reaches
through a relative import but that is NOT in that list is simply never copied --
`copy` neither creates it nor warns -- so a fresh (or re-run) provision leaves
the module absent, `ags bundle` cannot resolve the import, and the BAR window
fails to start. This is the same failure shape the role's own audio comment
records for `audio/composition.ts`, and it is exactly what happened when the bar
re-architecture added `kit/icon-source.ts`, `kit/shapes.ts`, the `domains/*`
read-model adapters, and the Bluetooth popup/state/widget sources: the sources
landed, the manifest did not.

A structural test that pins the manifest list cannot catch this class by itself:
it asserts the list is what it is, not that the list COVERS what the entry point
reaches. This gate derives the requirement from the source tree instead.

WHAT IT DOES.
  (a) parses the deployed AGS set out of `compositor_configs_skeleton_files`
      (roles/compositor_configs/vars/main.yml) -- the single source of truth for
      what a provision copies;
  (b) computes the RELATIVE-IMPORT closure of `dotfiles/config/ags/app.tsx` --
      the composition root AGS bundles -- following only relative specifiers
      (`./x`, `../x`) into files that participate in the bundle;
  (c) FAILS, listing every reachable file that is not deployed.

WHAT IT DELIBERATELY DOES NOT FOLLOW. A relative import resolves only to a
TS/TSX/ambient-declaration/CSS module. `lib/icon-registry.ts` imports
`../icons.json`, but `icons.json` is GENERATED OUTPUT written by the role's own
icon-manifest task (`compositor_configs_icon_manifest_dest`), not a skeleton, so
it is not a missing-module hazard and is not in this gate's scope. Non-relative
specifiers (`ags/gtk4/app`, `gi://Gtk`) are provided by the runtime, never
deployed per file. Commented-out imports are ignored: a `//`-commented example
in `app.tsx` naming `./audio/audio-panel.css` was picked up by an early version
of this scan and is not a real dependency.

Usage: ``python3 scripts/deploy-coverage.py [--root REPO_ROOT]``
Exit 0 = every reachable AGS module is registered for deployment.
Exit 1 = one or more reachable modules are not deployed (listed), or an input is
         missing/unreadable.

PyYAML is imported and if it is unavailable this gate FAILS rather than
skipping: the manifest is parsed as YAML, not line-mangled. Run it through the
provisioning project so PyYAML is importable, exactly as `icons-json-drift`
does:

    uv run --directory src/provisioning python ../../scripts/deploy-coverage.py

The `../../` is load-bearing: `--directory` moves the interpreter's CWD to
src/provisioning, so a `scripts/...` path does not resolve from there. The script
locates the repo from its own `__file__`, so its own CWD does not matter -- only
the path you type to reach it does.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VARS_FILE = "src/provisioning/ansible/roles/compositor_configs/vars/main.yml"
AGS_DIR = "dotfiles/config/ags"
SOURCE_PREFIX = "dotfiles/config/ags/"
ENTRY = "app.tsx"

# Files that participate in `ags bundle` and are therefore a missing-module
# hazard. `.d.ts` ends in `.ts`, so it is covered by the `.ts` suffix.
_MODULE_SUFFIXES = (".ts", ".tsx", ".css")

# Relative import specifiers: `import x from "./y"`, `import "./y"`,
# `export { x } from "./y"`, `import type { X } from "./y"`.
_IMPORT_RE = re.compile(r"""(?:from|import)\s*["']([^"']+)["']""")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")


def _is_module(path: Path) -> bool:
    return path.suffix in _MODULE_SUFFIXES


def _imports_of(path: Path) -> list[str]:
    """Every import/export specifier in ``path``, with comments removed.

    Comments are stripped because an example import written inside a comment is
    not a dependency, and treating it as one is a false positive that this gate
    cannot afford: the point of the gate is that a green run means something.
    """
    text = path.read_text()
    text = _BLOCK_COMMENT_RE.sub(" ", text)
    text = _LINE_COMMENT_RE.sub(" ", text)
    return _IMPORT_RE.findall(text)


def _resolve(base_dir: Path, spec: str) -> Path | None:
    """Resolve a relative ``spec`` against ``base_dir`` to a module file.

    Returns None for a non-relative specifier (runtime-provided) or a relative
    one that does not resolve to a bundle module (e.g. the generated
    ``../icons.json``).
    """
    if not spec.startswith("."):
        return None
    candidate = base_dir / spec
    if candidate.is_file() and _is_module(candidate):
        return candidate.resolve()
    for suffix in _MODULE_SUFFIXES:
        appended = Path(str(candidate) + suffix)
        if appended.is_file():
            return appended.resolve()
    for suffix in (".ts", ".tsx"):
        index = candidate / f"index{suffix}"
        if index.is_file():
            return index.resolve()
    return None


def relative_import_closure(ags_dir: Path, entry: str = ENTRY) -> set[Path]:
    """The set of module files reachable from ``entry`` by relative imports."""
    start = (ags_dir / entry).resolve()
    if not start.is_file():
        raise FileNotFoundError(f"AGS entry point not found: {start}")
    seen: set[Path] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for spec in _imports_of(current):
            resolved = _resolve(current.parent, spec)
            if resolved is not None and resolved not in seen:
                stack.append(resolved)
    return seen


def parse_deployed_ags_sources(vars_text: str) -> set[str]:
    """The AGS-relative paths in ``compositor_configs_skeleton_files``."""
    try:
        import yaml  # PyYAML ships with the provisioning project (ansible-core dep)
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            f"PyYAML is not importable ({exc}); this gate parses the manifest as "
            f"YAML rather than by line-mangling and must not guess. Run it as: "
            f"uv run --directory src/provisioning python ../../scripts/deploy-coverage.py"
        ) from exc

    data = yaml.safe_load(vars_text)
    if not isinstance(data, dict):
        raise ValueError(f"{VARS_FILE} did not parse to a mapping")
    files = data.get("compositor_configs_skeleton_files")
    if not isinstance(files, list):
        raise ValueError(
            f"{VARS_FILE} has no `compositor_configs_skeleton_files` list"
        )
    deployed: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source", ""))
        if source.startswith(SOURCE_PREFIX):
            deployed.add(source[len(SOURCE_PREFIX) :])
    return deployed


def main() -> int:
    ap = argparse.ArgumentParser(description="reachable AGS modules are deployed")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    vars_path = root / VARS_FILE
    ags_dir = (root / AGS_DIR).resolve()

    for path, label in ((vars_path, VARS_FILE), (ags_dir / ENTRY, f"{AGS_DIR}/{ENTRY}")):
        if not path.is_file():
            print(f"MISSING {label}: {path}")
            return 1

    try:
        deployed = parse_deployed_ags_sources(vars_path.read_text())
        closure = relative_import_closure(ags_dir)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}")
        return 1

    reachable = {path.relative_to(ags_dir).as_posix() for path in closure}
    missing = sorted(reachable - deployed)

    print(
        f"deploy-coverage: reachable AGS modules from {AGS_DIR}/{ENTRY}: "
        f"{len(reachable)}"
    )
    print(f"deploy-coverage: deployed AGS sources in the manifest: {len(deployed)}")

    if missing:
        print(
            f"deploy-coverage: FAIL -- {len(missing)} reachable module(s) not "
            f"registered in compositor_configs_skeleton_files:"
        )
        for rel in missing:
            print(f"  - {AGS_DIR}/{rel}")
        print(
            "  A provision copies ONLY the registered files, so each one above is "
            "absent from a fresh/re-run install and `ags bundle` cannot resolve "
            "its import -- the bar fails to start. Add each to "
            f"`compositor_configs_skeleton_files` in {VARS_FILE} (and mirror it in "
            "the verify role's `verify_compositor_skeleton_files`)."
        )
        return 1

    print(
        "deploy-coverage: PASS -- every AGS module reachable from app.tsx is "
        "registered for deployment"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
