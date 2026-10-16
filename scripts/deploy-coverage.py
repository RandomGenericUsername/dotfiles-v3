#!/usr/bin/env python3
"""deploy-coverage -- every AGS source reachable from app.tsx must be deployed.

WHY THIS GATE EXISTS. The AGS bar used to deploy PER FILE: the
`compositor_configs` role looped over `compositor_configs_skeleton_files` and
copied each listed file into the install spine (`<install>/config/ags/...`).
A file that the bar reached through a relative import but that was NOT in that
list was simply never copied -- `copy` neither creates it nor warns -- so a
fresh (or re-run) provision left the module absent, `ags bundle` could not
resolve the import, and the BAR window failed to start. That per-file hazard
is gone: the bar now deploys WHOLE as one versioned unit (the `ags_apps`
role symlinks the unit's bar/ subdir as the live <install>/config/ags), so no
manifest can drift from the entry point's closure. The gate's job changed
with it: instead of covering each reachable file, it asserts the bridge is
RETIRED (no per-file bar entry may remain in the skeleton list — a stale one
would template INTO the unit tree through the live-bar link and silently
diverge the live bar from the pinned tag) and that the provisioning role
installs the pinned unit, records the pin, deploys the live-bar link, and
creates the per-unit resolution shortcut.

A structural test that pins the remaining manifest list cannot catch a stale
bar entry by itself: it asserts the list is what it is, not that the list
contains no retired bridge source. This gate derives the requirement from the
source tree instead.

WHAT IT DOES.
  (a) parses the deployed non-bar set out of `compositor_configs_skeleton_files`
      (roles/compositor_configs/vars/main.yml) -- the single source of truth for
      what a provision copies per file;
  (b) computes the RELATIVE-IMPORT closure of `dotfiles/config/ags/app.tsx` --
      the composition root AGS bundles -- following only relative specifiers
      (`./x`, `../x`) into files that participate in the bundle;
  (c) FAILS on any `dotfiles/config/ags/` source still listed per file (the
      retired bridge), on any relative import traversing the retired
      `platform/` dir, and unless the provisioning roles install the pinned
      platform unit (shared-ancestor shortcut) AND the pinned bar unit
      (live-bar link + per-unit resolution shortcut).

WHAT IT DELIBERATELY DOES NOT FOLLOW. A relative import resolves only to a
TS/TSX/ambient-declaration/CSS module. Generated artifacts (`icons.json`) are
written by the role's own tasks, not skeletons, so they are not a
missing-module hazard and are not in this gate's scope. Non-relative specifiers
(`ags/gtk4/app`, `gi://Gtk`) are provided by the runtime, never deployed per
file. Commented-out imports are ignored: a `//`-commented example in `app.tsx`
naming `./audio/audio-panel.css` was picked up by an early version of this scan
and is not a real dependency.

THE BAR IS EXTERNAL NOW. The bar's own sources live in the pinned ags-apps
unit (`<install>/ags-apps/<tag>/bar/`), deployed whole via the live-bar
symlink — so the reachable closure below is covered BY CONSTRUCTION, and the
gate reports its size instead of diffing it against a manifest. The in-place
`dotfiles/config/ags/` tree remains the dev/typecheck/test source (the
bridge), and the closure still guards it: a relative import into the retired
in-place `platform/` dir is REJECTED loudly.

THE PLATFORM IS EXTERNAL TOO. `ags-platform` and its subpaths are a BARE
SPECIFIER resolved by AGS's embedded esbuild through provisioning-created
`node_modules` shortcuts (spine AD-17): the shared-ancestor shortcut for
every config tree, plus the per-unit shortcut inside the bar unit (esbuild
realpaths the live-bar link, so the shared ancestor is not an ancestor of
the real bar tree). The gate asserts the provisioning role installs the
pinned unit and creates the shared-ancestor shortcut, and the bar role
creates the per-unit one. A green run means "the retired bridge is gone and
both external units the bar needs are provisioned".

Usage: ``python3 scripts/deploy-coverage.py [--root REPO_ROOT]``
Exit 0 = the bridge is retired and both units are provisioned.
Exit 1 = a stale per-file bar entry remains, a retired-dir import exists, a
         unit is not provisioned, or an input is missing/unreadable.

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

# The platform is now an EXTERNAL unit consumed by a BARE SPECIFIER (spine
# AD-17): the bar imports `ags-platform`, `ags-platform/ports/*` and
# `ags-platform/adapters/*`, which AGS's embedded esbuild resolves through the
# shared-ancestor `node_modules/ags-platform` shortcut that provisioning
# creates. It is NOT deployed per file, so it is NOT this gate's coverage — and
# a non-relative specifier is skipped by `_resolve` anyway. It is named here so
# the external status is DECLARED rather than merely implied, and so the
# provisioning assertion below can check the unit + shortcut really exist in
# the role that installs them.
PLATFORM_PACKAGE = "ags-platform"
PLATFORM_ROLE_VARS = "src/provisioning/ansible/roles/ags_platform/vars/main.yml"
PLATFORM_ROLE_TASKS = "src/provisioning/ansible/roles/ags_platform/tasks/main.yml"

# The retired in-place platform copy (extract-platform-in-place) lived here. It
# is deleted by this change; a surviving relative import into it would resolve
# to nothing and be silently skipped by `_resolve`, so it is REJECTED loudly.
RETIRED_PLATFORM_DIR = "dotfiles/config/ags/platform"

# The bar unit role (ags-apps-bar-first slice 2, AD-1/AD-17/AD-23): the mirror
# of the platform constants above. The unit is the monorepo checkout at the
# pinned tag; the deployed bar is its bar/ subdir.
BAR_PACKAGE = "ags-apps"
BAR_ROLE_VARS = "src/provisioning/ansible/roles/ags_apps/vars/main.yml"
BAR_ROLE_TASKS = "src/provisioning/ansible/roles/ags_apps/tasks/main.yml"

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

    Returns None for a non-relative specifier (runtime-provided, INCLUDING the
    external ``ags-platform`` bare specifier) or a relative one that does not
    resolve to a bundle module (e.g. the generated ``../icons.json``).

    Raises for a relative specifier that traverses the RETIRED in-place
    platform dir: that is not a benign non-module, it is an import into code
    this change deleted, and `_resolve` would otherwise skip it silently.
    """
    if not spec.startswith("."):
        return None
    if re.search(r"(?:^|/)platform/", spec):
        raise ValueError(
            f"relative import into the retired in-place platform copy: {spec!r} "
            f"(resolved against {base_dir}); the platform is now the external "
            f"bare specifier {PLATFORM_PACKAGE!r} (spine AD-17). Repoint the "
            f"import — do NOT leave it relative, `_resolve` cannot see it."
        )
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


