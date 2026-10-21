#!/usr/bin/env python3
"""deploy-coverage -- the provisioning shape of the external bar + platform.

WHY THIS GATE EXISTS. The AGS bar used to deploy PER FILE: the
`compositor_configs` role looped over `compositor_configs_skeleton_files` and
copied each listed file into the install spine (`<install>/config/ags/...`).
A file that the bar reached through a relative import but that was NOT in that
list was simply never copied -- `copy` neither creates it nor warns -- so a
fresh (or re-run) provision left the module absent, `ags bundle` could not
resolve the import, and the BAR window failed to start. That per-file hazard
is gone: the bar now deploys WHOLE as one versioned unit (the `ags_apps`
role symlinks the unit's bar/ subdir as the live <install>/config/ags), so no
manifest can drift from the entry point's closure.

WHAT IT ASSERTS. The gate asserts the provisioning SHAPE, not the in-repo tree
(the in-repo `dotfiles/config/ags/` bridge is being retired and is NOT
required):
  (a) parses the deployed non-bar set out of `compositor_configs_skeleton_files`
      (roles/compositor_configs/vars/main.yml) and FAILS on any
      `dotfiles/config/ags/` source still listed per file -- a stale bridge
      entry would template INTO the unit tree through the live-bar link and
      silently diverge the live bar from the pinned tag;
  (b) FAILS if the retired in-place `platform/` dir still exists (the platform
      is now the external `ags-platform` bare specifier, spine AD-17);
  (c) asserts the `ags_platform` role installs the pinned platform unit and the
      shared-ancestor `node_modules/ags-platform` shortcut;
  (d) asserts the `ags_apps` role installs the pinned bar unit, deploys the
      live-bar link at `<install>/config/ags`, and creates the per-unit
      resolution shortcut;
  (e) asserts the SECOND app in the unit, the clipboard overlay `hypr-pano`
      (slice 3): the retired per-file source is gone from the gui_tools role
      and the repo, and the `ags_apps` role deploys the unit's `hypr-pano/`
      subdir as the live `<install>/config/ags-hypr-pano` link;
  (f) asserts the THIRD app in the unit, the notification daemon
      `notifications` (slice 4): the retired per-file source is gone from the
      gui_tools role and the repo, and the `ags_apps` role deploys the unit's
      `notifications/` subdir as the live `<install>/config/ags-notifications`
      link (the gui_tools AGS-instance entry that STARTS the daemon is kept);
  (g) asserts the FOURTH app in the unit, `capture-tool` (slice 5 + v0.4.0):
      the retired per-file GUI source is gone from the gui_tools role and the
      repo, the `ags_apps` role deploys the unit's `capture-tool/` subdir as the
      live `<install>/config/ags-capture` link (the gui_tools `capture`
      AGS-instance entry is kept), and the Python BACKEND now ships in the SAME
      unit (`capture-tool/bin/capture-tool`), linked into the user bin dir by the
      `ags_apps` role — nothing stays in-repo.
  (h) asserts the FIFTH app in the unit, the wallpaper selector
      `wallpaper-selector` (slice 6): the retired per-file source is gone from the
      gui_tools role and the repo, and the `ags_apps` role deploys the unit's
      `wallpaper-selector/` subdir as the live
      `<install>/config/ags-wallpaper-selector` link (the gui_tools
      `wallpaper-selector` AGS-instance entry is kept). The selector is a whole
      package like capture-tool — nothing stays in-repo.
  (i) asserts the SIXTH app in the unit, the icon color mapping editor `icme`
      (slice 7): the retired per-file source is gone from the gui_tools role and
      the repo, and the `ags_apps` role deploys the unit's `icme/` subdir as the
      live `<install>/config/ags-icme` link (the gui_tools
      `icon-color-mapping-editor` AGS-instance entry is kept). Like the selector
      icme is a whole package — nothing stays in-repo.
  (j) asserts the SEVENTH app in the unit, the btop Theme Studio
      `btop-theme-studio` (slice 8): the retired per-file source is gone from the
      gui_tools role and the repo, and the `ags_apps` role deploys the unit's
      `btop-theme-studio/` subdir as the live
      `<install>/config/ags-btop-studio` link (the gui_tools
      `btop-theme-studio` AGS-instance entry is kept). Like the selector/icme
      the studio is a whole package — nothing stays in-repo, including its
      Python live-preview engine (`live/btop_live.py`), which the app runs from
      the linked unit tree.

  (k) asserts `cli-output` is consumed from its pinned repo (S1): the in-tree
      package `src/shared/cli-output/` is gone and no package under `src/`
      pins it by `path` — either would make a local copy the source of truth
      while the tag is what every lock records.
  (l) asserts the same for `config-assembler-engine` (S2): the in-tree package
      `src/shared/config-assembler-engine/` is gone and no package under `src/`
      pins it by `path` — csg/weg/itr consume the pinned repo tag instead.
  (m) asserts the same for `oci-runtime` (S3): the in-tree package
      `src/shared/oci-runtime/` is gone, the now-empty `src/shared/` root is
      gone, and no package under `src/` pins it by `path` — csg/weg consume the
      pinned `v0.5.0` repo tag and build images from their own package root.

The relative-import closure of `dotfiles/config/ags/app.tsx` is still computed
when that dev/typecheck/test bridge is PRESENT (a developer checkout, or the
hermetic negative tests below) and reported as a NOTE -- it is no longer a
precondition. It still REJECTS loudly a relative import into the retired
in-place `platform/` dir, so a re-introduced relative platform import cannot
pass by pointing at a file that happens to exist.

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
symlink — covered BY CONSTRUCTION by the `ags_apps` assertion above, never
diffed per file.

THE CLIPBOARD OVERLAY IS EXTERNAL TOO (slice 3). `hypr-pano`'s sources live in
the same pinned unit (`<install>/ags-apps/<tag>/hypr-pano/`), deployed whole via
the live-pano symlink; the per-file `gui_tools_hypr_pano_app_files` manifest is
retired and its in-repo source deleted, both asserted above. Like the bar it
resolves its `ags-platform` imports through the unit's per-unit shortcut (it is
a SIBLING of bar/ inside the unit).

THE PLATFORM IS EXTERNAL TOO. `ags-platform` and its subpaths are a BARE
SPECIFIER resolved by AGS's embedded esbuild through provisioning-created
`node_modules` shortcuts (spine AD-17): the shared-ancestor shortcut for
every config tree, plus the per-unit shortcut inside the bar unit (esbuild
realpaths the live-bar link, so the shared ancestor is not an ancestor of
the real bar tree). A green run means "the retired bridge is gone and both
external units the bar needs are provisioned".

Usage: ``python3 scripts/deploy-coverage.py [--root REPO_ROOT]``
Exit 0 = the bridge is retired and both units are provisioned.
Exit 1 = a stale per-file bar entry remains, the retired platform dir exists, a
         unit is not provisioned, a relative import into the retired platform
         dir exists, or an input is missing/unreadable.

PyYAML is imported and if it is unavailable this gate FAILS rather than
skipping: the manifest is parsed as YAML, not line-mangled. Run it through the
provisioning project so PyYAML is importable, exactly as
`ansible-embedded-template-lint` does:

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
import tomllib
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

# The clipboard overlay (ags-apps-bar-first slice 3): the SECOND app moved into
# the ags-apps unit. It deploys WHOLE the same way as the bar — the ags_apps
# role links the unit's hypr-pano/ subdir as <install>/config/ags-hypr-pano — so
# the gate asserts the same two things: the retired per-file source is GONE and
# the live link is provisioned. The retired per-file deploy lived in the
# gui_tools role (gui_tools_hypr_pano_app_files), not the compositor manifest,
# so this half reads that role.
HYPR_PANO_PACKAGE = "hypr-pano"
GUI_TOOLS_ROLE_VARS = "src/provisioning/ansible/roles/gui_tools/vars/main.yml"

# The retired in-repo clipboard-overlay source: it moved into the ags-apps
# monorepo as hypr-pano/. A surviving copy is a second source of truth that no
# gate deploys but a reader could still mistake for the live app.
RETIRED_HYPR_PANO_DIR = "src/gui-tools/hypr-pano"

# The notification daemon (ags-apps-bar-first slice 4): the THIRD app moved into
# the ags-apps unit. It deploys WHOLE the same way as the bar and hypr-pano — the
# ags_apps role links the unit's notifications/ subdir as
# <install>/config/ags-notifications — so the gate asserts the same two things:
# the retired per-file source is GONE and the live link is provisioned. The
# retired per-file deploy lived in the gui_tools role
# (gui_tools_notifications_app_files), not the compositor manifest, so this half
# reads that role. NOTE: the gui_tools AGS-INSTANCE entry (which STARTS the
# daemon from the symlinked dir) is deliberately NOT retired — only the per-file
# placement is.
NOTIFICATIONS_PACKAGE = "notifications"
RETIRED_NOTIFICATIONS_DIR = "src/gui-tools/notifications"

# The capture-tool app (ags-apps-bar-first slice 5, completed at ags-apps
# v0.4.0): the FOURTH app moved into the ags-apps unit. It deploys WHOLE like the
# bar/hypr-pano/notifications — the ags_apps role links the unit's capture-tool/
# subdir as <install>/config/ags-capture AND links the unit's Python backend
# (capture-tool/bin/capture-tool) into the user bin dir — so the gate asserts the
# retired per-file source is GONE and both links are provisioned. The retired
# per-file deploy lived in the gui_tools role (gui_tools_app_files), not the
# compositor manifest, so this half reads that role. NOTE: the gui_tools
# AGS-INSTANCE entry (`capture`, on-demand) is deliberately NOT retired — only the
# per-file placement is.
#
# capture-tool is now a WHOLE package: from v0.4.0 the Python BACKEND ships in
# the unit (`capture-tool/bin/capture-tool` + `capture-tool/tests/python/`), so
# the in-repo `src/gui-tools/capture-tool/` dir must be gone ENTIRELY. A
# surviving copy would be a second source of truth that no gate deploys.
CAPTURE_TOOL_PACKAGE = "capture-tool"
RETIRED_CAPTURE_TOOL_DIR = "src/gui-tools/capture-tool"
# The unit-side backend (the entry point under capture-tool/) + the bin-dir
# entry point the ags_apps role installs.
CAPTURE_TOOL_BACKEND = "bin/capture-tool"
CLI_TOOLS_ROLE_TASKS = "src/provisioning/ansible/roles/cli_tools/tasks/main.yml"

# The wallpaper selector (ags-apps-bar-first slice 6): the FIFTH app moved into
# the ags-apps unit. It deploys WHOLE like the bar/hypr-pano/notifications/
# capture-tool — the ags_apps role links the unit's wallpaper-selector/ subdir as
# <install>/config/ags-wallpaper-selector — so the gate asserts the same two
# things: the retired per-file source is GONE and the live link is provisioned.
# The retired per-file deploy lived in the gui_tools role
# (gui_tools_wallpaper_selector_app_files), not the compositor manifest, so this
# half reads that role. NOTE: the gui_tools AGS-INSTANCE entry
# (`wallpaper-selector`, on-demand) is deliberately NOT retired — only the
# per-file placement is. UNLIKE capture-tool the selector is a WHOLE package:
# nothing stays in-repo, so the whole in-repo dir must be gone.
WALLPAPER_SELECTOR_PACKAGE = "wallpaper-selector"
RETIRED_WALLPAPER_SELECTOR_DIR = "src/gui-tools/wallpaper-selector"

# The icon color mapping editor (ags-apps-bar-first slice 7): the SEVENTH app
# moved into the ags-apps unit. It deploys WHOLE like the bar/hypr-pano/
# notifications/capture-tool/wallpaper-selector — the ags_apps role links the
# unit's icme/ subdir as <install>/config/ags-icme — so the gate asserts the same
# two things: the retired per-file source is GONE and the live link is
# provisioned. The retired per-file deploy lived in the gui_tools role
# (gui_tools_icme_app_files), not the compositor manifest, so this half reads
# that role. NOTE: the gui_tools AGS-INSTANCE entry
# (`icon-color-mapping-editor`, on-demand) is deliberately NOT retired — only the
# per-file placement is. icme is a WHOLE package: nothing stays in-repo, so the
# whole in-repo dir must be gone. The `icon-color-mapping-editor` launcher's
# ICME_REPO_ROOT hint is unchanged (it points at this checkout for the
# icon-template/mapping INPUTS, not the app sources).
ICME_PACKAGE = "icme"
RETIRED_ICME_DIR = "src/gui-tools/icon-color-mapping-editor"

# The btop Theme Studio (slice 8): the SEVENTH app moved into the ags-apps unit.
# It deploys WHOLE like the bar/hypr-pano/notifications/capture-tool/
# wallpaper-selector/icme — the ags_apps role links the unit's
# btop-theme-studio/ subdir as <install>/config/ags-btop-studio — so the gate
# asserts the same two things: the retired per-file source is GONE and the live
# link is provisioned. The retired per-file deploy lived in the gui_tools role
# (gui_tools_btop_studio_app_files), not the compositor manifest, so this half
# reads that role. NOTE: the gui_tools AGS-INSTANCE entry
# (`btop-theme-studio`, on-demand) is deliberately NOT retired — only the
# per-file placement is. The studio is a WHOLE package: nothing stays in-repo,
# including its Python live-preview engine (live/btop_live.py). The engine needs
# no separate install: the app resolves `${GLib.get_current_dir()}/live/
# btop_live.py`, and `ags run -d` re-roots the process into the linked
# (realpathed) app dir inside the unit.
BTOP_STUDIO_PACKAGE = "btop-theme-studio"
RETIRED_BTOP_STUDIO_DIR = "src/gui-tools/btop-theme-studio"

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
# `{name: itr, repo: …, tag: v0.1.0}`, no `source:` path, and the `cli_tools`
# role installs FROM a tag-bearing checkout at <install>/cli-tools/itr/<tag>/
# (AD-10) rather than from a `git+…@tag` URL. The in-tree package is retired in
# the same slice that proves the new wiring, so a surviving copy is a second
# source of truth that no consumer installs.
CLI_TOOLS_MANIFEST = "dotfiles/provisioning/cli-tools.yaml"
CLI_TOOLS_ROLE_VARS = "src/provisioning/ansible/roles/cli_tools/vars/main.yml"
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
    if not re.match(r"^v\d", str(version)):
        raise ValueError(
            f"ags_apps_version {version!r} names no monorepo release — the unit "
            f"is a monorepo deployed whole, so the pin is a release tag "
            f"(e.g. v0.3.0); got {version!r}"
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


def assert_no_per_file_hypr_pano_sources(root: Path) -> None:
    """The clipboard-overlay bridge is retired: no per-file entry may remain.

    The overlay deploys WHOLE via the ags_apps live-pano link, so a per-file
    entry (gui_tools_hypr_pano_app_files, an ags-hypr-pano/ spine dir, or a dest
    under it) would template INTO the unit tree through the link and silently
    diverge the live app from the pinned tag. The in-repo source must be gone
    too: it lives in the ags-apps unit now.
    """
    import yaml

    if (root / RETIRED_HYPR_PANO_DIR).exists():
        raise ValueError(
            f"the retired in-repo {HYPR_PANO_PACKAGE!r} source still exists at "
            f"{RETIRED_HYPR_PANO_DIR}/ — the overlay deploys WHOLE from the "
            f"ags-apps unit; the in-repo copy is a second source of truth"
        )

    vars_path = root / GUI_TOOLS_ROLE_VARS
    if not vars_path.is_file():
        raise ValueError(
            f"the overlay deploys as the external {HYPR_PANO_PACKAGE!r} unit but "
            f"no gui_tools role declares it: {GUI_TOOLS_ROLE_VARS} is missing"
        )
    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{GUI_TOOLS_ROLE_VARS} did not parse to a mapping")

    if data.get("gui_tools_hypr_pano_app_files"):
        raise ValueError(
            "the overlay deploys WHOLE via the ags_apps live-pano link, but "
            "gui_tools_hypr_pano_app_files still lists per-file sources in "
            f"{GUI_TOOLS_ROLE_VARS} — delete it; the per-file bridge is retired"
        )
    for key, value in data.items():
        if key.endswith("_app_files") and isinstance(value, list):
            for entry in value:
                dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                if "/ags-hypr-pano/" in dest:
                    raise ValueError(
                        f"{key} still deploys into the retired ags-hypr-pano/ "
                        f"spine: {dest} — the overlay deploys WHOLE via the unit"
                    )
    if any(
        "ags-hypr-pano" in str(d) for d in data.get("gui_tools_config_dirs", [])
    ):
        raise ValueError(
            "gui_tools_config_dirs still ensures the retired ags-hypr-pano/ dir "
            "— the ags_apps role owns it as the live-pano symlink"
        )


def assert_hypr_pano_provisioning(root: Path) -> None:
    """The external hypr-pano live link must be provisioned, not assumed.

    Mirror of assert_bar_provisioning for the second app in the unit: the
    ags_apps role declares the unit's hypr-pano/ subdir and links it as
    <install>/config/ags-hypr-pano. Without this, deleting the in-repo source
    would leave the gate green with the live overlay unprovisioned — exactly the
    silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the overlay deploys as the external {HYPR_PANO_PACKAGE!r} unit but "
            f"no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the overlay role has no tasks to deploy it: {BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    pano_dir = str(data.get("ags_apps_hypr_pano_dir", ""))
    if not pano_dir.endswith("/hypr-pano"):
        raise ValueError(
            f"ags_apps_hypr_pano_dir must be the unit's hypr-pano/ subdir (the "
            f"monorepo deviation — the repo root is not the package); got "
            f"{pano_dir!r}"
        )
    live = str(data.get("ags_apps_live_pano_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate and names `ags-hypr-pano`.
    if "spine_config_dir" not in live or not live.endswith("/ags-hypr-pano"):
        raise ValueError(
            f"ags_apps_live_pano_link must deploy the unit's hypr-pano as "
            f"<install>/config/ags-hypr-pano; got {live!r}"
        )

    tasks = tasks_path.read_text()
    if "ags_apps_hypr_pano_dir" not in tasks or "ags_apps_live_pano_link" not in tasks:
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the unit's hypr-pano/ as the "
            f"live-pano link"
        )


def assert_no_per_file_notifications_sources(root: Path) -> None:
    """The notification-daemon bridge is retired: no per-file entry may remain.

    The daemon deploys WHOLE via the ags_apps live-notifications link, so a
    per-file entry (gui_tools_notifications_app_files, an ags-notifications/
    spine dir, or a dest under it) would template INTO the unit tree through the
    link and silently diverge the live daemon from the pinned tag. The in-repo
    source must be gone too: it lives in the ags-apps unit now.
    """
    import yaml

    if (root / RETIRED_NOTIFICATIONS_DIR).exists():
        raise ValueError(
            f"the retired in-repo {NOTIFICATIONS_PACKAGE!r} source still exists "
            f"at {RETIRED_NOTIFICATIONS_DIR}/ — the daemon deploys WHOLE from the "
            f"ags-apps unit; the in-repo copy is a second source of truth"
        )

    vars_path = root / GUI_TOOLS_ROLE_VARS
    if not vars_path.is_file():
        raise ValueError(
            f"the daemon deploys as the external {NOTIFICATIONS_PACKAGE!r} unit "
            f"but no gui_tools role declares it: {GUI_TOOLS_ROLE_VARS} is missing"
        )
    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{GUI_TOOLS_ROLE_VARS} did not parse to a mapping")

    if data.get("gui_tools_notifications_app_files"):
        raise ValueError(
            "the daemon deploys WHOLE via the ags_apps live-notifications link, "
            "but gui_tools_notifications_app_files still lists per-file sources "
            f"in {GUI_TOOLS_ROLE_VARS} — delete it; the per-file bridge is retired"
        )
    for key, value in data.items():
        if key.endswith("_app_files") and isinstance(value, list):
            for entry in value:
                dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                if "/ags-notifications/" in dest:
                    raise ValueError(
                        f"{key} still deploys into the retired ags-notifications/ "
                        f"spine: {dest} — the daemon deploys WHOLE via the unit"
                    )
    if any(
        "ags-notifications" in str(d) for d in data.get("gui_tools_config_dirs", [])
    ):
        raise ValueError(
            "gui_tools_config_dirs still ensures the retired ags-notifications/ "
            "dir — the ags_apps role owns it as the live-notifications symlink"
        )


def assert_notifications_provisioning(root: Path) -> None:
    """The external notifications live link must be provisioned, not assumed.

    Mirror of assert_hypr_pano_provisioning for the third app in the unit: the
    ags_apps role declares the unit's notifications/ subdir and links it as
    <install>/config/ags-notifications. Without this, deleting the in-repo source
    would leave the gate green with the live daemon unprovisioned — exactly the
    silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the daemon deploys as the external {NOTIFICATIONS_PACKAGE!r} unit "
            f"but no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the notifications role has no tasks to deploy it: {BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    notif_dir = str(data.get("ags_apps_notifications_dir", ""))
    if not notif_dir.endswith("/notifications"):
        raise ValueError(
            f"ags_apps_notifications_dir must be the unit's notifications/ subdir "
            f"(the monorepo deviation — the repo root is not the package); got "
            f"{notif_dir!r}"
        )
    live = str(data.get("ags_apps_live_notifications_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate and names `ags-notifications`.
    if "spine_config_dir" not in live or not live.endswith("/ags-notifications"):
        raise ValueError(
            f"ags_apps_live_notifications_link must deploy the unit's "
            f"notifications as <install>/config/ags-notifications; got {live!r}"
        )

    tasks = tasks_path.read_text()
    if (
        "ags_apps_notifications_dir" not in tasks
        or "ags_apps_live_notifications_link" not in tasks
    ):
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the unit's notifications/ as the "
            f"live-notifications link"
        )


def assert_no_per_file_capture_tool_sources(root: Path) -> None:
    """The capture-tool bridge is retired: the whole in-repo app dir is gone.

    From ags-apps v0.4.0 the app is ONE self-contained unit: the AGS GUI AND the
    Python backend (bin/capture-tool + tests/python/) ship in the unit's
    capture-tool/ subdir. The ags_apps role links the GUI as ags-capture and the
    backend as <bin>/capture-tool, so a surviving in-repo copy — GUI or backend —
    is a second source of truth that no gate deploys. A per-file gui_tools entry
    would additionally template INTO the unit tree through the live link and
    silently diverge the live GUI from the pinned tag.
    """
    import yaml

    if (root / RETIRED_CAPTURE_TOOL_DIR).exists():
        raise ValueError(
            f"the retired in-repo {CAPTURE_TOOL_PACKAGE!r} dir still exists at "
            f"{RETIRED_CAPTURE_TOOL_DIR} — the GUI AND the Python backend ship "
            f"in the ags-apps unit (v0.4.0+); the in-repo copy is a second "
            f"source of truth"
        )

    # The retired copy task lived in cli_tools; a stale src reference would
    # resurrect the split (an old backend from this checkout installed over the
    # unit's pinned one).
    cli_tasks = root / CLI_TOOLS_ROLE_TASKS
    if not cli_tasks.is_file():
        raise ValueError(f"{CLI_TOOLS_ROLE_TASKS} is missing")
    if RETIRED_CAPTURE_TOOL_DIR in cli_tasks.read_text():
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} still references {RETIRED_CAPTURE_TOOL_DIR} — "
            f"the backend is installed from the unit by the ags_apps role"
        )

    vars_path = root / GUI_TOOLS_ROLE_VARS
    if not vars_path.is_file():
        raise ValueError(
            f"the GUI deploys as the external {CAPTURE_TOOL_PACKAGE!r} unit but "
            f"no gui_tools role declares it: {GUI_TOOLS_ROLE_VARS} is missing"
        )
    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{GUI_TOOLS_ROLE_VARS} did not parse to a mapping")

    for key, value in data.items():
        if key.endswith("_app_files") and isinstance(value, list):
            for entry in value:
                dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                if "/ags-capture/" in dest:
                    raise ValueError(
                        f"{key} still deploys into the retired ags-capture/ "
                        f"spine: {dest} — the GUI deploys WHOLE via the unit"
                    )
    if any(
        "ags-capture" in str(d) for d in data.get("gui_tools_config_dirs", [])
    ):
        raise ValueError(
            "gui_tools_config_dirs still ensures the retired ags-capture/ dir — "
            "the ags_apps role owns it as the live-capture symlink"
        )
    if data.get("gui_tools_capture_obsolete"):
        raise ValueError(
            "gui_tools_capture_obsolete still lists per-file paths — the GUI "
            f"deploys WHOLE via the unit; delete it in {GUI_TOOLS_ROLE_VARS}"
        )


def assert_capture_tool_provisioning(root: Path) -> None:
    """The external capture-tool app must be provisioned, not assumed.

    The ags_apps role declares the unit's capture-tool/ subdir and links it as
    <install>/config/ags-capture, and links the unit's Python backend
    (capture-tool/bin/capture-tool) into the user bin dir. Without this, deleting
    the in-repo app would leave the gate green with the GUI or the CLI
    unprovisioned — exactly the silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the app deploys as the external {CAPTURE_TOOL_PACKAGE!r} unit but "
            f"no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the capture-tool role has no tasks to deploy it: {BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    capture_dir = str(data.get("ags_apps_capture_tool_dir", ""))
    if not capture_dir.endswith("/capture-tool"):
        raise ValueError(
            f"ags_apps_capture_tool_dir must be the unit's capture-tool/ subdir "
            f"(the monorepo deviation — the repo root is not the package); got "
            f"{capture_dir!r}"
        )
    backend = str(data.get("ags_apps_capture_tool_backend", ""))
    if (
        "ags_apps_capture_tool_dir" not in backend
        or not backend.endswith(f"/{CAPTURE_TOOL_BACKEND}")
    ):
        raise ValueError(
            f"ags_apps_capture_tool_backend must be the pinned unit's backend "
            f"({CAPTURE_TOOL_BACKEND}); got {backend!r}"
        )
    bin_link = str(data.get("ags_apps_capture_tool_bin_link", ""))
    if "ags_apps_bin_dir" not in bin_link or not bin_link.endswith(
        f"/{CAPTURE_TOOL_PACKAGE}"
    ):
        raise ValueError(
            f"ags_apps_capture_tool_bin_link must install the CLI into the user "
            f"bin dir as {CAPTURE_TOOL_PACKAGE!r}; got {bin_link!r}"
        )
    live = str(data.get("ags_apps_live_capture_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate and names `ags-capture`.
    if "spine_config_dir" not in live or not live.endswith("/ags-capture"):
        raise ValueError(
            f"ags_apps_live_capture_link must deploy the unit's capture-tool as "
            f"<install>/config/ags-capture; got {live!r}"
        )

    tasks = tasks_path.read_text()
    if (
        "ags_apps_capture_tool_dir" not in tasks
        or "ags_apps_live_capture_link" not in tasks
    ):
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the unit's capture-tool/ as the "
            f"live-capture link"
        )
    if (
        "ags_apps_capture_tool_backend" not in tasks
        or "ags_apps_capture_tool_bin_link" not in tasks
    ):
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not link the unit's capture-tool backend into "
            f"the user bin dir (ags_apps_capture_tool_backend -> "
            f"ags_apps_capture_tool_bin_link)"
        )


def assert_no_per_file_wallpaper_selector_sources(root: Path) -> None:
    """The wallpaper-selector bridge is retired: no per-file entry may remain.

    The selector deploys WHOLE via the ags_apps live-wallpaper-selector link, so a
    per-file entry (a gui_tools app_files dest under ags-wallpaper-selector/, an
    ags-wallpaper-selector/ spine dir, or a gui_tools_wallpaper_selector_app_files
    key) would template INTO the unit tree through the link and silently diverge
    the live selector from the pinned tag. The in-repo source must be gone too: it
    lives in the ags-apps unit now. Unlike capture-tool the selector is a WHOLE
    package, so the entire in-repo dir must be absent.
    """
    import yaml

    if (root / RETIRED_WALLPAPER_SELECTOR_DIR).exists():
        raise ValueError(
            f"the retired in-repo {WALLPAPER_SELECTOR_PACKAGE!r} source still "
            f"exists at {RETIRED_WALLPAPER_SELECTOR_DIR}/ — the selector deploys "
            f"WHOLE from the ags-apps unit; the in-repo copy is a second source of "
            f"truth"
        )

    vars_path = root / GUI_TOOLS_ROLE_VARS
    if not vars_path.is_file():
        raise ValueError(
            f"the selector deploys as the external {WALLPAPER_SELECTOR_PACKAGE!r} "
            f"unit but no gui_tools role declares it: {GUI_TOOLS_ROLE_VARS} is "
            f"missing"
        )
    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{GUI_TOOLS_ROLE_VARS} did not parse to a mapping")

    if data.get("gui_tools_wallpaper_selector_app_files"):
        raise ValueError(
            "the selector deploys WHOLE via the ags_apps "
            "live-wallpaper-selector link, but gui_tools_wallpaper_selector_app_files "
            f"still lists per-file sources in {GUI_TOOLS_ROLE_VARS} — delete it; the "
            "per-file bridge is retired"
        )
    for key, value in data.items():
        if key.endswith("_app_files") and isinstance(value, list):
            for entry in value:
                dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                if "/ags-wallpaper-selector/" in dest:
                    raise ValueError(
                        f"{key} still deploys into the retired "
                        f"ags-wallpaper-selector/ spine: {dest} — the selector "
                        f"deploys WHOLE via the unit"
                    )
    if any(
        "ags-wallpaper-selector" in str(d)
        for d in data.get("gui_tools_config_dirs", [])
    ):
        raise ValueError(
            "gui_tools_config_dirs still ensures the retired "
            "ags-wallpaper-selector/ dir — the ags_apps role owns it as the "
            "live-wallpaper-selector symlink"
        )


def assert_wallpaper_selector_provisioning(root: Path) -> None:
    """The external wallpaper-selector live link must be provisioned, not assumed.

    Mirror of assert_capture_tool_provisioning for the fifth app in the unit: the
    ags_apps role declares the unit's wallpaper-selector/ subdir and links it as
    <install>/config/ags-wallpaper-selector. Without this, deleting the in-repo
    source would leave the gate green with the live selector unprovisioned —
    exactly the silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the selector deploys as the external {WALLPAPER_SELECTOR_PACKAGE!r} "
            f"unit but no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the wallpaper-selector role has no tasks to deploy it: "
            f"{BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    selector_dir = str(data.get("ags_apps_wallpaper_selector_dir", ""))
    if not selector_dir.endswith("/wallpaper-selector"):
        raise ValueError(
            f"ags_apps_wallpaper_selector_dir must be the unit's "
            f"wallpaper-selector/ subdir (the monorepo deviation — the repo root "
            f"is not the package); got {selector_dir!r}"
        )
    live = str(data.get("ags_apps_live_wallpaper_selector_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate and names `ags-wallpaper-selector`.
    if "spine_config_dir" not in live or not live.endswith(
        "/ags-wallpaper-selector"
    ):
        raise ValueError(
            f"ags_apps_live_wallpaper_selector_link must deploy the unit's "
            f"wallpaper-selector as <install>/config/ags-wallpaper-selector; got "
            f"{live!r}"
        )

    tasks = tasks_path.read_text()
    if (
        "ags_apps_wallpaper_selector_dir" not in tasks
        or "ags_apps_live_wallpaper_selector_link" not in tasks
    ):
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the unit's wallpaper-selector/ as "
            f"the live-wallpaper-selector link"
        )


def assert_no_per_file_icme_sources(root: Path) -> None:
    """The icme bridge is retired: no per-file entry may remain.

    The editor deploys WHOLE via the ags_apps live-icme link, so a per-file entry
    (a gui_tools app_files dest under ags-icme/, an ags-icme/ spine dir, or a
    gui_tools_icme_app_files key) would template INTO the unit tree through the
    link and silently diverge the live editor from the pinned tag. The in-repo
    source must be gone too: it lives in the ags-apps unit now. Like the
    wallpaper selector, icme is a WHOLE package, so the entire in-repo dir must be
    absent.
    """
    import yaml

    if (root / RETIRED_ICME_DIR).exists():
        raise ValueError(
            f"the retired in-repo {ICME_PACKAGE!r} source still exists at "
            f"{RETIRED_ICME_DIR}/ — the editor deploys WHOLE from the ags-apps "
            f"unit; the in-repo copy is a second source of truth"
        )

    vars_path = root / GUI_TOOLS_ROLE_VARS
    if not vars_path.is_file():
        raise ValueError(
            f"the editor deploys as the external {ICME_PACKAGE!r} unit but no "
            f"gui_tools role declares it: {GUI_TOOLS_ROLE_VARS} is missing"
        )
    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{GUI_TOOLS_ROLE_VARS} did not parse to a mapping")

    if data.get("gui_tools_icme_app_files"):
        raise ValueError(
            "the editor deploys WHOLE via the ags_apps live-icme link, but "
            "gui_tools_icme_app_files still lists per-file sources in "
            f"{GUI_TOOLS_ROLE_VARS} — delete it; the per-file bridge is retired"
        )
    for key, value in data.items():
        if key.endswith("_app_files") and isinstance(value, list):
            for entry in value:
                dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                if "/ags-icme/" in dest:
                    raise ValueError(
                        f"{key} still deploys into the retired ags-icme/ spine: "
                        f"{dest} — the editor deploys WHOLE via the unit"
                    )
    if any(
        "ags-icme" in str(d) for d in data.get("gui_tools_config_dirs", [])
    ):
        raise ValueError(
            "gui_tools_config_dirs still ensures the retired ags-icme/ dir — "
            "the ags_apps role owns it as the live-icme symlink"
        )


def assert_icme_provisioning(root: Path) -> None:
    """The external icme live link must be provisioned, not assumed.

    Mirror of assert_wallpaper_selector_provisioning for the seventh app in the
    unit: the ags_apps role declares the unit's icme/ subdir and links it as
    <install>/config/ags-icme. Without this, deleting the in-repo source would
    leave the gate green with the live editor unprovisioned — exactly the
    silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the editor deploys as the external {ICME_PACKAGE!r} unit but "
            f"no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the icme role has no tasks to deploy it: {BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    icme_dir = str(data.get("ags_apps_icme_dir", ""))
    if not icme_dir.endswith("/icme"):
        raise ValueError(
            f"ags_apps_icme_dir must be the unit's icme/ subdir (the monorepo "
            f"deviation — the repo root is not the package); got {icme_dir!r}"
        )
    live = str(data.get("ags_apps_live_icme_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate and names `ags-icme`.
    if "spine_config_dir" not in live or not live.endswith("/ags-icme"):
        raise ValueError(
            f"ags_apps_live_icme_link must deploy the unit's icme as "
            f"<install>/config/ags-icme; got {live!r}"
        )

    tasks = tasks_path.read_text()
    if "ags_apps_icme_dir" not in tasks or "ags_apps_live_icme_link" not in tasks:
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the unit's icme/ as the "
            f"live-icme link"
        )


def assert_no_per_file_btop_studio_sources(root: Path) -> None:
    """The btop Theme Studio bridge is retired: no per-file entry may remain.

    The studio deploys WHOLE via the ags_apps live-btop-studio link, so a
    per-file entry (a gui_tools app_files dest under ags-btop-studio/, an
    ags-btop-studio/ spine dir, or a gui_tools_btop_studio_app_files key) would
    template INTO the unit tree through the link and silently diverge the live
    studio from the pinned tag. The in-repo source must be gone too: it lives in
    the ags-apps unit now. Like the selector/icme the studio is a WHOLE package,
    so the entire in-repo dir must be absent — including live/btop_live.py,
    which the app runs from the linked unit tree.
    """
    import yaml

    if (root / RETIRED_BTOP_STUDIO_DIR).exists():
        raise ValueError(
            f"the retired in-repo {BTOP_STUDIO_PACKAGE!r} source still exists at "
            f"{RETIRED_BTOP_STUDIO_DIR}/ — the studio deploys WHOLE from the "
            f"ags-apps unit; the in-repo copy is a second source of truth"
        )

    vars_path = root / GUI_TOOLS_ROLE_VARS
    if not vars_path.is_file():
        raise ValueError(
            f"the studio deploys as the external {BTOP_STUDIO_PACKAGE!r} unit but "
            f"no gui_tools role declares it: {GUI_TOOLS_ROLE_VARS} is missing"
        )
    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{GUI_TOOLS_ROLE_VARS} did not parse to a mapping")

    if data.get("gui_tools_btop_studio_app_files"):
        raise ValueError(
            "the studio deploys WHOLE via the ags_apps live-btop-studio link, but "
            "gui_tools_btop_studio_app_files still lists per-file sources in "
            f"{GUI_TOOLS_ROLE_VARS} — delete it; the per-file bridge is retired"
        )
    for key, value in data.items():
        if key.endswith("_app_files") and isinstance(value, list):
            for entry in value:
                dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                if "/ags-btop-studio/" in dest:
                    raise ValueError(
                        f"{key} still deploys into the retired ags-btop-studio/ "
                        f"spine: {dest} — the studio deploys WHOLE via the unit"
                    )
    if any(
        "ags-btop-studio" in str(d) for d in data.get("gui_tools_config_dirs", [])
    ):
        raise ValueError(
            "gui_tools_config_dirs still ensures the retired ags-btop-studio/ dir "
            "— the ags_apps role owns it as the live-btop-studio symlink"
        )


def assert_btop_studio_provisioning(root: Path) -> None:
    """The external btop Theme Studio live link must be provisioned, not assumed.

    Mirror of assert_icme_provisioning for the eighth app in the unit: the
    ags_apps role declares the unit's btop-theme-studio/ subdir and links it as
    <install>/config/ags-btop-studio. Without this, deleting the in-repo source
    would leave the gate green with the live studio unprovisioned — exactly the
    silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the studio deploys as the external {BTOP_STUDIO_PACKAGE!r} unit but "
            f"no provisioning role declares it: {BAR_ROLE_VARS} is missing"
        )
    if not tasks_path.is_file():
        raise ValueError(
            f"the btop-theme-studio role has no tasks to deploy it: "
            f"{BAR_ROLE_TASKS} is missing"
        )

    data = yaml.safe_load(vars_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{BAR_ROLE_VARS} did not parse to a mapping")

    studio_dir = str(data.get("ags_apps_btop_studio_dir", ""))
    if not studio_dir.endswith("/btop-theme-studio"):
        raise ValueError(
            f"ags_apps_btop_studio_dir must be the unit's btop-theme-studio/ "
            f"subdir (the monorepo deviation — the repo root is not the package); "
            f"got {studio_dir!r}"
        )
    live = str(data.get("ags_apps_live_btop_studio_link", ""))
    # Shape, not the exact Jinja string: the link routes through the spine
    # config dir intermediate and names `ags-btop-studio`.
    if "spine_config_dir" not in live or not live.endswith("/ags-btop-studio"):
        raise ValueError(
            f"ags_apps_live_btop_studio_link must deploy the unit's studio as "
            f"<install>/config/ags-btop-studio; got {live!r}"
        )

    tasks = tasks_path.read_text()
    if (
        "ags_apps_btop_studio_dir" not in tasks
        or "ags_apps_live_btop_studio_link" not in tasks
    ):
        raise ValueError(
            f"{BAR_ROLE_TASKS} does not deploy the unit's btop-theme-studio/ as "
            f"the live-btop-studio link"
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
        raise ValueError(f"{src} is missing — cannot check {CLI_OUTPUT_PACKAGE!r} pins")
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
        raise ValueError(
            f"{src} is missing — cannot check "
            f"{CONFIG_ASSEMBLER_ENGINE_PACKAGE!r} pins"
        )
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
        raise ValueError(f"{src} is missing — cannot check {OCI_RUNTIME_PACKAGE!r} pins")
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

    role_vars_path = root / CLI_TOOLS_ROLE_VARS
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

    tasks_path = root / CLI_TOOLS_ROLE_TASKS
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

    # AD-7 for a CLI whose build verb takes the tag from SETTINGS ENV instead of
    # argv (csg's `v0.1.0` `install` has no `--image-tag`). The contract is the
    # same — the image tag is the manifest pin — so the gate asserts the env
    # transport carries exactly `{{ item.tag }}`, that the build still uses the
    # tag-qualified checkout as context, and that no literal tag appears in the
    # ... and that no literal tag appears in the task CODE (comments may name a
    # version — a hardcoded `v0.1.0` in an argv/env would survive a pin bump).
    task_code = "\n".join(
        line for line in tasks_text.splitlines() if not line.lstrip().startswith("#")
    )
    if tag in task_code:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} contains the literal image tag {tag!r} in a "
            f"task — the tag must come from the manifest pin (`{{{{ item.tag }}}}`) "
            f"so a pin bump reaches the build (spine AD-7)"
        )
    env_builds = [
        task
        for task in yaml.safe_load(tasks_text) or []
        if isinstance(task.get("environment"), dict)
        and tag_env_key in task["environment"]
    ]
    if len(env_builds) != 1:
        raise ValueError(
            f"{CLI_TOOLS_ROLE_TASKS} must carry exactly ONE image build whose "
            f"tag comes from {tag_env_key} (csg's verb has no --image-tag); "
            f"found {len(env_builds)}"
        )
    env_task = env_builds[0]
    env_argv = _task_argv(env_task) or []
    if env_argv[0:2] != ["{{ item.name }}", "install"]:
        raise ValueError(
            f"the {tag_env_key} build is not an `<cli> install` argv build: "
            f"{env_argv!r}"
        )
    if "--image-tag" in env_argv:
        raise ValueError(
            f"the {tag_env_key} build also passes --image-tag — pick ONE "
            f"transport; csg's v0.1.0 verb does not accept the flag"
        )
    if env_argv[env_argv.index("--context") + 1 :][:1] != [
        "{{ cli_tools_checkout_root }}/{{ item.name }}/{{ item.tag }}"
    ]:
        raise ValueError(
            f"the {tag_env_key} build uses the wrong context — it must build "
            f"from the tag-qualified checkout (spine AD-5/AD-10)"
        )
    if str(env_task["environment"][tag_env_key]).strip() != "{{ item.tag }}":
        raise ValueError(
            f"the {tag_env_key} build tags the image "
            f"{env_task['environment'][tag_env_key]!r} — the image tag must be "
            f"the manifest pin (`{{{{ item.tag }}}}`), never a literal "
            f"(spine AD-7)"
        )


def assert_csg_provisioned_from_pinned_manifest(root: Path) -> None:
    """cli-tools-repos S6: `csg` (palette generator) is consumed from its pin.

    csg is the LAST extracted CLI and the second container-mode one. Its
    `v0.1.0` build verb has no `--image-tag`, so the AD-7 assertion follows the
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


def assert_manifest_source_scope(root: Path) -> None:
    """The CLI manifest has exactly ONE local `source:` — `dotfiles-runtime`.

    AD-11 (final, strict) / OPEN-7: every EXTRACTED entry is `{name, repo,
    tag}`. `dotfiles-runtime` is not extracted — this repo still authors it at
    `src/runtime` — so it is the single permitted in-repo source. Asserted so
    the mixed-shape window cannot silently reopen: a stray `source:` on a CLI
    entry is a local path one consumer would resolve while the others use the
    tag.
    """
    import yaml

    manifest_path = root / CLI_TOOLS_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"{CLI_TOOLS_MANIFEST} is missing")
    data = yaml.safe_load(manifest_path.read_text())
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{CLI_TOOLS_MANIFEST} has no `entries` list")

    source_entries = [e for e in entries if isinstance(e, dict) and "source" in e]
    if len(source_entries) != 1:
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST} must carry exactly ONE `source:` entry "
            f"(`dotfiles-runtime` -> src/runtime); found "
            f"{[(e.get('name'), e.get('source')) for e in source_entries]}"
        )
    only = source_entries[0]
    if only.get("name") != "dotfiles-runtime" or str(
        only.get("source")
    ).strip() != "src/runtime":
        raise ValueError(
            f"{CLI_TOOLS_MANIFEST}'s only local source must be "
            f"`dotfiles-runtime: src/runtime` (the runtime this repo still "
            f"authors); got {only.get('name')!r}: {only.get('source')!r}"
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
    vars_path = root / VARS_FILE
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
        # The bar bridge is retired: the skeleton list must carry no per-file
        # bar source (a stale one templates into the unit tree through the
        # live-bar link). The remaining `deployed` entries are non-bar
        # skeletons (hypr/hyprpaper/rofi) — reported, not diffed.
        assert_no_per_file_bar_skeletons(deployed)
        assert_platform_provisioning(root)
        assert_bar_provisioning(root)
        # Slice 3: the clipboard overlay deploys WHOLE too. Asserted AFTER the
        # bar so a hermetic fixture that only exercises the bar bridge (and does
        # not carry the gui_tools role) fails on its own subject, not here.
        assert_no_per_file_hypr_pano_sources(root)
        assert_hypr_pano_provisioning(root)
        # Slice 4: the notification daemon deploys WHOLE too (same shape as
        # hypr-pano: retired per-file gui_tools source + live-notifications link).
        assert_no_per_file_notifications_sources(root)
        assert_notifications_provisioning(root)
        # Slice 5 (+ v0.4.0): capture-tool deploys WHOLE too, GUI and Python
        # backend alike — both halves are asserted.
        assert_no_per_file_capture_tool_sources(root)
        assert_capture_tool_provisioning(root)
        # Slice 6: the wallpaper selector deploys WHOLE too (same shape as
        # hypr-pano/notifications). Like capture-tool it is a whole package:
        # nothing stays in-repo.
        assert_no_per_file_wallpaper_selector_sources(root)
        assert_wallpaper_selector_provisioning(root)
        # Slice 7: the icon color mapping editor deploys WHOLE too (same shape
        # as the selector). Like the selector it is a whole package: nothing
        # stays in-repo.
        assert_no_per_file_icme_sources(root)
        assert_icme_provisioning(root)
        # Slice 8: the btop Theme Studio deploys WHOLE too (same shape as the
        # selector/icme). Like them it is a whole package: nothing stays in-repo.
        assert_no_per_file_btop_studio_sources(root)
        assert_btop_studio_provisioning(root)
        # The parent dir itself is retired: the per-app checks above catch a
        # known app returning; this catches ANY reappearance under the old root.
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
        # AD-7 assertion for its SETTINGS-ENV tag transport (its v0.1.0 build
        # verb has no --image-tag) and the tag-qualified build context.
        assert_csg_provisioned_from_pinned_manifest(root)
        # Terminal: both parent roots are retired (the last CLI left the repo).
        assert_no_cli_tools_dir(root)
        # AD-11 (final, strict): exactly one local `source:` in the CLI
        # manifest, and it is `dotfiles-runtime` -> src/runtime (OPEN-7).
        assert_manifest_source_scope(root)
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
        f"deploy-coverage: external bare specifier {PLATFORM_PACKAGE!r} — unit + "
        f"shared-ancestor shortcut provisioned (not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external bar unit {BAR_PACKAGE!r} — pinned unit + "
        f"live-bar link + per-unit resolution shortcut provisioned "
        f"(not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external {HYPR_PANO_PACKAGE!r} app — pinned unit subdir "
        f"+ live-pano link provisioned; no per-file gui_tools source remains "
        f"(not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external {NOTIFICATIONS_PACKAGE!r} app — pinned unit "
        f"subdir + live-notifications link provisioned; no per-file gui_tools "
        f"source remains (not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external {CAPTURE_TOOL_PACKAGE!r} app — pinned unit "
        f"subdir + live-capture link provisioned; no per-file gui_tools source "
        f"remains and the Python backend is linked from the unit into the user "
        f"bin dir (not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external {WALLPAPER_SELECTOR_PACKAGE!r} app — pinned "
        f"unit subdir + live-wallpaper-selector link provisioned; no per-file "
        f"gui_tools source remains (not a per-file deploy)"
    )
    print(
        f"deploy-coverage: external {ICME_PACKAGE!r} app — pinned unit subdir + "
        f"live-icme link provisioned; no per-file gui_tools source remains (not a "
        f"per-file deploy)"
    )
    print(
        f"deploy-coverage: external {BTOP_STUDIO_PACKAGE!r} app — pinned unit "
        f"subdir + live-btop-studio link provisioned; no per-file gui_tools source "
        f"remains (not a per-file deploy)"
    )

    print(
        "deploy-coverage: PASS -- the retired bar + hypr-pano + notifications + "
        "capture-tool + wallpaper-selector + icme + btop-theme-studio bridges "
        "carry no per-file deploy source and the external units are provisioned"
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
        f"deploy-coverage: PASS -- six packages are consumed from their pinned "
        f"repos ({CLI_OUTPUT_PACKAGE}, {CONFIG_ASSEMBLER_ENGINE_PACKAGE}, "
        f"{OCI_RUNTIME_PACKAGE}, {ITR_NAME}, {WEG_NAME}, {CSG_NAME}); "
        f"{RETIRED_CLI_TOOLS_DIR}/ and {RETIRED_SHARED_LIBS_DIR}/ are retired, "
        f"and the CLI manifest carries exactly ONE in-repo source "
        f"(dotfiles-runtime -> src/runtime)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
