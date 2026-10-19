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
  (g) asserts the FOURTH app in the unit, the capture-tool AGS GUI
      `capture-tool` (slice 5): the retired per-file GUI source is gone from the
      gui_tools role and the repo, the `ags_apps` role deploys the unit's
      `capture-tool/` subdir as the live `<install>/config/ags-capture` link (the
      gui_tools `capture` AGS-instance entry is kept), and the Python BACKEND
      (`bin/capture-tool`, installed by cli_tools) SURVIVES in-repo.
  (h) asserts the FIFTH app in the unit, the wallpaper selector
      `wallpaper-selector` (slice 6): the retired per-file source is gone from the
      gui_tools role and the repo, and the `ags_apps` role deploys the unit's
      `wallpaper-selector/` subdir as the live
      `<install>/config/ags-wallpaper-selector` link (the gui_tools
      `wallpaper-selector` AGS-instance entry is kept). The selector is a whole
      package — unlike capture-tool, nothing stays in-repo.
  (i) asserts the SIXTH app in the unit, the icon color mapping editor `icme`
      (slice 7): the retired per-file source is gone from the gui_tools role and
      the repo, and the `ags_apps` role deploys the unit's `icme/` subdir as the
      live `<install>/config/ags-icme` link (the gui_tools
      `icon-color-mapping-editor` AGS-instance entry is kept). Like the selector
      icme is a whole package — nothing stays in-repo.

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

# The capture-tool AGS GUI (ags-apps-bar-first slice 5): the FOURTH app moved
# into the ags-apps unit. It deploys WHOLE like the bar/hypr-pano/notifications —
# the ags_apps role links the unit's capture-tool/ subdir as
# <install>/config/ags-capture — so the gate asserts the same two things: the
# retired per-file source is GONE and the live link is provisioned. The retired
# per-file deploy lived in the gui_tools role (gui_tools_app_files), not the
# compositor manifest, so this half reads that role. NOTE: the gui_tools
# AGS-INSTANCE entry (`capture`, on-demand) is deliberately NOT retired — only the
# per-file placement is.
#
# UNLIKE the other apps, capture-tool is a SPLIT package: the AGS GUI moves into
# the unit, but the Python BACKEND stays in-repo (cli_tools installs it). So the
# "in-repo source is gone" assertion is per-GUI-PATH, not whole-dir, and the gate
# ALSO asserts the backend survives — otherwise a future "delete the whole dir"
# would silently drop the backend the keybind and the GUI both shell out to.
CAPTURE_TOOL_PACKAGE = "capture-tool"
RETIRED_CAPTURE_TOOL_GUI = (
    "src/gui-tools/capture-tool/app.tsx",
    "src/gui-tools/capture-tool/style.css",
    "src/gui-tools/capture-tool/types.ts",
    "src/gui-tools/capture-tool/ui",
    "src/gui-tools/capture-tool/domain",
    "src/gui-tools/capture-tool/ports",
    "src/gui-tools/capture-tool/adapters",
    "src/gui-tools/capture-tool/lib",
    "src/gui-tools/capture-tool/tsconfig.capture.json",
    "src/gui-tools/capture-tool/tests/ts",
    "src/gui-tools/capture-tool/tests/tsconfig.tests.json",
)
CAPTURE_TOOL_BACKEND = "src/gui-tools/capture-tool/bin/capture-tool"

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
    """The capture-tool GUI bridge is retired: no per-file entry may remain.

    The GUI deploys WHOLE via the ags_apps live-capture link, so a per-file entry
    (a gui_tools_app_files dest under ags-capture/, an ags-capture/ spine dir, or
    the retired gui_tools_capture_obsolete list) would template INTO the unit tree
    through the link and silently diverge the live GUI from the pinned tag. The
    GUI source must be gone too: it lives in the ags-apps unit now. The Python
    BACKEND must SURVIVE (cli_tools installs it) — a whole-dir delete would
    silently drop it.
    """
    import yaml

    for retired in RETIRED_CAPTURE_TOOL_GUI:
        if (root / retired).exists():
            raise ValueError(
                f"the retired in-repo {CAPTURE_TOOL_PACKAGE!r} GUI path still "
                f"exists at {retired} — the GUI deploys WHOLE from the ags-apps "
                f"unit; the in-repo copy is a second source of truth"
            )

    if not (root / CAPTURE_TOOL_BACKEND).is_file():
        raise ValueError(
            f"the {CAPTURE_TOOL_PACKAGE!r} Python BACKEND is missing at "
            f"{CAPTURE_TOOL_BACKEND} — only the AGS GUI moved into the ags-apps "
            f"unit; the backend stays in-repo and cli_tools installs it"
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
    """The external capture-tool live link must be provisioned, not assumed.

    Mirror of assert_notifications_provisioning for the fourth app in the unit:
    the ags_apps role declares the unit's capture-tool/ subdir and links it as
    <install>/config/ags-capture. Without this, deleting the in-repo GUI would
    leave the gate green with the live GUI unprovisioned — exactly the
    silent-coverage-loss this gate exists to prevent.
    """
    import yaml

    vars_path = root / BAR_ROLE_VARS
    tasks_path = root / BAR_ROLE_TASKS
    if not vars_path.is_file():
        raise ValueError(
            f"the GUI deploys as the external {CAPTURE_TOOL_PACKAGE!r} unit but "
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
        # Slice 5: the capture-tool AGS GUI deploys WHOLE too (same shape), but
        # the Python backend SURVIVES in-repo — both halves are asserted.
        assert_no_per_file_capture_tool_sources(root)
        assert_capture_tool_provisioning(root)
        # Slice 6: the wallpaper selector deploys WHOLE too (same shape as
        # hypr-pano/notifications). Unlike capture-tool it is a whole package:
        # nothing stays in-repo.
        assert_no_per_file_wallpaper_selector_sources(root)
        assert_wallpaper_selector_provisioning(root)
        # Slice 7: the icon color mapping editor deploys WHOLE too (same shape
        # as the selector). Like the selector it is a whole package: nothing
        # stays in-repo.
        assert_no_per_file_icme_sources(root)
        assert_icme_provisioning(root)
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
        f"subdir + live-capture link provisioned; no per-file gui_tools GUI source "
        f"remains and the Python backend survives in-repo (not a per-file deploy)"
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
        "deploy-coverage: PASS -- the retired bar + hypr-pano + notifications + "
        "capture-tool + wallpaper-selector + icme bridges carry no per-file deploy "
        "source and the external units are provisioned"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