def assert_platform_provisioning(root: Path) -> None:
    """The external platform unit + shortcut must be provisioned, not assumed.

    The bar now imports `ags-platform` by bare specifier; nothing in the repo
    tree provides it (that is the point of AD-17). The gate cannot verify the
    HOST (verify.yaml does that), but it CAN refuse to pass if the repo has no
    provisioning that installs the pinned unit and creates the shared-ancestor
    shortcut. Without this, deleting the platform from the repo would leave the
    gate green with the bare specifier unresolvable at install time — exactly
    the silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / PLATFORM_ROLE_VARS
    tasks_path = root / PLATFORM_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the platform is consumed by bare specifier {PLATFORM_PACKAGE!r} but "
            f"no provisioning role declares the unit: {PLATFORM_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the platform role has no tasks to install the unit: {PLATFORM_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{PLATFORM_ROLE_VARS} did not parse to a mapping")

    version = data.get("ags_platform_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(
            f"{PLATFORM_ROLE_VARS} does not pin ags_platform_version — the unit "
            f"must be versioned by directory (spine AD-23)"
        )

    # Assert the SHAPE, not the exact Jinja string (the vars route through
    # intermediates, which is an implementation detail): the unit is
    # <install>/ags-platform/<version>/, and the shortcut is
    # <install>/config/node_modules/ags-platform (the SHARED ANCESTOR of every
    # config/ags-*).
    install_root = str(data.get("ags_platform_install_root", ""))
    if not ("install_dir" in install_root and "ags-platform" in install_root):
        raise ValueError(
            f"ags_platform_install_root must be <install>/ags-platform; got "
            f"{install_root!r}"
        )

    unit = str(data.get("ags_platform_unit_dir", ""))
    if "ags_platform_version" not in unit:
        raise ValueError(
            f"ags_platform_unit_dir must version the unit by directory "
            f"(ags_platform_version); got {unit!r}"
        )

    spine = str(data.get("ags_platform_spine_config_dir", ""))
    if not ("install_dir" in spine and "config" in spine):
        raise ValueError(
            f"ags_platform_spine_config_dir must be <install>/config (the SHARED "
            f"ANCESTOR); got {spine!r}"
        )
    shortcut_dir = str(data.get("ags_platform_shortcut_dir", ""))
    if "node_modules" not in shortcut_dir:
        raise ValueError(
            f"ags_platform_shortcut_dir must be a node_modules dir; got "
            f"{shortcut_dir!r}"
        )
    shortcut = str(data.get("ags_platform_shortcut", ""))
    if not shortcut.endswith("/ags-platform"):
        raise ValueError(
            f"ags_platform_shortcut must be named `ags-platform` so the bare "
            f"specifier resolves; got {shortcut!r}"
        )

    tasks = tasks_path.read_text()
    if "ags_platform_unit_dir" not in tasks or "ags_platform_repo_url" not in tasks:
        raise ValueError(
            f"{PLATFORM_ROLE_TASKS} does not clone the pinned unit into ags_platform_unit_dir"
        )
    if "ags_platform_shortcut" not in tasks:
        raise ValueError(
            f"{PLATFORM_ROLE_TASKS} does not create the shared-ancestor shortcut"
        )


def assert_no_per_file_bar_skeletons(deployed: set[str]) -> None:
    """The bridge is retired: no per-file bar entry may remain in the manifest.

    `deployed` holds the manifest's bar-bridge sources (AGS-relative paths).
    Every one of them would template INTO the unit tree through the live-bar
    link — a stale entry silently diverges the live bar from the pinned tag
    on every provision — so the set must be EMPTY.
    """
    if deployed:
        stale = sorted(deployed)
        raise ValueError(
            f"the bar deploys WHOLE via the ags_apps unit symlink, but "
            f"{len(stale)} per-file bar source(s) remain in "
            f"compositor_configs_skeleton_files: dotfiles/config/ags/{stale[0]}"
            + (f" (+{len(stale) - 1} more)" if len(stale) > 1 else "")
            + " — delete them; the bridge is retired as a deploy source"
        )


def assert_bar_provisioning(root: Path) -> None:
    """The external bar unit + live link + resolution shortcut must be provisioned.

    The live bar IS the pinned unit's bar/ subdir (no per-file copy can drift),
    so the gate cannot diff a manifest against the closure — instead it asserts
    the SHAPE of the provisioning that deploys it whole (mirror of
    assert_platform_provisioning):
    - the ags_apps role declares the unit (repo URL + tag pin),
    - the unit is versioned by directory under <install>/ags-apps/,
    - the bar subdir (the monorepo deviation) names the package,
    - the live-bar link deploys it at <install>/config/ags,
    - the per-unit node_modules shortcut resolves the bar's own
      bare-specifier platform imports (esbuild realpaths the live-bar link,
      so the shared-ancestor shortcut is not an ancestor of the real tree).
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the bar deploys as the external {BAR_PACKAGE!r} unit but "
            f"no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the bar role has no tasks to install the unit: {BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    version = data.get("ags_apps_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(
            f"{BAR_ROLE_VARS} does not pin ags_apps_version — the unit "
            f"must be versioned by directory (spine AD-23)"
        )
    if not str(version).startswith("bar-"):
        raise ValueError(
            f"ags_apps_version {version!r} names no bar release — tags are "
            f"per-app releases (e.g. bar-v0.1.0); got {version!r}"
        )

    install_root = str(data.get("ags_apps_install_root", ""))
    if not ("install_dir" in install_root and "ags-apps" in install_root):
        raise ValueError(
            f"ags_apps_install_root must be <install>/ags-apps; got "
            f"{install_root!r}"
        )

    unit = str(data.get("ags_apps_unit_dir", ""))
    if "ags_apps_version" not in unit:
        raise ValueError(
            f"ags_apps_unit_dir must version the unit by directory "
            f"(ags_apps_version); got {unit!r}"
        )

    bar_dir = str(data.get("ags_apps_bar_dir", ""))
    if not bar_dir.endswith("/bar"):
        raise ValueError(
            f"ags_apps_bar_dir must be the unit's bar/ subdir (the monorepo "
            f"deviation — the repo root is not the package); got {bar_dir!r}"
        )

    live = str(data.get("ags_apps_live_bar_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate (an implementation detail) and names `ags`.
    if "spine_config_dir" not in live or not live.endswith("/ags"):
        raise ValueError(
            f"ags_apps_live_bar_link must deploy the unit as the live "
            f"<install>/config/ags; got {live!r}"
        )

    resolution_dir = str(data.get("ags_apps_resolution_dir", ""))
    if "node_modules" not in resolution_dir:
        raise ValueError(
            f"ags_apps_resolution_dir must be a node_modules dir; got "
            f"{resolution_dir!r}"
        )
    resolution = str(data.get("ags_apps_resolution_shortcut", ""))
    # Shape, not the exact Jinja string: the shortcut routes through the
    # resolution-dir intermediate and names `ags-platform`.
    if "ags_apps_resolution_dir" not in resolution or not resolution.endswith(
        "/ags-platform"
    ):
        raise ValueError(
            f"ags_apps_resolution_shortcut must be a per-unit node_modules "
            f"shortcut named `ags-platform` so the realpathed bar resolves "
            f"the bare specifier; got {resolution!r}"
        )

    tasks = tasks_path.read_text()
    if "ags_apps_unit_dir" not in tasks or "ags_apps_repo_url" not in tasks:
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not clone the pinned unit into ags_apps_unit_dir"
        )
    if "ags_apps_live_bar_link" not in tasks:
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the live-bar link"
        )
    if "ags_apps_resolution_shortcut" not in tasks:
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not create the per-unit resolution shortcut"
        )


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
        # The in-place platform copy is gone: assert the tree really has no
        # platform dir, so a re-introduced relative import cannot pass by
        # pointing at a file that still happens to exist.
        if (root / RETIRED_PLATFORM_DIR).exists():
            raise ValueError(
                f"the retired in-place platform copy still exists at "
                f"{RETIRED_PLATFORM_DIR}/ — the bar must consume the external "
                f"unit (spine AD-17), not a vendored copy"
            )
        # The bar bridge is retired: the skeleton list must carry no per-file
        # bar source (a stale one templates into the unit tree through the
        # live-bar link). The remaining `deployed` entries are non-bar
        # skeletons (hypr/hyprpaper/rofi) — reported, not diffed.
        assert_no_per_file_bar_skeletons(deployed)
        assert_platform_provisioning(root)
        assert_bar_provisioning(root)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}")
        return 1

    reachable = {path.relative_to(ags_dir).as_posix() for path in closure}

    print(
        f"deploy-coverage: reachable AGS modules from {AGS_DIR}/{ENTRY}: "
        f"{len(reachable)} (deployed WHOLE via the {BAR_PACKAGE!r} unit symlink "
        f"— covered by the unit assertion below, not diffed per file)"
    )
    print(f"deploy-coverage: per-file non-bar sources in the manifest: {len(deployed)}")
    print(
        f"deploy-coverage: external bare specifier {PLATFORM_PACKAGE!r} — unit + "
        f"shared-ancestor shortcut provisioned (not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external bar unit {BAR_PACKAGE!r} — pinned unit + "
        f"live-bar link + per-unit resolution shortcut provisioned "
        f"(not a per-file deploy)"
    )

    print(
        "deploy-coverage: PASS -- the retired bar bridge carries no per-file "
        "deploy source and both external units are provisioned"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
