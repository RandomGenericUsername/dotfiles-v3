#!/usr/bin/env python3
"""deploy-coverage -- the provisioning shape of the final all-standalone AGS tree.

WHY THIS GATE EXISTS. The composition owns the single AGS app list and program
tuple, and the pinned engine owns the one installer/verify implementation. This
gate proves the two sides agree before a host is provisioned: a stale per-file
app source, a half-moved pin, a missing shared platform shortcut, or a legacy
owner would otherwise surface only on a fresh machine.

WHAT IT ASSERTS.

  (a) the pin set: `installer.pin` is read by `bootstrap.sh` (never repeated as
      a literal), the assets manifest/role/verify agree, every CLI manifest
      entry is mirrored by the pinned engine's `cli_tools`/verify roles, and the
      csg-templates source names the csg pin;
  (b) the pinned engine is the final all-standalone shape: no `ags_apps` role or
      playbook remains, `ags_platform` installs the tuple platform unit, and
      `ags_apps_units` (not cli_tools/gui_tools/config_links) owns the ONE
      `<install>/apps/node_modules/ags-platform` shortcut and every app surface;
  (c) the composition app list: all seven entries are `owner: standalone` with
      the released repo/tag, unique app/install/instance/config/spine/XDG
      surfaces, one bar palette pointer, and the final launcher/autostart/bin
      surfaces; the engine's seven-app fixture and verify mirror agree;
  (d) the one program tuple: contracts/ags-platform/dotfiles-assets are semver
      tags, the platform and assets roles/verify mirrors resolve the tuple, and
      a missing/extra/skewed tuple fails;
  (e) the committed app-list and tuple fixtures accept legacy/mixed/
      all-standalone lists and reject duplicate/owner/repo/tag violations; the
      pinned engine's fake-app cutover fixture (quiesce → install/start →
      verify → rollback) is present;
  (f) the static config, template, desktop and asset corpora are the pinned
      `dotfiles-assets` classes (no in-tree copy), and the retired in-repo
      source/engine/corpus roots are absent;
  (g) the terminal composition-only shape: `src/` is absent, `dotfiles/` holds
      `provisioning/`, and the retired runtime/CLI/GUI/provisioning roots are
      gone.

THE AGS APP GATE LIVES IN `scripts/ags_app_consumption.py`. It mirrors the
contracts v0.3.0 structural rules (draft-07 + `x-uniqueKeys`) because a stock
checkout has no contracts clone, exercises the fixtures, and checks the final
app list against the pinned engine's installer/verify/fixture shape. This gate
calls it after the core pin/corpus guards.

Usage: ``python3 scripts/deploy-coverage.py [--root REPO_ROOT]``. PyYAML is
required and a missing toolchain fails rather than skips; run it through
``uv run --no-project --with pyyaml python scripts/deploy-coverage.py``. The
pinned engine checkout is read from `dotfiles/provisioning/installer.pin`
(cached at `.dev/dotfiles-provision-<tag>/`), never from an in-repo copy.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

from ags_app_consumption import (
    APPS_MANIFEST,
    PROGRAM_TUPLE,
    run_checks as run_ags_app_consumption_checks,
)
from engine_checkout import EngineCheckoutError, engine_checkout, read_engine_pin

# The pinned engine checkout, resolved once in main(). Every role constant below
# is relative to THAT root (the engine owns `ansible/`); composition-owned paths
# (`dotfiles/...`) stay relative to `root`.
_ENGINE_ROOT: Path | None = None


def engine_path(relative: str) -> Path:
    """Resolve an engine-relative path against the pinned checkout."""
    if _ENGINE_ROOT is None:
        raise RuntimeError("the pinned engine checkout was not resolved")
    return _ENGINE_ROOT / relative


VARS_FILE = "ansible/roles/compositor_configs/vars/main.yml"
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
PLATFORM_ROLE_VARS = "ansible/roles/ags_platform/vars/main.yml"
PLATFORM_ROLE_TASKS = "ansible/roles/ags_platform/tasks/main.yml"

# The retired in-place platform copy (extract-platform-in-place) lived here. It
# is deleted by this change; a surviving relative import into it would resolve
# to nothing and be silently skipped by `_resolve`, so it is REJECTED loudly.
RETIRED_PLATFORM_DIR = "dotfiles/config/ags/platform"

# The final all-standalone topology has ONE AGS installer: `ags_apps_units`.
# The retired `ags_apps` monorepo role/playbook and the per-app launcher/config
# ownership in cli_tools/gui_tools/config_links are asserted absent by the
# app-consumption gate (`scripts/ags_app_consumption.py`). The only deploy
# source left here is the in-repo GUI source root guard below.

# The in-repo GUI source ROOT itself is retired. Every app it used to hold now
# deploys WHOLE from the ags-apps unit, so the parent dir has no remaining
# purpose. The per-app constants above catch a known app reappearing; this one
# catches the dir coming back for ANY reason (a leftover, an unknown app, a
# stray file), so an empty `src/gui-tools/` can never quietly become a home for
# a second source of truth again.
RETIRED_GUI_TOOLS_DIR = "src/gui-tools"

# `cli-output` left the repo (cli-tools-repos S1): it is consumed from its
# pinned repo (`git = …/cli-output, tag = "v0.1.0"`) by the runtime, the
# provisioning package and the three CLIs. The in-tree package is retired, and
# a `path =` source would silently resurrect the local copy as the source of
# truth — exactly the drift the pin exists to prevent.
CLI_OUTPUT_PACKAGE = "cli-output"
RETIRED_CLI_OUTPUT_DIR = "src/shared/cli-output"

# `config-assembler-engine` left the repo (cli-tools-repos S2): csg, weg and itr
# consume it from its pinned repo (`git = …/config-assembler-engine, tag =
# "v0.1.0"`). The in-tree package is retired, and a `path =` source would
# silently resurrect the local copy as the source of truth — exactly the drift
# the pin exists to prevent. Same two-half shape as `cli-output` above.
CONFIG_ASSEMBLER_ENGINE_PACKAGE = "config-assembler-engine"
RETIRED_CONFIG_ASSEMBLER_ENGINE_DIR = "src/shared/config-assembler-engine"

# `oci-runtime` left the repo (cli-tools-repos S3): csg and weg consume it from
# its pinned repo (`git = …/oci-runtime, tag = "v0.5.0"`). It was the LAST
# in-repo shared library, so the parent `src/shared/` root is retired too —
# leaving it behind (even empty) would be an obvious home for a vendored copy
# that no consumer installs. Same two-half shape as S1/S2: the tree is gone and
# no package under `src/` may pin it by `path`.
OCI_RUNTIME_PACKAGE = "oci-runtime"
RETIRED_OCI_RUNTIME_DIR = "src/shared/oci-runtime"
RETIRED_SHARED_LIBS_DIR = "src/shared"

# `icon-templates-renderer` (console: `itr`) is the FIRST CLI consumed from its
# own pinned repo (cli-tools-repos S4): the manifest entry is
# `{name: itr, repo: …, tag: v0.2.0}`, no `source:` path, and the `cli_tools`
# role installs FROM a tag-bearing checkout at <install>/cli-tools/itr/<tag>/
# (AD-10) rather than from a `git+…@tag` URL. The in-tree package is retired in
# the same slice that proves the new wiring, so a surviving copy is a second
# source of truth that no consumer installs.
CLI_TOOLS_MANIFEST = "dotfiles/provisioning/cli-tools.yaml"
CLI_TOOLS_ROLE_TASKS = "ansible/roles/cli_tools/tasks/main.yml"
# The installer engine is a separate external pin (not a CLI tool): bootstrap
# installs the tool from this tag and both composition gates read that checkout.
INSTALLER_PIN = "dotfiles/provisioning/installer.pin"
# S7 (AD-4/AD-17): the composition pin set, validated as ONE set. The runtime
# is now the pinned `dotfiles-runtime` repo; its `[tool.uv.sources]` pins live
# there and are locked by its own gates. This repo authors no Python package,
# so it carries no library/contract pin. `bootstrap.sh` reads the installer pin
# file rather than repeating the tag.
BOOTSTRAP = "bootstrap.sh"
# S7 (AD-17 terminal): what a COMPOSITION repo may still author. `dotfiles/`
# carries the manifests and the one mutable preference (OPEN-5 / R-07); `src/`
# is absent (the runtime moved to its pinned repo). Everything else is a pin.
COMPOSITION_DOTFILES_ENTRIES = ("provisioning",)
RETIRED_ASSETS_DIR = "dotfiles/assets"
# S6b: the engine's Python package and Ansible tree are the pinned external
# `dotfiles-provision` repo; this root has no remaining purpose.
RETIRED_PROVISIONING_ROOT = "src/provisioning"
RETIRED_ICON_MAPPINGS_DIR = "dotfiles/config/icon-template-color-scheme-mappings"

# S4: the desktop entries and the repo-authored helper script moved to the same
# pinned `dotfiles-assets` repo (`desktop/` class, v0.5.0). `dotfiles/applications/`
# and `dotfiles/scripts/` are retired; the compositor_configs role reads
# <install>/assets/<tag>/desktop/{applications,scripts,desktop.yaml} and resolves
# the contract's requires/optional before it copies (spine AD-10 layer 2).
RETIRED_DESKTOP_DIRS = ("dotfiles/applications", "dotfiles/scripts")
DESKTOP_PIN_ROLE = "compositor_configs"

# S5 (AD-12): the pinned corpus's SHAPE. The manifest `assets:` block is the one
# source of truth for repo/tag/class map; the role and verify carry mirrors
# (Ansible does not read manifests) and this gate locks them together, so a pin
# bump or a widened schema window cannot land on one side only. The retired-path
# sweep below REUSES the S1–S4 constants — it adds no path literals, it only
# reports the five classes explicitly.
ASSETS_MANIFEST = "dotfiles/provisioning/assets.yaml"
ASSETS_ROLE_VARS = "ansible/roles/assets/vars/main.yml"
VERIFY_ROLE_VARS = "ansible/roles/verify/vars/main.yml"
ASSETS_CLASSES = ("icons", "templates", "configs", "content", "desktop")
_SEMVER_TAG = re.compile(r"^v\d+\.\d+\.\d+$")

# S2: the static config corpus moved to the pinned `dotfiles-assets` repo
# (configs/ class, v0.3.x). These five directories are gone; S3 retires the last
# two (`zsh/`, whose only file was the .zshrc template, and `wlogout/`, whose
# stylesheet source moved to the templates class while its `layout` already lives
# in the corpus). The byte contract is proven before each deletion; from here on a
# surviving copy is a second, unowned source of truth that no role reads.
RETIRED_STATIC_CONFIG_DIRS = (
    "dotfiles/config/hypr",
    "dotfiles/config/hyprpaper",
    "dotfiles/config/nvim",
    "dotfiles/config/rofi",
    "dotfiles/config/starship",
    # S3: the last two template sources left, so their directories go too.
    "dotfiles/config/zsh",
    "dotfiles/config/wlogout",
)
RETIRED_STATIC_CONFIG_FILES = (
    "dotfiles/config/wlogout/layout",
    # S3: the wlogout stylesheet SOURCE is a `templates` asset; a copy in the repo
    # (or in the spine, which the wlogout_config role prunes) is the residue this
    # slice removes.
    "dotfiles/config/wlogout/style.css.tpl",
)

# S3: the five rendering roles read their template bodies from the pinned corpus
# (`<install>/assets/<tag>/templates/…`). A role-internal `templates/` dir would be
# a second source of truth; the render task is the only place the path may appear,
# and it must be the pinned checkout.
TEMPLATE_RENDER_ROLES = {
    "zsh_config": 1,
    "kitty_config": 1,
    "btop_config": 1,
    "wlogout_config": 1,
    "display_manager": 2,
}
RETIRED_ROLE_TEMPLATE_DIRS = tuple(
    f"ansible/roles/{role}/templates" for role in TEMPLATE_RENDER_ROLES
)

# S5: the retired paths that belonged to each corpus class, sourced from the
# guard constants above (never re-typed). A class is covered when its retired
# tree/file is ABSENT; the sweep exists so one assets failure names the CLASS,
# not a bare path. The S1–S4 assertions still own the detailed messages.
ASSET_CLASS_RETIRED_PATHS = {
    "icons": (RETIRED_ASSETS_DIR, RETIRED_ICON_MAPPINGS_DIR),
    "templates": (
        RETIRED_STATIC_CONFIG_DIRS
        + RETIRED_ROLE_TEMPLATE_DIRS
        + RETIRED_STATIC_CONFIG_FILES
    ),
    "configs": RETIRED_STATIC_CONFIG_DIRS + RETIRED_STATIC_CONFIG_FILES,
    "content": (RETIRED_ASSETS_DIR,),
    "desktop": RETIRED_DESKTOP_DIRS,
}
CLI_TOOLS_ROLE_VARS = "ansible/roles/cli_tools/vars/main.yml"
RUNTIME_NAME = "dotfiles-runtime"
RETIRED_RUNTIME_DIR = "src/runtime"
ITR_NAME = "itr"
RETIRED_ITR_DIR = "src/cli-tools/icon-templates-renderer"
WEG_NAME = "weg"
RETIRED_WEG_DIR = "src/cli-tools/wallpaper-effects-generator"
CSG_NAME = "csg"
RETIRED_CSG_DIR = "src/cli-tools/color-scheme-generator"

# The terminal catch-all (cli-tools-repos S6): the LAST CLI left the repo, so
# the parent roots are retired. `src/cli-tools/` held the four in-tree trees
# (csg/weg/itr) plus the nested openspec root; `src/shared/` held the four
# shared libraries. A surviving parent (even empty) is an obvious home for a
# vendored copy that no consumer installs, so the presence of either is a gate
# failure regardless of what it contains.
RETIRED_CLI_TOOLS_DIR = "src/cli-tools"
# `src/shared/` is asserted by assert_no_in_tree_oci_runtime (S3); S6 restates
# it in the terminal catch-all so one gate run reports both parent roots.
CONTAINER_IMAGE_TAG_ENV_KEY = "COLORSCHEME__CONTAINER__IMAGE_TAG"

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
            f"uv run --no-project --with pyyaml python scripts/deploy-coverage.py"
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
    """The external platform unit must be provisioned, not assumed.

    Every AGS app imports `ags-platform` by bare specifier; nothing in the repo
    tree provides it (AD-17). The final topology installs the platform at
    `<install>/ags-platform/<version>/`; `ags_apps_units` owns the ONE
    `<install>/apps/node_modules/ags-platform` resolver. This role must not
    resurrect the retired `<install>/config/node_modules` shortcut (a second
    resolver for a tree that no longer lives under `<install>/config`).
    """
    import yaml

    vars_path = engine_path(PLATFORM_ROLE_VARS)
    tasks_path = engine_path(PLATFORM_ROLE_TASKS)
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

    pin_file = str(data.get("ags_platform_pin_file", ""))
    if not pin_file.endswith("/pinned"):
        raise ValueError(
            f"ags_platform_pin_file must record the installed tag beside the "
            f"unit tree; got {pin_file!r}"
        )

    if "ags_platform_shortcut" in data:
        raise ValueError(
            f"{PLATFORM_ROLE_VARS} still declares an `ags_platform_shortcut` — "
            f"the shared resolver belongs to `ags_apps_units` under "
            f"<install>/apps/node_modules (AD-31), not this role"
        )

    tasks = tasks_path.read_text()
    if "ags_platform_unit_dir" not in tasks or "ags_platform_repo_url" not in tasks:
        raise ValueError(
            f"{PLATFORM_ROLE_TASKS} does not clone the pinned unit into ags_platform_unit_dir"
        )
    if "ags_platform_shortcut" in tasks:
        raise ValueError(
            f"{PLATFORM_ROLE_TASKS} still creates a platform shortcut; the one "
            f"shared resolver is owned by `ags_apps_units`"
        )


def assert_no_per_file_bar_skeletons(deployed: set[str]) -> None:
    """No per-file AGS source may remain in the compositor skeleton list.

    `deployed` holds the manifest's bar-bridge sources (AGS-relative paths).
    Every one of them would template INTO the standalone app tree through its
    live link — a stale entry silently diverges the deployed app from the pinned
    tag — so the set must be EMPTY.
    """
    if deployed:
        stale = sorted(deployed)
        raise ValueError(
            f"the bar deploys as the standalone ags-bar tag, but "
            f"{len(stale)} per-file bar source(s) remain in "
            f"compositor_configs_skeleton_files: dotfiles/config/ags/{stale[0]}"
            + (f" (+{len(stale) - 1} more)" if len(stale) > 1 else "")
            + " — delete them; the per-file bridge is retired as a deploy source"
        )


def assert_no_gui_tools_dir(root: Path) -> None:
    """The in-repo GUI source root is retired: it must not exist at all.

    The per-app checks above catch a known app name coming back. This one is
    the catch-all: every app now deploys WHOLE from the ags-apps unit, so
    `src/gui-tools/` itself has no remaining purpose. Leaving the directory
    behind — even empty — makes it the obvious place for the next in-repo
    source, which no gate would deploy but a reader could mistake for live.
    """
    if (root / RETIRED_GUI_TOOLS_DIR).exists():
        raise ValueError(
            f"the retired in-repo GUI source root {RETIRED_GUI_TOOLS_DIR}/ still "
            f"exists — every app deploys WHOLE from the ags-apps unit; delete "
            f"the directory (an empty leftover must not become a new home for "
            f"in-repo GUI sources)"
        )


def assert_no_in_tree_cli_output(root: Path) -> None:
    """`cli-output` is consumed from its pinned repo: no local copy, no path pin.

    cli-tools-repos S1 moved the package out of this repo (tag `v0.1.0`) and
    deleted `src/shared/cli-output/`. Both halves are asserted so neither can
    quietly come back:
      (a) the in-tree package dir must not exist — a surviving copy would be a
          second source of truth that no consumer installs; and
      (b) no package under `src/` may carry a `[tool.uv.sources]` entry that
          pins `cli-output` by `path` — that would resolve the local checkout
          instead of the tag while still passing an import.
    """
    retired = root / RETIRED_CLI_OUTPUT_DIR
    if retired.exists():
        raise ValueError(
            f"the retired in-tree {CLI_OUTPUT_PACKAGE!r} package still exists at "
            f"{RETIRED_CLI_OUTPUT_DIR}/ — it is consumed from its pinned repo "
            f"tag v0.1.0; delete the directory"
        )

    src = root / "src"
    if not src.is_dir():
        # No in-repo package remains; `assert_composition_only` owns the `src/`
        # absence. Nothing can carry a path pin.
        return
    for pyproject in sorted(src.rglob("pyproject.toml")):
        # Skip virtualenvs and any other hidden tree (e.g. .venv): only the
        # authored package manifests participate in the pin.
        if any(part.startswith(".") for part in pyproject.relative_to(root).parts):
            continue
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        source = (
            data.get("tool", {}).get("uv", {}).get("sources", {}).get(CLI_OUTPUT_PACKAGE)
        )
        if isinstance(source, dict) and "path" in source:
            raise ValueError(
                f"{pyproject.relative_to(root)} still pins {CLI_OUTPUT_PACKAGE!r} "
                f"by path ({source['path']!r}) — consume the pinned repo tag "
                f"(git = …, tag = v0.1.0) instead"
            )


def assert_no_in_tree_config_assembler_engine(root: Path) -> None:
    """`config-assembler-engine` is consumed from its pinned repo: no local copy.

    cli-tools-repos S2 moved the package out of this repo (tag `v0.1.0`) and
    deleted `src/shared/config-assembler-engine/`. Both halves are asserted so
    neither can quietly come back:
      (a) the in-tree package dir must not exist — a surviving copy would be a
          second source of truth that csg/weg/itr do not install; and
      (b) no package under `src/` may carry a `[tool.uv.sources]` entry that
          pins `config-assembler-engine` by `path` — that would resolve the
          local checkout instead of the tag while still passing an import.
    """
    retired = root / RETIRED_CONFIG_ASSEMBLER_ENGINE_DIR
    if retired.exists():
        raise ValueError(
            f"the retired in-tree {CONFIG_ASSEMBLER_ENGINE_PACKAGE!r} package "
            f"still exists at {RETIRED_CONFIG_ASSEMBLER_ENGINE_DIR}/ — it is "
            f"consumed from its pinned repo tag v0.1.0; delete the directory"
        )

    src = root / "src"
    if not src.is_dir():
        # No in-repo package remains; `assert_composition_only` owns the `src/`
        # absence. Nothing can carry a path pin.
        return
    for pyproject in sorted(src.rglob("pyproject.toml")):
        # Skip virtualenvs and any other hidden tree (e.g. .venv): only the
        # authored package manifests participate in the pin.
        if any(part.startswith(".") for part in pyproject.relative_to(root).parts):
            continue
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        source = (
            data.get("tool", {})
            .get("uv", {})
            .get("sources", {})
            .get(CONFIG_ASSEMBLER_ENGINE_PACKAGE)
        )
        if isinstance(source, dict) and "path" in source:
            raise ValueError(
                f"{pyproject.relative_to(root)} still pins "
                f"{CONFIG_ASSEMBLER_ENGINE_PACKAGE!r} by path "
                f"({source['path']!r}) — consume the pinned repo tag "
                f"(git = …, tag = v0.1.0) instead"
            )


def assert_no_in_tree_oci_runtime(root: Path) -> None:
    """`oci-runtime` is consumed from its pinned repo: no local copy, no path pin.

    cli-tools-repos S3 moved the package out of this repo (tag `v0.5.0`) and
    deleted `src/shared/oci-runtime/`. Three halves are asserted so none can
    quietly come back:
      (a) the in-tree package dir must not exist — a surviving copy would be a
          second source of truth that csg/weg do not install;
      (b) the parent `src/shared/` root must not exist — it was the last
          shared library, so an empty leftover must not become a new home for
          a vendored copy; and
      (c) no package under `src/` may carry a `[tool.uv.sources]` entry that
          pins `oci-runtime` by `path` — that would resolve the local checkout
          instead of the tag while still passing an import.
    """
    retired = root / RETIRED_OCI_RUNTIME_DIR
    if retired.exists():
        raise ValueError(
            f"the retired in-tree {OCI_RUNTIME_PACKAGE!r} package still exists at "
            f"{RETIRED_OCI_RUNTIME_DIR}/ — it is consumed from its pinned repo "
            f"tag v0.5.0; delete the directory"
        )

    shared = root / RETIRED_SHARED_LIBS_DIR
    if shared.exists():
        raise ValueError(
            f"the retired shared-library root {RETIRED_SHARED_LIBS_DIR}/ still "
            f"exists — every shared library is consumed from its pinned repo; "
            f"delete the directory (an empty leftover must not become a new "
            f"home for a vendored copy)"
        )

    src = root / "src"
    if not src.is_dir():
        # No in-repo package remains; `assert_composition_only` owns the `src/`
        # absence. Nothing can carry a path pin.
        return
    for pyproject in sorted(src.rglob("pyproject.toml")):
        # Skip virtualenvs and any other hidden tree (e.g. .venv): only the
        # authored package manifests participate in the pin.
        if any(part.startswith(".") for part in pyproject.relative_to(root).parts):
            continue
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        source = (
            data.get("tool", {}).get("uv", {}).get("sources", {}).get(OCI_RUNTIME_PACKAGE)
        )
        if isinstance(source, dict) and "path" in source:
            raise ValueError(
                f"{pyproject.relative_to(root)} still pins {OCI_RUNTIME_PACKAGE!r} "
                f"by path ({source['path']!r}) — consume the pinned repo tag "
                f"(git = …, tag = v0.5.0) instead"
            )


def _task_argv(task: object) -> list[str] | None:
    """The argv list of an Ansible task, or None when it is not argv-form.

    Reads the module body (`ansible.builtin.command` or the short `command`
    form) and returns the argv elements as strings, so a gate can assert the
    EXACT argv a task passes instead of pattern-matching the file text.
    """
    if not isinstance(task, dict):
        return None
    for module in ("ansible.builtin.command", "command"):
        body = task.get(module)
        if isinstance(body, dict) and isinstance(body.get("argv"), list):
            return [str(item) for item in body["argv"]]
    return None


def assert_cli_provisioned_from_pinned_manifest(
    root: Path,
    name: str,
    retired_dir: str,
    slice_label: str,
    tag_env_key: str | None = None,
) -> None:
    """One CLI is provisioned from its pinned repo, never a local path.

    cli-tools-repos moved the CLIs out of this repo one slice at a time
    (`itr` in S4, `weg` in S5, `csg` in S6). This gate asserts the SHAPE of the
    consumption for ONE entry, since the host assertions live in `verify`
    (AD-11):
      (a) the manifest entry is `{name, repo, tag}` — a repo and tag are
          present and there is NO `source:` path (a source would silently
          resolve the local checkout in one consumer while others use the tag);
      (b) the role mirror in `vars/main.yml` carries the same repo/tag and
          installs from the tag-qualified checkout root;
      (c) the role tasks address the tag-bearing checkout path
          (`<install>/cli-tools/<name>/<tag>`) and never a `git+…@tag` URL —
          AD-10 requires the installed tool's PEP 610 record to be a path that
          names the tag;
      (d) the retired in-tree package dir does not exist.
    """
    import yaml

    manifest_path = root / CLI_TOOLS_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"{CLI_TOOLS_MANIFEST} is missing")
    data = yaml.safe_load(manifest_path.read_text())
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"{CLI_TOOLS_MANIFEST} has no `entries` list")
    by_name = {
        str(entry.get("name")): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("name")
    }
    entry = by_name.get(name)
    if entry is None:
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST} has no {name!r} entry — the CLI "
            f"is consumed from its pinned repo; re-add it as {{name, repo, tag}}"
        )
    if "source" in entry:
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST} still provisions {name!r} from a source "
            f"path ({entry['source']!r}) — it must carry repo+tag and install "
            f"from the tag-bearing checkout (spine AD-10)"
        )
    if not str(entry.get("repo") or "").strip() or not str(entry.get("tag") or "").strip():
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST} entry {name!r} must carry BOTH repo and "
            f"tag (spine AD-10); got repo={entry.get('repo')!r} tag={entry.get('tag')!r}"
        )
    tag = str(entry["tag"]).strip()

    role_vars_path = engine_path(CLI_TOOLS_ROLE_VARS)
    if not role_vars_path.is_file():
        raise ValueError(f"{CLI_TOOLS_ROLE_VARS} is missing")
    role_vars = yaml.safe_load(role_vars_path.read_text())
    role_entries = role_vars.get("cli_tools") if isinstance(role_vars, dict) else None
    role_entry = next(
        (
            role
            for role in role_entries or []
            if isinstance(role, dict) and role.get("name") == name
        ),
        None,
    )
    if role_entry is None:
        raise ValueError(f"{CLI_TOOLS_ROLE_VARS} has no {name!r} cli_tools entry")
    if "source" in role_entry:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_VARS} still provisions {name!r} from a source "
            f"path ({role_entry['source']!r}) — role and manifest must agree on "
            f"the pinned shape"
        )
    if (
        str(role_entry.get("repo") or "").strip() != str(entry["repo"]).strip()
        or str(role_entry.get("tag") or "").strip() != tag
    ):
        raise ValueError(
            f"{CLI_TOOLS_ROLE_VARS} {name!r} pin ({role_entry.get('repo')!r}, "
            f"{role_entry.get('tag')!r}) does not mirror {CLI_TOOLS_MANIFEST} "
            f"({entry.get('repo')!r}, {tag!r})"
        )
    checkout_root = str(role_vars.get("cli_tools_checkout_root", ""))
    if "install_dir" not in checkout_root or not checkout_root.endswith("/cli-tools"):
        raise ValueError(
            f"{CLI_TOOLS_ROLE_VARS} cli_tools_checkout_root must be "
            f"<install>/cli-tools (spine AD-10); got {checkout_root!r}"
        )

    tasks_path = engine_path(CLI_TOOLS_ROLE_TASKS)
    if not tasks_path.is_file():
        raise ValueError(f"{CLI_TOOLS_ROLE_TASKS} is missing")
    tasks_text = tasks_path.read_text()
    for fragment in (
        "{{ cli_tools_checkout_root }}/{{ item.name }}/{{ item.tag }}",
        "{{ item.item.tag }}",
        "pinned",
    ):
        if fragment not in tasks_text:
            raise ValueError(
                f"{CLI_TOOLS_ROLE_TASKS} does not reference {fragment!r} — the "
                f"role must clone at the pinned tag and install from the "
                f"tag-bearing checkout (spine AD-10)"
            )
    for line in tasks_text.splitlines():
        stripped = line.lstrip()
        if "uv tool install" not in stripped or stripped.startswith("#"):
            continue
        if "git+" in stripped:
            raise ValueError(
                f"{CLI_TOOLS_ROLE_TASKS} installs from a git+…@tag URL — the "
                f"tool must be installed FROM the tag-bearing checkout so PEP "
                f"610 records a path that names the tag (spine AD-10)"
            )

    # AD-7: for a container-mode pinned CLI the image tag is the pin, never
    # `latest`. `verify` asserts the image exists at the tag-qualified
    # reference; this asserts the BUILD is what tags it that way, so the
    # rendered settings and the built image cannot disagree about the tag.
    image_builds = [
        argv
        for argv in (_task_argv(task) for task in yaml.safe_load(tasks_text) or [])
        if argv is not None and "--image-tag" in argv
    ]
    if not image_builds:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} has no image build passing --image-tag — "
            f"a pinned container-mode CLI must be built at the pin, never at "
            f"the CLI default `latest` (spine AD-7)"
        )
    for argv in image_builds:
        built_tag = argv[argv.index("--image-tag") + 1 :][:1]
        if built_tag != ["{{ item.tag }}"]:
            raise ValueError(
                f"{CLI_TOOLS_ROLE_TASKS} builds an image tagged {built_tag} — "
                f"the tag must be the manifest pin (`--image-tag "
                f"{{{{ item.tag }}}}`), never a literal such as `latest` "
                f"(spine AD-7)"
            )
        if argv[argv.index("--context") + 1 :][:1] != [
            "{{ cli_tools_checkout_root }}/{{ item.name }}/{{ item.tag }}"
        ]:
            raise ValueError(
                f"{CLI_TOOLS_ROLE_TASKS} builds a pinned image from the wrong "
                f"context — it must build from the tag-qualified checkout "
                f"(spine AD-5/AD-10)"
            )

    retired = root / retired_dir
    if retired.exists():
        raise ValueError(
            f"the retired in-tree {name!r} package still exists at "
            f"{retired_dir}/ — it is consumed from its pinned repo tag "
            f"{tag}; delete the directory (cli-tools-repos {slice_label})"
        )

    if tag_env_key is None:
        return

    # AD-7 for a CLI whose build verb takes the tag from SETTINGS ENV instead
    # of argv (csg and tpr have no `--image-tag`). The engine resolves the
    # per-tool env key from `cli_tools_image_tag_env_keys` and always writes
    # `{{ item.tag }}`; the build still uses the tag-qualified checkout as its
    # context (csg on argv, tpr through its source-root env).
    task_code = "\n".join(
        line for line in tasks_text.splitlines() if not line.lstrip().startswith("#")
    )
    if tag in task_code:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} contains the literal image tag {tag!r} in a "
            f"task — the tag must come from the manifest pin (`{{{{ item.tag }}}}`) "
            f"so a pin bump reaches the build (spine AD-7)"
        )

    env_keys = role_vars.get("cli_tools_image_tag_env_keys")
    if not isinstance(env_keys, dict) or env_keys.get(name) != tag_env_key:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_VARS}: cli_tools_image_tag_env_keys must map "
            f"{name!r} to {tag_env_key!r}; got {env_keys!r}"
        )
    if not any(
        token in tasks_text
        for token in (
            "cli_tools_image_tag_env_builds",
            "cli_tools_image_tag_env_context_builds",
        )
    ):
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} has no env-tag image build loop for "
            f"{name!r} — the pinned image would never be built at the manifest "
            f"tag (spine AD-7)"
        )
    if "cli_tools_image_tag_env_keys[item.name]: item.tag" not in tasks_text:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} does not pass the per-tool env key as "
            f"`{{{{ item.tag }}}}` — a literal/default tag could ship `latest`"
        )
    if name == "csg" and (
        "{{ cli_tools_checkout_root }}/{{ item.name }}/{{ item.tag }}" not in tasks_text
    ):
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} lost the tag-qualified build context for "
            f"{name!r} (spine AD-5/AD-10)"
        )


def assert_csg_provisioned_from_pinned_manifest(root: Path) -> None:
    """cli-tools-repos S6: `csg` (palette generator) is consumed from its pin.

    csg is the LAST extracted CLI and the second container-mode one. Its
    `install` verb has no `--image-tag`, so the AD-7 assertion follows the
    SETTINGS-ENV transport (`COLORSCHEME__CONTAINER__IMAGE_TAG`) instead of
    argv — same pin, same tag-qualified build context.
    """
    assert_cli_provisioned_from_pinned_manifest(
        root,
        CSG_NAME,
        RETIRED_CSG_DIR,
        "S6",
        tag_env_key=CONTAINER_IMAGE_TAG_ENV_KEY,
    )


def assert_no_cli_tools_dir(root: Path) -> None:
    """cli-tools-repos S6 (terminal): both retired package roots are absent.

    Every compute-provider CLI is consumed from its pinned repo and every
    shared library from its pinned repo, so `src/cli-tools/` and `src/shared/`
    have no remaining purpose. The per-package assertions above catch a known
    package reappearing; this catches the PARENT coming back for any reason (a
    leftover, an unknown package, a vendored copy), because an empty
    `src/cli-tools/` is exactly the shape that invites one.
    """
    for retired in (RETIRED_CLI_TOOLS_DIR, RETIRED_SHARED_LIBS_DIR):
        if (root / retired).exists():
            raise ValueError(
                f"the retired package root {retired}/ still exists — every CLI "
                f"tool and shared library is consumed from its pinned repo "
                f"(spine AD-10); delete the directory"
            )


def assert_no_assets_corpus(root: Path) -> None:
    """S1 (AD-16 catch-all): the icons/content corpus is not authored here.

    `dotfiles/assets/` held the icon templates, the wallpaper archive and the
    authored btop themes; `dotfiles/config/icon-template-color-scheme-mappings/`
    held the icon mappings. All of it now ships in the pinned `dotfiles-assets`
    repo (v0.2.0) and deploys from `<install>/assets/<tag>/`. A leftover copy
    would be a second, unowned source of truth — exactly the drift the pin
    exists to prevent — so its return fails this gate.
    """
    for retired in (RETIRED_ASSETS_DIR, RETIRED_ICON_MAPPINGS_DIR):
        if (root / retired).exists():
            raise ValueError(
                f"the retired asset tree {retired}/ still exists — the icons and "
                f"content corpus is the pinned dotfiles-assets repo (spine AD-6); "
                f"delete the in-tree copy and bump the pin instead"
            )


def assert_no_in_tree_static_configs(root: Path) -> None:
    """S2 (AD-16): the static config corpus is not authored here.

    `dotfiles/config/{hypr,hyprpaper,nvim,rofi,starship}/` and
    `dotfiles/config/wlogout/layout` (25 files) now ship in the pinned
    `dotfiles-assets` repo (v0.3.x, `configs/` class); the compositor_configs and
    config_copies roles read `<install>/assets/<tag>/configs/`. A leftover copy
    would be a second, unowned source of truth — exactly the drift the pin exists
    to prevent — so its return fails this gate.

    `dotfiles/config/wlogout/` is retired at S3: its only remaining file was the
    Jinja source, and that moved to the assets `templates` class with the rest.
    The guard therefore rejects the directory now, not just the copied `layout`.
    """
    for retired in RETIRED_STATIC_CONFIG_DIRS:
        if (root / retired).exists():
            raise ValueError(
                f"the retired static config tree {retired}/ still exists — the "
                f"static config corpus is the pinned dotfiles-assets repo "
                f"(configs class, S2/AD-6); delete the in-tree copy and bump the "
                f"pin instead"
            )
    for retired in RETIRED_STATIC_CONFIG_FILES:
        if (root / retired).exists():
            raise ValueError(
                f"the retired static config file {retired} still exists — the "
                f"copied config corpus and its templates now ship in the pinned "
                f"dotfiles-assets repo (configs + templates classes, S2/S3)"
            )


def assert_no_in_tree_templates(root: Path) -> None:
    """S3 (AD-8/AD-16): template bodies and their sources live in the corpus.

    Two halves, because a split can fail in two directions:

    * the RETIRED sources are gone — `dotfiles/config/{zsh,wlogout}` and the three
      role-internal `templates/` dirs. A surviving copy is a second source of truth
      that no role reads (the render tasks point at the pinned checkout).
    * every render task that DOES remain reads the pinned checkout: each of the
      five roles has the declared number of `ansible.builtin.template` tasks, each
      `src:` resolves through `<role>_assets_templates_dir` (which itself resolves
      `<install>/assets/<role>_assets_pinned_tag>/templates`), and each role carries
      that pin mirror. This is the CI-runnable half of AD-8.4: the required-var
      parity test needs the corpus to read the schemas, so it skips on a runner
      without a checkout; this assertion needs only this repo and never skips.
    """
    for retired in RETIRED_STATIC_CONFIG_DIRS:
        if (root / retired).exists():
            raise ValueError(
                f"the retired template source {retired}/ still exists — the Jinja "
                f"corpus ships in the pinned dotfiles-assets repo (templates class, "
                f"S3) and the roles read <install>/assets/<tag>/templates/; delete "
                f"the in-tree copy and bump the pin instead"
            )
    for retired in RETIRED_ROLE_TEMPLATE_DIRS:
        if engine_path(retired).exists():
            raise ValueError(
                f"the retired role-internal template dir {retired}/ still exists "
                f"in the pinned engine — the corpus ships in dotfiles-assets "
                f"(templates class, S3); a role-local templates/ dir is a second "
                f"source of truth"
            )
    for retired in RETIRED_STATIC_CONFIG_FILES:
        if (root / retired).exists():
            raise ValueError(
                f"the retired template source {retired} still exists — wlogout's only "
                f"in-repo source is the corpus copy (templates/wlogout/style.css.tpl); "
                f"delete it"
            )

    import yaml

    keys = {"name", "when", "become", "become_user", "become_method", "become_flags", "args",
            "register", "changed_when", "failed_when", "creates", "vars", "loop", "until",
            "retries", "delay", "tags", "environment", "ignore_errors", "notify", "check_mode"}
    for role, expected in TEMPLATE_RENDER_ROLES.items():
        role_dir = engine_path(f"ansible/roles/{role}")
        tasks_path = role_dir / "tasks" / "main.yml"
        vars_path = role_dir / "vars" / "main.yml"
        if not tasks_path.is_file() or not vars_path.is_file():
            raise ValueError(f"role {role}: tasks/main.yml or vars/main.yml is missing")
        role_vars = yaml.safe_load(vars_path.read_text()) or {}
        templates_dir = role_vars.get(f"{role}_assets_templates_dir")
        pin = role_vars.get(f"{role}_assets_pinned_tag")
        if templates_dir != (
            f"{{{{ install_dir | trim }}}}/assets/{{{{ {role}_assets_pinned_tag }}}}/templates"
        ):
            raise ValueError(
                f"role {role}: {role}_assets_templates_dir must resolve "
                f"<install>/assets/<{role}_assets_pinned_tag>/templates; got "
                f"{templates_dir!r}"
            )
        if not str(pin or "").startswith("v"):
            raise ValueError(
                f"role {role}: {role}_assets_pinned_tag must be a vX.Y.Z pin mirror of "
                f"assets.tag; got {pin!r}"
            )
        tasks = yaml.safe_load(tasks_path.read_text()) or []
        renders = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            module = next((k for k in task if k not in keys and k != "with_items"), None)
            if module == "ansible.builtin.template":
                renders.append(task)
        if len(renders) != expected:
            raise ValueError(
                f"role {role}: expected {expected} ansible.builtin.template task(s); found "
                f"{len(renders)} — a render task that disappeared would leave the "
                f"spine file stale, and a new one must be counted here"
            )
        prefix = f"{{{{ {role}_assets_templates_dir }}}}/"
        for task in renders:
            src = str((task.get("ansible.builtin.template") or {}).get("src", ""))
            if not src.startswith(prefix):
                raise ValueError(
                    f"role {role}: render task {task.get('name')!r} must read "
                    f"`{prefix}<group>/<file>` from the pinned corpus; got {src!r}. A "
                    f"bare file name resolves inside the role's own templates/ dir "
                    f"(retired in S3), so the render would fail on a provision."
                )


def assert_no_in_tree_desktop_corpus(root: Path) -> None:
    """S4 (AD-10/AD-16): the desktop entries and the helper script are corpus data.

    Two halves, because a split can fail in two directions:

    * the RETIRED sources are gone — `dotfiles/applications/` and
      `dotfiles/scripts/`. A surviving copy is a second source of truth no role
      reads (the deploy reads the pinned checkout), and it is exactly the drift
      the pin exists to prevent.
    * the role that deploys them reads the PINNED class and resolves the contract
      before it copies: the pin mirror is a `vX.Y.Z`, the desktop dir resolves
      `<install>/assets/<pin>/desktop`, the layer-2 tasks (contract slurp + parse,
      a `command -v` probe, the required-binary assert, the optional-skip report)
      come before the copy, the entry copy's `src` is the pinned `applications/`
      dir, and the helper script's source is the pinned `scripts/` dir. This half
      is CI-runnable: it needs only this repo, so it never skips.
    """
    for retired in RETIRED_DESKTOP_DIRS:
        if (root / retired).exists():
            raise ValueError(
                f"the retired desktop tree {retired}/ still exists — the desktop "
                f"entries and helper scripts are the pinned dotfiles-assets repo "
                f"(desktop class, S4/AD-10); delete the in-tree copy and bump the "
                f"pin instead"
            )

    import yaml

    role_dir = engine_path(f"ansible/roles/{DESKTOP_PIN_ROLE}")
    vars_path = role_dir / "vars" / "main.yml"
    tasks_path = role_dir / "tasks" / "main.yml"
    if not vars_path.is_file() or not tasks_path.is_file():
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: tasks/main.yml or vars/main.yml is missing"
        )
    role_vars = yaml.safe_load(vars_path.read_text()) or {}
    pin = role_vars.get(f"{DESKTOP_PIN_ROLE}_assets_pinned_tag")
    if not str(pin or "").startswith("v"):
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: {DESKTOP_PIN_ROLE}_assets_pinned_tag must be a "
            f"vX.Y.Z pin mirror of assets.tag; got {pin!r}"
        )
    desktop_dir = role_vars.get(f"{DESKTOP_PIN_ROLE}_assets_desktop_dir")
    expected_dir = (
        "{{ install_dir | trim }}/assets/"
        f"{{{{ {DESKTOP_PIN_ROLE}_assets_pinned_tag }}}}/desktop"
    )
    if desktop_dir != expected_dir:
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: {DESKTOP_PIN_ROLE}_assets_desktop_dir must "
            f"resolve <install>/assets/<pin>/desktop; got {desktop_dir!r}"
        )
    contract = role_vars.get(f"{DESKTOP_PIN_ROLE}_desktop_contract_file")
    if contract != f"{{{{ {DESKTOP_PIN_ROLE}_assets_desktop_dir }}}}/desktop.yaml":
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: the desktop contract must be read beside the "
            f"pinned class (…/desktop.yaml); got {contract!r}"
        )

    entries = role_vars.get(f"{DESKTOP_PIN_ROLE}_desktop_entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: {DESKTOP_PIN_ROLE}_desktop_entries must list the "
            f"deployed entries"
        )
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "file", "dest"}:
            raise ValueError(
                f"role {DESKTOP_PIN_ROLE}: desktop entry {entry!r} must carry exactly "
                f"{{name, file, dest}} — the source is the pinned class, never a repo path"
            )
        if not str(entry["file"]).endswith(".desktop"):
            raise ValueError(
                f"role {DESKTOP_PIN_ROLE}: desktop entry {entry['name']!r} `file` must be "
                f"a *.desktop name; got {entry['file']!r}"
            )
        if "{{ compositor_configs_xdg_data_home }}/applications/" not in str(entry["dest"]):
            raise ValueError(
                f"role {DESKTOP_PIN_ROLE}: desktop entry {entry['name']!r} must deploy to "
                f"<XDG data>/applications/; got {entry['dest']!r}"
            )
    scripts = role_vars.get(f"{DESKTOP_PIN_ROLE}_bin_scripts")
    if not isinstance(scripts, list) or not scripts:
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: {DESKTOP_PIN_ROLE}_bin_scripts must list the helper "
            f"scripts"
        )
    for script in scripts:
        if not isinstance(script, dict):
            raise ValueError(f"role {DESKTOP_PIN_ROLE}: bin script {script!r} is not a mapping")
        source = str(script.get("source", ""))
        if not source.startswith(
            f"{{{{ {DESKTOP_PIN_ROLE}_assets_desktop_dir }}}}/scripts/"
        ):
            raise ValueError(
                f"role {DESKTOP_PIN_ROLE}: bin script {script.get('name')!r} must read the "
                f"pinned desktop class's scripts/ dir; got {source!r}"
            )

    tasks = yaml.safe_load(tasks_path.read_text()) or []
    names = [str(task.get("name")) for task in tasks if isinstance(task, dict)]
    required_tasks = (
        "Parse the desktop class contract",
        "Assert the contract and this role describe the same desktop entries",
        "Assert every required desktop-entry binary is installed",
        "Report desktop entries skipped for a missing optional binary",
        "Install application desktop entry overrides",
        "Install desktop helper scripts (touchpad toggle for XF86 binds)",
    )
    missing_tasks = [name for name in required_tasks if name not in names]
    if missing_tasks:
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: layer-2/layer-3 desktop tasks are missing: "
            f"{missing_tasks} — a deployed entry whose binaries were never resolved is "
            f"the dead-menu-entry defect AD-10 exists for"
        )
    copy_index = names.index("Install application desktop entry overrides")
    for before in required_tasks[:4]:
        if names.index(before) > copy_index:
            raise ValueError(
                f"role {DESKTOP_PIN_ROLE}: {before!r} must run BEFORE the desktop entry "
                f"copy — resolving after a copy leaves a dead entry on disk"
            )
    copy_task = next(
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("name") == "Install application desktop entry overrides"
    )
    copy_src = str((copy_task.get("ansible.builtin.copy") or {}).get("src", ""))
    if copy_src != (
        "{{ compositor_configs_assets_desktop_dir }}/applications/{{ item.file }}"
    ):
        raise ValueError(
            f"role {DESKTOP_PIN_ROLE}: the desktop entry copy must read the pinned "
            f"class's applications/ dir; got {copy_src!r}"
        )


def assert_assets_shape(root: Path) -> tuple[str, tuple[str, ...]]:
    """S5 (AD-12): the pinned corpus is consumed through ONE mirrored pin.

    Four things, all CI-runnable (this repo only, no checkout, no network):

    * the manifest `assets:` block carries a `repo` and a SEMVER `tag`, and names
      exactly the five class dirs with the schema-bearing ones declaring a
      contract (`configs`/`content` declare `null` — no schema to version);
    * the role mirror (`assets_repo` / `assets_pinned_tag` / `assets_classes`)
      and the verify mirror (`verify_assets_pinned_tag` / the five class dirs)
      agree with the manifest, so a pin bump cannot land on one side;
    * the AD-12 support window exists on BOTH sides, names exactly the
      schema-bearing classes, and is EQUAL — a widened window on one side would
      let the fetch accept a corpus verify rejects (or the reverse);
    * no per-class `source:` points back into this checkout's `dotfiles/` tree
      (the split's whole point: the corpus is the pin, not a repo path), and
      every retired corpus path is absent — reusing the S1–S4 guard constants so
      one assets failure names the CLASS.

    Returns ``(tag, classes)`` so the caller can print the pin and every class
    dir it just proved.
    """
    import yaml

    manifest_path = root / ASSETS_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"the assets manifest {ASSETS_MANIFEST} is missing")
    manifest = yaml.safe_load(manifest_path.read_text()) or {}
    block = manifest.get("assets") if isinstance(manifest, dict) else None
    if not isinstance(block, dict):
        raise ValueError(f"{ASSETS_MANIFEST} has no `assets:` mapping")
    repo = str(block.get("repo") or "").strip()
    tag = str(block.get("tag") or "").strip()
    if not repo:
        raise ValueError(f"{ASSETS_MANIFEST} `assets.repo` is empty")
    if not _SEMVER_TAG.fullmatch(tag):
        raise ValueError(
            f"{ASSETS_MANIFEST} `assets.tag` must be a semver tag (vX.Y.Z, never "
            f"`latest` or a branch); got {tag!r}"
        )
    classes = block.get("classes")
    if not isinstance(classes, dict) or set(classes) != set(ASSETS_CLASSES):
        got = sorted(classes) if isinstance(classes, dict) else classes
        raise ValueError(
            f"{ASSETS_MANIFEST} `assets.classes` must name exactly "
            f"{list(ASSETS_CLASSES)}; got {got!r}"
        )
    for name, entry in classes.items():
        if not isinstance(entry, dict) or entry.get("dest") != name:
            raise ValueError(
                f"{ASSETS_MANIFEST} class {name!r} must map to its own dir "
                f"(dest == {name!r}); got {entry!r}"
            )
    schema_bearing = {name for name, entry in classes.items() if entry.get("schema") is not None}
    schema_less = set(classes) - schema_bearing
    if schema_less != {"configs", "content"}:
        raise ValueError(
            f"{ASSETS_MANIFEST}: `configs` and `content` are the ONLY schema-less "
            f"classes (catalog.yaml: schema null); got schema-less={sorted(schema_less)}"
        )

    def _load_vars(relative: str) -> dict:
        path = engine_path(relative)
        if not path.is_file():
            raise ValueError(f"the role vars file {relative} is missing")
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{relative} is not a mapping")
        return data

    role_vars = _load_vars(ASSETS_ROLE_VARS)
    verify_vars = _load_vars(VERIFY_ROLE_VARS)
    if str(role_vars.get("assets_repo")) != repo:
        raise ValueError(
            f"{ASSETS_ROLE_VARS}: assets_repo {role_vars.get('assets_repo')!r} must "
            f"mirror {ASSETS_MANIFEST} `assets.repo` {repo!r}"
        )
    if str(role_vars.get("assets_pinned_tag")) != tag:
        raise ValueError(
            f"{ASSETS_ROLE_VARS}: assets_pinned_tag "
            f"{role_vars.get('assets_pinned_tag')!r} must mirror {tag!r}"
        )
    if role_vars.get("assets_classes") != classes:
        raise ValueError(
            f"{ASSETS_ROLE_VARS}: assets_classes must equal {ASSETS_MANIFEST} "
            f"`assets.classes` (pin bump edits both or the gate fails)"
        )
    if str(verify_vars.get("verify_assets_pinned_tag")) != tag:
        raise ValueError(
            f"{VERIFY_ROLE_VARS}: verify_assets_pinned_tag "
            f"{verify_vars.get('verify_assets_pinned_tag')!r} must mirror {tag!r}"
        )
    class_dirs = [str(item) for item in verify_vars.get("verify_assets_class_dirs") or []]
    expected_dirs = [
        f"{{{{ verify_assets_tag_dir }}}}/{name}" for name in ASSETS_CLASSES
    ]
    if class_dirs != expected_dirs:
        raise ValueError(
            f"{VERIFY_ROLE_VARS}: verify_assets_class_dirs must be the five class "
            f"dirs under the pinned tag; expected {expected_dirs}, got {class_dirs}"
        )

    support = role_vars.get("assets_schema_support")
    verify_support = verify_vars.get("verify_assets_schema_support")
    if not isinstance(support, dict) or set(support) != schema_bearing:
        raise ValueError(
            f"{ASSETS_ROLE_VARS}: assets_schema_support must name exactly the "
            f"schema-bearing classes {sorted(schema_bearing)}; got {support!r}"
        )
    if not all(isinstance(value, int) and value >= 1 for value in support.values()):
        raise ValueError(
            f"{ASSETS_ROLE_VARS}: every assets_schema_support value must be a "
            f"positive integer major; got {support!r}"
        )
    if support != verify_support:
        raise ValueError(
            f"the schema support windows disagree: {ASSETS_ROLE_VARS} has "
            f"{support!r}, {VERIFY_ROLE_VARS} has {verify_support!r} — the fetch "
            f"and verify must accept the same corpus"
        )

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{ASSETS_MANIFEST} has no `entries` list")
    for entry in entries:
        if not isinstance(entry, dict) or "source" not in entry:
            continue
        source = str(entry["source"])
        if "dotfiles/" in source or source.startswith("dotfiles"):
            raise ValueError(
                f"{ASSETS_MANIFEST} entry {entry.get('name')!r} source "
                f"{source!r} points into this checkout's dotfiles/ tree — the "
                f"corpus is the pinned assets repo, not a repo path"
            )
        if not (
            source.startswith("{{ install_dir | trim }}/assets/")
            or source.startswith("{{ install_dir | trim }}/cli-tools/")
        ):
            raise ValueError(
                f"{ASSETS_MANIFEST} entry {entry.get('name')!r} source "
                f"{source!r} must resolve under the install spine "
                f"(<install>/assets/ or a pinned cli checkout), never the repo"
            )
    for copy in role_vars.get("assets_copies") or []:
        source = str((copy or {}).get("source", ""))
        if not source.startswith("{{ assets_checkout_root }}/") or "dotfiles/" in source:
            raise ValueError(
                f"{ASSETS_ROLE_VARS}: copy {copy.get('name')!r} source {source!r} "
                f"must read the pinned assets checkout ({{{{ assets_checkout_root }}}}); "
                f"a dotfiles/ path would resurrect the retired in-repo corpus"
            )

    for schema_class, retired_paths in ASSET_CLASS_RETIRED_PATHS.items():
        for relative in retired_paths:
            # Role-internal template dirs live in the engine checkout; corpus
            # paths live in this composition checkout.
            candidate = (
                engine_path(relative)
                if relative in RETIRED_ROLE_TEMPLATE_DIRS
                else root / relative
            )
            if candidate.exists():
                raise ValueError(
                    f"the retired {schema_class} corpus path {relative} still exists "
                    f"— the {schema_class} class is the pinned dotfiles-assets repo "
                    f"(assets {tag}); delete the in-tree copy and bump the pin"
                )

    return tag, ASSETS_CLASSES


def assert_manifest_source_scope(root: Path) -> None:
    """The CLI manifest has ZERO local `source:` entries (REQ-002).

    Every entry — csg, weg, itr and dotfiles-runtime — is `{name, repo, tag}`.
    The runtime moved to its own pinned repo, so a `source:` on any entry is a
    local path one consumer would resolve while the others use the tag. The
    source-path install branch remains in the engine as an extension point, but
    its loop selects nothing.

    The installer engine is NOT a CLI-tool entry: it is a separate pin
    (`dotfiles/provisioning/installer.pin`) consumed by `bootstrap.sh` and the
    two composition gates. It must never be smuggled into this manifest as a
    `dotfiles-provision` tool, because that would give the engine two sources
    of truth and make `cli-tools.yaml` claim a tool the `cli_tools` role does
    not install.
    """
    import yaml

    pin_path = root / INSTALLER_PIN
    if not pin_path.is_file():
        raise ValueError(
            f"the installer pin {INSTALLER_PIN} is missing — the engine must be "
            f"consumed as a pinned external repo"
        )
    installer_tag = read_engine_pin(root)

    manifest_path = root / CLI_TOOLS_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"{CLI_TOOLS_MANIFEST} is missing")
    data = yaml.safe_load(manifest_path.read_text())
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{CLI_TOOLS_MANIFEST} has no `entries` list")

    for entry in entries:
        name = str(entry.get("name")) if isinstance(entry, dict) else ""
        if name == "dotfiles-provision" or "dotfiles-provision" in str(
            entry.get("repo") if isinstance(entry, dict) else ""
        ):
            raise ValueError(
                f"{CLI_TOOLS_MANIFEST} names the installer engine {name!r} — the "
                f"engine is pinned separately in {INSTALLER_PIN} "
                f"({installer_tag}) and is not a CLI tool entry"
            )

    source_entries = [e for e in entries if isinstance(e, dict) and "source" in e]
    if source_entries:
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST} must carry ZERO `source:` entries — the "
            f"runtime is the pinned dotfiles-runtime repo (REQ-002); found "
            f"{[(e.get('name'), e.get('source')) for e in source_entries]}"
        )

    for entry in entries:
        name = str(entry.get("name"))
        if "source" in entry:
            continue
        if not str(entry.get("repo") or "").strip() or not str(
            entry.get("tag") or ""
        ).strip():
            raise ValueError(
                f"{CLI_TOOLS_MANIFEST} entry {name!r} has neither a local "
                f"source nor BOTH repo and tag (spine AD-10); got "
                f"repo={entry.get('repo')!r} tag={entry.get('tag')!r}"
            )


def assert_pin_set(root: Path, assets_tag: str) -> tuple[str, dict[str, str]]:
    """S7 (AD-4/AD-17): every composition pin is a semver tag, and mirrored.

    The composition repo is the ONE place the pin set is declared, so it is the
    one place it can be validated as a set:

    * **installer engine** — `installer.pin` is the single source; `bootstrap.sh`
      reads that file (it must not repeat the tag as a literal, which would let
      a shell-side bump diverge from the one the Python gates read) and keeps
      its own semver shape check;
    * **palette producer** — `bootstrap.sh` selects `tpr` by default through the
      `RUNTIME_PALETTE_PRODUCER` provisioning input (the engine renders
      `producer.json`), and sets no ambient double-underscore variable;
    * **assets corpus** — the tag returned by :func:`assert_assets_shape`, which
      has already locked the manifest against the role + verify + per-consumer
      mirrors;
    * **CLIs** — every manifest entry, including `dotfiles-runtime`, is a
      semver tag mirrored by the pinned engine's `cli_tools` role vars AND by
      `verify` (`version`, tag-bearing checkout path, `pinned` record).
    * **csg-templates source** — the composition `assets.yaml` source path names
      the same csg tag as the CLI manifest. The engine role derives the live
      copy path from its own mirror, so a stale manifest path is a latent
      second pin that this gate rejects.

    This repo authors no `[tool.uv.sources]`; the runtime's library/contract
    pins live in `dotfiles-runtime` and are locked by its own gates.

    Returns ``(installer_tag, cli_tags)`` for the caller to print.
    """
    import yaml

    # 1. The installer engine: ONE pin file, read by shell and Python.
    installer_tag = read_engine_pin(root)
    bootstrap_path = root / BOOTSTRAP
    if not bootstrap_path.is_file():
        raise ValueError(f"{BOOTSTRAP} is missing — it is the fresh-machine entry point")
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    if INSTALLER_PIN not in bootstrap:
        raise ValueError(
            f"{BOOTSTRAP} does not read {INSTALLER_PIN} — the engine tag must "
            f"come from the one pin file, not a second declaration"
        )
    if installer_tag in bootstrap:
        raise ValueError(
            f"{BOOTSTRAP} names the engine tag {installer_tag!r} literally — "
            f"it must only read {INSTALLER_PIN}; a literal can diverge from the "
            f"tag both Python gates resolve"
        )
    if "[0-9]+\\.[0-9]+\\.[0-9]+" not in bootstrap:
        raise ValueError(
            f"{BOOTSTRAP} lost its semver shape check for {INSTALLER_PIN} — a "
            f"branch, `latest` or a SHA must fail in the shell too"
        )

    # 1b. The v3 cutover default: a normal bootstrap renders producer=tpr.
    # The runtime reads <install>/config/dotfiles-runtime/producer.json, which
    # the engine renders from this provisioning input. An explicit
    # RUNTIME_PALETTE_PRODUCER=csg remains the documented rollback.
    tpr_default = (
        'export RUNTIME_PALETTE_PRODUCER='
        '"${RUNTIME_PALETTE_PRODUCER:-tpr}"'
    )
    if tpr_default not in bootstrap:
        raise ValueError(
            f"{BOOTSTRAP} must select tpr by default with {tpr_default!r} — "
            f"otherwise a fresh bootstrap silently renders producer=csg"
        )
    if "RUNTIME__PALETTE__PRODUCER=" in bootstrap:
        raise ValueError(
            f"{BOOTSTRAP} sets the retired double-underscore "
            f"RUNTIME__PALETTE__PRODUCER variable — the runtime reads "
            f"producer.json, not ambient env"
        )

    # 2. The assets corpus tag (mirrors are already locked by assert_assets_shape).
    if not _SEMVER_TAG.fullmatch(assets_tag):
        raise ValueError(
            f"the assets pin must be a semver tag (vX.Y.Z); got {assets_tag!r}"
        )

    # 3. Every CLI: manifest tag == role mirror == verify mirror.
    manifest_path = root / CLI_TOOLS_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"{CLI_TOOLS_MANIFEST} is missing")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{CLI_TOOLS_MANIFEST} has no `entries` list")

    role_vars_path = engine_path(CLI_TOOLS_ROLE_VARS)
    verify_vars_path = engine_path(VERIFY_ROLE_VARS)
    for path, label in (
        (role_vars_path, CLI_TOOLS_ROLE_VARS),
        (verify_vars_path, VERIFY_ROLE_VARS),
    ):
        if not path.is_file():
            raise ValueError(f"the role vars file {label} is missing")
    role_vars = yaml.safe_load(role_vars_path.read_text(encoding="utf-8")) or {}
    verify_vars = yaml.safe_load(verify_vars_path.read_text(encoding="utf-8")) or {}
    role_by_name = {
        str(entry.get("name")): entry
        for entry in role_vars.get("cli_tools") or []
        if isinstance(entry, dict) and entry.get("name")
    }

    cli_tags: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{CLI_TOOLS_MANIFEST} entry {entry!r} is not a mapping")
        name = str(entry.get("name") or "")
        if not name:
            raise ValueError(f"{CLI_TOOLS_MANIFEST} has an entry without a name")
        if "source" in entry:
            # assert_manifest_source_scope owns the one permitted local source.
            continue
        tag = str(entry.get("tag") or "").strip()
        if not _SEMVER_TAG.fullmatch(tag):
            raise ValueError(
                f"{CLI_TOOLS_MANIFEST} entry {name!r} must carry a semver tag "
                f"(vX.Y.Z, never `latest`, a branch or a SHA); got {tag!r}"
            )
        role_entry = role_by_name.get(name)
        if role_entry is None:
            raise ValueError(
                f"{role_vars_path} has no {name!r} cli_tools entry — the role "
                f"mirror is missing"
            )
        role_tag = str(role_entry.get("tag") or "").strip()
        if role_tag != tag:
            raise ValueError(
                f"{role_vars_path} pins {name!r} at {role_tag!r} but "
                f"{CLI_TOOLS_MANIFEST} pins {tag!r} — bump both or neither"
            )
        # The engine's verify mirror names the runtime without the repo prefix
        # (`verify_runtime_version`), while the checkout path keeps the repo name.
        verify_name = "runtime" if name == RUNTIME_NAME else name
        version_key = f"verify_{verify_name}_version"
        checkout_key = f"verify_{verify_name}_checkout"
        pin_key = f"verify_{verify_name}_pin_file"
        verify_tag = str(verify_vars.get(version_key) or "").strip()
        if verify_tag != tag:
            raise ValueError(
                f"{VERIFY_ROLE_VARS} {version_key} is {verify_tag!r} but the "
                f"manifest pins {tag!r} — verify would assert a different tag "
                f"than provisioning installs"
            )
        expected_checkout = (
            "{{ verify_cli_tools_checkout_root }}/" + name + "/{{ " + version_key + " }}"
        )
        if verify_vars.get(checkout_key) != expected_checkout:
            raise ValueError(
                f"{VERIFY_ROLE_VARS} {checkout_key} must be "
                f"{expected_checkout!r}; got {verify_vars.get(checkout_key)!r}"
            )
        expected_pin = "{{ verify_cli_tools_checkout_root }}/" + name + "/pinned"
        if verify_vars.get(pin_key) != expected_pin:
            raise ValueError(
                f"{VERIFY_ROLE_VARS} {pin_key} must be {expected_pin!r}; got "
                f"{verify_vars.get(pin_key)!r}"
            )
        cli_tags[name] = tag

    # 4. The composition csg-templates source mirrors the csg pin.
    csg_tag = cli_tags.get("csg")
    if csg_tag is None:
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST} has no `csg` entry — the csg-templates "
            f"source cannot be checked"
        )
    assets_manifest_path = root / ASSETS_MANIFEST
    if not assets_manifest_path.is_file():
        raise ValueError(f"the assets manifest {ASSETS_MANIFEST} is missing")
    assets_manifest = yaml.safe_load(
        assets_manifest_path.read_text(encoding="utf-8")
    ) or {}
    assets_entries = assets_manifest.get("entries")
    if not isinstance(assets_entries, list):
        raise ValueError(f"{ASSETS_MANIFEST} has no `entries` list")
    csg_template = next(
        (
            entry
            for entry in assets_entries
            if isinstance(entry, dict) and entry.get("name") == "csg-templates"
        ),
        None,
    )
    if csg_template is None:
        raise ValueError(
            f"{ASSETS_MANIFEST} has no `csg-templates` entry — the csg "
            f"template catalog is a pinned-CLI source"
        )
    csg_source = str(csg_template.get("source") or "")
    csg_source_prefix = "{{ install_dir | trim }}/cli-tools/csg/"
    if not csg_source.startswith(csg_source_prefix):
        raise ValueError(
            f"{ASSETS_MANIFEST} csg-templates source {csg_source!r} must be "
            f"under {csg_source_prefix!r}"
        )
    csg_source_tag = csg_source[len(csg_source_prefix):].split("/", 1)[0]
    if csg_source_tag != csg_tag:
        raise ValueError(
            f"{ASSETS_MANIFEST} csg-templates source pins {csg_source_tag!r} "
            f"but {CLI_TOOLS_MANIFEST} pins csg at {csg_tag!r} — bump both or "
            f"neither"
        )

    return installer_tag, cli_tags


def assert_composition_only(root: Path) -> None:
    """S7 (AD-17 terminal): this repo authors the manifests and gates only.

    The per-tree guards above catch a known corpus returning; this catch-all
    catches ANY new authored tree, which is the failure mode that does not yet
    have a name. `src/` is absent: the runtime moved to the pinned
    `dotfiles-runtime` repo. `dotfiles/` may hold `provisioning/` only.
    `dotfiles/config/` is absent since R-07: the btop active-theme is host
    state in the install spine, and every static config is the pinned assets
    `configs` class. The retired corpus roots and the in-repo engine root are
    asserted absent here as the terminal sweep, so a fresh checkout that forgets
    one of the specific guards still fails.
    """
    dotfiles = root / "dotfiles"
    if not dotfiles.is_dir():
        raise ValueError("dotfiles/ is missing — the composition manifests live there")
    authored_dotfiles = sorted(
        child.name
        for child in dotfiles.iterdir()
        if not child.name.startswith(".") and child.name not in COMPOSITION_DOTFILES_ENTRIES
    )
    if authored_dotfiles:
        raise ValueError(
            f"dotfiles/ carries {authored_dotfiles} beyond "
            f"{list(COMPOSITION_DOTFILES_ENTRIES)} — this repo authors manifests "
            f"and gates; config/corpus data is the pinned dotfiles-assets repo "
            f"(AD-17)"
        )

    config = dotfiles / "config"
    if config.exists():
        raise ValueError(
            "dotfiles/config/ must be absent — the btop active-theme preference is "
            "host state in the install spine (R-07/OPEN-5), and every static config "
            "is the pinned dotfiles-assets configs class"
        )

    src = root / "src"
    if src.exists():
        raise ValueError(
            f"src/ still exists — the runtime moved to the pinned "
            f"`{RUNTIME_NAME}` repo (REQ-002); this repo authors no Python. "
            f"Delete {src} and consume the runtime by `{{name, repo, tag}}` "
            f"(AD-17)"
        )

    for retired in (RETIRED_PROVISIONING_ROOT, RETIRED_ASSETS_DIR, *RETIRED_DESKTOP_DIRS):
        if (root / retired).exists():
            raise ValueError(
                f"the retired tree {retired}/ still exists — this repo is the "
                f"composition repo only; delete it and bump the pin instead "
                f"(AD-16/AD-17)"
            )


def assert_itr_provisioned_from_pinned_manifest(root: Path) -> None:
    """cli-tools-repos S4: `itr` (icon renderer) is consumed from its pin."""
    assert_cli_provisioned_from_pinned_manifest(
        root, ITR_NAME, RETIRED_ITR_DIR, "S4"
    )


def assert_weg_provisioned_from_pinned_manifest(root: Path) -> None:
    """cli-tools-repos S5: `weg` (effects generator) is consumed from its pin."""
    assert_cli_provisioned_from_pinned_manifest(
        root, WEG_NAME, RETIRED_WEG_DIR, "S5"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="the external bar + platform units are provisioned"
    )
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    try:
        pin = read_engine_pin(root)
        engine = engine_checkout(root)
    except EngineCheckoutError as exc:
        print(f"FAIL {exc}")
        return 1
    global _ENGINE_ROOT
    _ENGINE_ROOT = engine
    print(f"CHECK pinned installer engine {pin} at {engine}")
    vars_path = engine_path(VARS_FILE)
    ags_dir = (root / AGS_DIR).resolve()

    if not vars_path.is_file():
        print(f"MISSING {VARS_FILE}: {vars_path}")
        return 1

    try:
        deployed = parse_deployed_ags_sources(vars_path.read_text())
        # The in-repo `dotfiles/config/ags/` tree is the dev/typecheck/test
        # bridge and is being retired: it is NOT a precondition. When it is
        # present, compute its relative-import closure and report it as a NOTE.
        # The closure still rejects a relative import into the retired in-place
        # platform dir (which is why the computation stays), so a re-introduced
        # relative platform import cannot pass by pointing at an existing file.
        closure: set[Path] | None = None
        if (ags_dir / ENTRY).is_file():
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
        # The installer engine is external (S6b): a surviving in-repo package
        # would be a second source of truth beside installer.pin, and a stale
        # import would bypass the pinned checkout the gates just resolved.
        if (root / RETIRED_PROVISIONING_ROOT).exists():
            raise ValueError(
                f"{RETIRED_PROVISIONING_ROOT}/ still exists — the engine is the pinned "
                f"external dotfiles-provision repo ({INSTALLER_PIN}); delete the "
                f"in-repo copy"
            )
        # The bar bridge is retired: the skeleton list must carry no per-file
        # bar source (a stale one templates into the unit tree through the
        # live-bar link). The remaining `deployed` entries are non-bar
        # skeletons (hypr/hyprpaper/rofi) — reported, not diffed.
        assert_no_per_file_bar_skeletons(deployed)
        # The platform unit is installed by ags_platform; the ONE shared
        # apps/node_modules shortcut is owned by ags_apps_units (asserted by the
        # app-consumption gate below).
        assert_platform_provisioning(root)
        # The old in-repo GUI source root is retired; every AGS app now deploys
        # as an immutable standalone tag from the composition app list.
        assert_no_gui_tools_dir(root)
        # cli-tools-repos S1: `cli-output` is consumed from its pinned repo.
        # The in-tree package AND every `path =` source for it are retired, so
        # neither a leftover copy nor a re-pointed pin can slip back in.
        assert_no_in_tree_cli_output(root)
        # cli-tools-repos S2: same shape for `config-assembler-engine` (csg,
        # weg, itr consume the v0.1.0 tag; the in-tree tree is retired).
        assert_no_in_tree_config_assembler_engine(root)
        # cli-tools-repos S3: `oci-runtime` (v0.5.0) was the last shared
        # library, so the package AND the `src/shared/` root are retired.
        assert_no_in_tree_oci_runtime(root)
        # cli-tools-repos S4: `itr` is the first CLI consumed from its own
        # pinned repo. The manifest/role shape is asserted (repo+tag, no
        # source), the role must install from the tag-bearing checkout, and the
        # in-tree package must be gone.
        assert_itr_provisioned_from_pinned_manifest(root)
        # cli-tools-repos S5: the same shape for `weg` — repo+tag from the
        # manifest, no source path, installed from the tag-bearing checkout,
        # and the in-tree package gone.
        assert_weg_provisioned_from_pinned_manifest(root)
        # cli-tools-repos S6: `csg` closes the set. Same pinned shape, plus the
        # AD-7 assertion for its SETTINGS-ENV tag transport (its `install` build
        # verb has no --image-tag) and the tag-qualified build context.
        assert_csg_provisioned_from_pinned_manifest(root)
        # REQ-002: the runtime is a pinned repo too. Same generic shape check;
        # `src/runtime/` must be gone.
        assert_cli_provisioned_from_pinned_manifest(
            root, RUNTIME_NAME, RETIRED_RUNTIME_DIR, "REQ-002"
        )
        # Terminal: both parent roots are retired (the last CLI left the repo).
        assert_no_cli_tools_dir(root)
        # AD-11 (final, strict): ZERO local `source:` entries. Every tool,
        # including the runtime, is `{name, repo, tag}` (REQ-002).
        assert_manifest_source_scope(root)
        # S1 (AD-16 catch-all): the icons/content corpus lives in the pinned
        # `dotfiles-assets` repo; the in-tree sources are retired.
        assert_no_assets_corpus(root)
        # S2 (AD-16): the static config corpus moved to the same pin (configs
        # class); the five tool dirs and wlogout's copied `layout` are retired,
        # and S3 added zsh/ + wlogout/ once their template sources left.
        assert_no_in_tree_static_configs(root)
        # S3 (AD-8/AD-16): the template bodies are corpus too. The retired sources
        # are absent AND every render task reads the pinned checkout through its
        # role's pin mirror — the CI-runnable half of AD-8.4.
        assert_no_in_tree_templates(root)
        # S4 (AD-10/AD-16): the desktop entries + helper script are corpus too.
        # The retired trees are absent AND the role resolves the pinned class's
        # contract BEFORE the copy (layer 2), reading only the pinned checkout.
        assert_no_in_tree_desktop_corpus(root)
        # S5 (AD-12): the pinned corpus's shape — one manifest pin mirrored by
        # the role and verify, the same schema support window on both sides, no
        # per-class source back into dotfiles/, and every class's retired corpus
        # path absent (the sweep reuses the S1–S4 constants above).
        assets_tag, assets_classes = assert_assets_shape(root)
        # S7 (AD-4/AD-17): ONE pin set. installer.pin ↔ bootstrap, assets ↔
        # role/verify, every CLI tag ↔ manifest/role/verify, and every
        # library/contract source a git + semver tag. This is the executable
        # answer to "where is the pin list" — ARCHITECTURE section 4.1 documents
        # the same set for human readers.
        installer_tag, cli_tags = assert_pin_set(root, assets_tag)
        # AD-31/AD-32: ONE app list and ONE program tuple. Validated against
        # the contracts v0.3.0 structural rules (mirrored here so a stock
        # checkout needs no contracts clone), the pinned engine's legacy-role
        # surfaces, and the committed legacy/mixed/all-standalone fixtures.
        # The fixture self-test runs on every gate invocation, so a broken
        # list shape fails here rather than at the first cutover.
        app_summary = run_ags_app_consumption_checks(root, engine)
        # S7 (AD-17 terminal): the catch-all. Anything authored under src/ or
        # dotfiles/ beyond the manifests (or any retired corpus/engine root
        # returning) fails here even if its named per-tree guard was forgotten.
        assert_composition_only(root)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}")
        return 1

    if closure is not None:
        print(
            f"deploy-coverage: NOTE — {AGS_DIR}/{ENTRY} present (dev bridge); "
            f"{len(closure)} reachable module(s), covered by the unit assertion "
            f"below, not diffed per file"
        )
    else:
        print(
            f"deploy-coverage: NOTE — {AGS_DIR}/{ENTRY} absent (bridge retired); "
            f"the closure is not computed"
        )
    print(f"deploy-coverage: per-file non-bar sources in the manifest: {len(deployed)}")
    print(
        f"deploy-coverage: external bare specifier {PLATFORM_PACKAGE!r} — the "
        f"pinned unit is installed by ags_platform; the ONE shared "
        f"<install>/apps/node_modules/ags-platform shortcut is owned by "
        f"ags_apps_units (not a per-file deploy)"
    )
    print(
        "deploy-coverage: PASS -- no per-file AGS app sources remain; all seven "
        "apps install as immutable standalone tags from the composition list"
    )
    print(
        f"deploy-coverage: {CLI_OUTPUT_PACKAGE!r} is consumed from its pinned "
        f"repo — no in-tree package and no path source"
    )
    print(
        f"deploy-coverage: {CONFIG_ASSEMBLER_ENGINE_PACKAGE!r} is consumed from "
        f"its pinned repo — no in-tree package and no path source"
    )
    print(
        f"deploy-coverage: {OCI_RUNTIME_PACKAGE!r} is consumed from its pinned "
        f"repo — no in-tree package, no {RETIRED_SHARED_LIBS_DIR}/ root and no "
        f"path source"
    )
    print(
        f"deploy-coverage: {ITR_NAME!r} is provisioned from its pinned manifest "
        f"entry (repo+tag, no source) and installed from the tag-bearing "
        f"checkout — the in-tree tree is retired"
    )
    print(
        f"deploy-coverage: {WEG_NAME!r} is provisioned from its pinned manifest "
        f"entry (repo+tag, no source) and installed from the tag-bearing "
        f"checkout; its image tag is the pin (never `latest`) — the in-tree "
        f"tree is retired"
    )
    print(
        f"deploy-coverage: {CSG_NAME!r} is provisioned from its pinned manifest "
        f"entry (repo+tag, no source) and installed from the tag-bearing "
        f"checkout; its base + backend images are tagged with the pin via "
        f"{CONTAINER_IMAGE_TAG_ENV_KEY} (never `latest`) — the in-tree tree is "
        f"retired"
    )
    print(
        f"deploy-coverage: {RUNTIME_NAME!r} is provisioned from its pinned "
        f"manifest entry (repo+tag, no source) and installed from the "
        f"tag-bearing checkout; {RETIRED_RUNTIME_DIR}/ is retired"
    )
    print(
        "deploy-coverage: PASS -- the static config corpus (hypr, hyprpaper, "
        "nvim, rofi, starship + wlogout/layout) is the pinned dotfiles-assets "
        "configs class; every in-tree copy is retired, including the last two "
        "template sources (dotfiles/config/{zsh,wlogout})"
    )
    print(
        "deploy-coverage: PASS -- the template corpus is the pinned dotfiles-assets "
        f"templates class: {len(TEMPLATE_RENDER_ROLES)} roles read "
        "<install>/assets/<their pin>/templates/, no role carries a templates/ dir, "
        "and no in-tree *.j2/*.tpl source remains"
    )
    print(
        "deploy-coverage: PASS -- the desktop corpus is the pinned dotfiles-assets "
        "desktop class: compositor_configs reads <install>/assets/<pin>/desktop/"
        "{applications,scripts,desktop.yaml}, resolves the contract's "
        "requires/optional BEFORE the copy, and dotfiles/{applications,scripts} are "
        "retired"
    )
    print(
        f"deploy-coverage: PASS -- the assets corpus pin is {assets_tag}, mirrored "
        f"by {ASSETS_ROLE_VARS} and {VERIFY_ROLE_VARS} (repo + tag + class map + "
        f"the AD-12 schema support window); no per-class source points into "
        f"dotfiles/ and every retired corpus path is absent"
    )
    print(
        "deploy-coverage: pin set — installer dotfiles-provision "
        f"{installer_tag} (from {INSTALLER_PIN}; {BOOTSTRAP} reads it, no literal), "
        "assets dotfiles-assets "
        f"{assets_tag}, CLIs "
        + ", ".join(f"{name} {tag}" for name, tag in sorted(cli_tags.items()))
        + " — every pin semver and gate-mirrored; the runtime's library/contract "
        "pins live in dotfiles-runtime"
    )
    print(
        f"deploy-coverage: app list {APPS_MANIFEST} — {app_summary['apps']} apps, "
        f"owners legacy={app_summary['owners']['legacy']} "
        f"standalone={app_summary['owners']['standalone']}; final all-standalone "
        f"one-owner topology, released repo/tag per app"
    )
    print(
        f"deploy-coverage: program tuple {PROGRAM_TUPLE} — ags-platform "
        f"{app_summary['tuple']['ags-platform']}, contracts "
        f"{app_summary['tuple']['contracts']}, dotfiles-assets "
        f"{app_summary['tuple']['dotfiles-assets']} (agrees with assets.tag); one "
        f"tuple per install"
    )
    print(
        f"deploy-coverage: engine final topology — ags-platform "
        f"{app_summary['engine']['platform']} resolved by ags_platform and "
        f"verify; legacy ags_apps role/playbook "
        f"{app_summary['engine']['legacy_role']}; verify standalone mirror + "
        f"seven-app cutover/one-owner fixtures present "
        f"({app_summary['engine_fixtures']} final apps revalidated)"
    )
    print(
        f"deploy-coverage: PASS — app-list fixtures "
        f"({app_summary['app_fixtures']}) accept legacy/mixed/all-standalone and "
        f"reject duplicate/owner/repo violations; program-tuple fixtures accept "
        f"{app_summary['tuple_accepted']} and reject "
        f"{app_summary['tuple_rejected']}"
    )
    print(
        "deploy-coverage: COMPOSITION-ONLY — src/ is absent (the runtime is the "
        f"pinned {RUNTIME_NAME} repo), dotfiles/ holds "
        f"{list(COMPOSITION_DOTFILES_ENTRIES)} (config/ is absent; the "
        "active-theme is spine host state), and "
        f"src/runtime/, {RETIRED_PROVISIONING_ROOT}/, {RETIRED_ASSETS_DIR}/, "
        + ", ".join(f"{path}/" for path in RETIRED_DESKTOP_DIRS)
        + " are absent"
    )
    print(
        "deploy-coverage: assets classes: "
        + " ".join(assets_classes)
        + f" (dirs under <install>/assets/{assets_tag}/)"
    )
    print(
        f"deploy-coverage: PASS -- six packages are consumed from their pinned "
        f"repos ({CLI_OUTPUT_PACKAGE}, {CONFIG_ASSEMBLER_ENGINE_PACKAGE}, "
        f"{OCI_RUNTIME_PACKAGE}, {ITR_NAME}, {WEG_NAME}, {CSG_NAME}) and "
        f"{RUNTIME_NAME} is consumed from its pinned repo; "
        f"{RETIRED_RUNTIME_DIR}/, {RETIRED_CLI_TOOLS_DIR}/ and "
        f"{RETIRED_SHARED_LIBS_DIR}/ are retired, and the CLI manifest carries "
        f"ZERO in-repo sources"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
