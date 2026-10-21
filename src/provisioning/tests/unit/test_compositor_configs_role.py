from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml



def _authored_icons_yaml() -> Path | None:
    """Resolve the authored icon map — it is assets corpus since S1.

    The map moved to the pinned `dotfiles-assets` repo, so it is not in this
    checkout. Resolution: explicit ``DOTFILES_ASSETS_ICONS_YAML``, else the
    provisioned spine's deployed copy. ``None`` means "not provided" — the
    caller must skip loudly rather than seed a stub the bar gate rejects.
    """
    explicit = os.environ.get("DOTFILES_ASSETS_ICONS_YAML")
    candidates: list[Path] = [Path(explicit).expanduser()] if explicit else []
    spine = os.environ.get("DOTFILES_INSTALL_SPINE")
    if spine:
        candidates.append(Path(spine).expanduser() / "icon-mappings" / "icons.yaml")
    else:
        xdg_data = Path(
            os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
        )
        candidates.append(xdg_data / "dotfiles" / "icon-mappings" / "icons.yaml")
    return next((path for path in candidates if path.is_file()), None)

def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_assets_role.py`` / ``test_default_palette_role.py``: anchored
    on ``pyproject.toml`` so the sibling project's ``ansible/`` tree in a shared
    workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-7 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "compositor_configs"

_TASK_KEYWORDS = {
    "name",
    "when",
    "become",
    "become_user",
    "become_method",
    "become_flags",
    "args",
    "register",
    "changed_when",
    "failed_when",
    "creates",
    "vars",
    "loop",
    "until",
    "retries",
    "delay",
    "tags",
    "environment",
    "ignore_errors",
    "notify",
    "check_mode",
    "block",
    "rescue",
    "always",
    "delegate_to",
    "run_once",
    "no_log",
    "include_tasks",
    "import_tasks",
    "include_role",
    "meta",
}


def _load_tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLES_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return data


def _module_key(task: dict[str, object]) -> str | None:
    """Return the module FQCN key for a task, or None for bare-key tasks."""
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, object]) -> dict[str, object]:
    """Return the module body as a dict for a task. String-valued modules
    (free-form `command`/`shell` tasks) yield an empty dict — use
    ``_module_text`` for those."""
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return {}
    assert isinstance(module, dict)
    return module


def _module_text(task: dict[str, object]) -> str:
    """Return the module body as text for free-form tasks (string-valued
    modules)."""
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return module
    assert isinstance(module, dict)
    return " ".join(str(value) for value in module.values())


def _creates_value(task: dict[str, object]) -> object | None:
    """Return the ``creates`` value whether declared top-level, in args, or
    inside the module body."""
    direct = task.get("creates")
    if direct is not None:
        return direct
    for container in (task.get("args"), _module(task)):
        if isinstance(container, dict) and container.get("creates") is not None:
            return container.get("creates")
    return None


def _vars() -> Any:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _tasks_with_module(module: str) -> list[dict[str, object]]:
    return [task for task in _load_tasks() if _module_key(task) == module]


def _copy_tasks() -> list[dict[str, object]]:
    return _tasks_with_module("ansible.builtin.copy")


def _skeleton_task() -> dict[str, object]:
    """The single skeleton placement task: the `template` task carrying
    `force: true` (repo-authoritative, owner decision 2026-08-26), looping
    over {{ compositor_configs_skeleton_files }}."""
    matches = [
        task
        for task in _tasks_with_module("ansible.builtin.template")
        if str(_module(task).get("force")) == "True"
        and "compositor_configs_skeleton_files" in str(task.get("loop", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one skeleton placement task looping over "
        f"compositor_configs_skeleton_files; found {len(matches)}"
    )
    return matches[0]


#: The bar unit's source repo. The live bar is the pinned external `ags-apps`
#: unit (slice 2), so the in-repo `dotfiles/config/ags` bridge is retired. The
#: execution tests below run compositor-configs.yaml STANDALONE and must seed
#: the unit's bar package by hand; they source it from a local `ags-apps`
#: checkout (override with $AGS_APPS_REPO). Mirrors `contract-pin-check.py`'s
#: sibling-checkout handling: when the checkout is absent the tests that need
#: the real unit SKIP rather than fail (this suite is dev-only; CI has none).
_AGS_APPS_REPO = Path(
    os.environ.get("AGS_APPS_REPO", "/home/inumaki/Development/ags-apps")
)


def _seed_assets_configs(install: Path) -> None:
    """Materialize the pinned assets `configs/` class the skeletons render from.

    S2: the role reads `<install>/assets/<tag>/configs/…`, which the assets role
    fetches. These execution tests run THIS role in isolation (no network), so
    they seed the same shape with a recognizable body. `hyprland.lua` carries the
    one render-time token, so the template module must resolve it to this run's
    XDG config home — exactly what the assertions below check.
    """
    tag = str(_vars()["compositor_configs_assets_pinned_tag"])
    root = install / "assets" / tag / "configs"
    for entry in _vars()["compositor_configs_skeleton_files"]:
        relative = str(entry["source"]).split("}}/", 1)[1]
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"-- skeleton {entry['name']}\n")
    (root / "hypr" / "hyprland.lua").write_text(
        'local cfg = "{{ compositor_configs_xdg_config_home }}/hypr"\n'
        'dofile(cfg .. "/keybindings.lua")\n'
    )


def _preseed_bar_unit(install: Path) -> Path:
    """Seed the pinned bar unit exactly as the ags_apps role deploys it.

    Bootstrap order (ags-apps.yaml before compositor-configs.yaml) guarantees
    the live-bar link into the pinned unit exists before this role generates
    icons.json through it and gates on the unit's CLI. Execution tests that
    run compositor-configs.yaml STANDALONE must build that state by hand: the
    unit's bar package is copied from a local `ags-apps` checkout (the bar
    deploys WHOLE from there now — the in-repo bridge is retired), the pin is
    recorded, and <install>/config/ags links at the unit's bar/. `node_modules`
    and `@girs` are skipped: the strict-gate CLI is pure (`node:*` + the bar's
    own pure modules), so neither the 49 MB GJS typings nor the dev platform
    shortcut is needed.
    """
    src = _AGS_APPS_REPO / "bar"
    if not (src / "bar" / "validate-cli.ts").is_file():
        pytest.skip(
            f"ags-apps bar unit not found at {src} (set AGS_APPS_REPO); the "
            "strict bar gate needs the unit's validate-cli.ts"
        )
    bar = install / "ags-apps" / "v0.4.0" / "bar"
    shutil.copytree(
        src,
        bar,
        ignore=shutil.ignore_patterns("node_modules", "@girs", ".git"),
    )
    (install / "ags-apps" / "pinned").write_text("v0.4.0\n")
    (install / "config").mkdir(parents=True, exist_ok=True)
    (install / "config" / "ags").symlink_to(bar, target_is_directory=True)
    # The capture-tool AGS GUI deploys WHOLE the same way (slice 5): the unit's
    # capture-tool/ subdir is linked as <install>/config/ags-capture, and the
    # role's capture icons.json is generated THROUGH that link (mirror of the
    # bar's icons.json). A standalone compositor-configs run must build that state
    # by hand, exactly as it does for the bar.
    capture = install / "ags-apps" / "v0.4.0" / "capture-tool"
    capture.mkdir(parents=True, exist_ok=True)
    (capture / "app.tsx").write_text("export {}\n")
    (install / "config" / "ags-capture").symlink_to(
        capture, target_is_directory=True
    )
    return bar


class TestCompositorConfigsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_icme_chooser_rule_still_matches_the_editors_chooser_titles(self) -> None:
        """The icme-filechooser-replaces-editor rule must keep matching EVERY
        file chooser the editor can open — Mappings inputs + Templates picker —
        so all of them float centered at editor size instead of tiling.

        The rule matches portal-window TITLES, and those titles are the GUI
        dialogs' own label strings. The editor source moved into the ags-apps
        unit (slice 7), so the source-side cross-check cannot run here; the four
        titles the editor uses are therefore PINNED in this test, and a rename in
        the unit must be accompanied by a rule update here. (The cross-repo
        rename lock is a known gap: nothing in either repo can observe both
        sides.)
        """
        import re

        rule = (
            _ANSIBLE_DIR.parents[2]
            / "dotfiles"
            / "config"
            / "hypr"
            / "window-rules.lua"
        ).read_text()
        m = re.search(
            r"icme-filechooser-replaces-editor.*?title = \"([^\"]+)\"",
            rule,
            re.S,
        )
        assert m, "icme-filechooser-replaces-editor rule must carry a title regex"
        normalized = m.group(1).replace("\\", "")

        pinned_titles = [
            "Icons manifest (edited by tool)",
            "SVG template root",
            "Color scheme (read-only)",
            "Template file",
        ]
        for title in pinned_titles:
            assert title in normalized, (
                f"editor chooser title {title!r} missing from the "
                "icme-filechooser-replaces-editor window rule"
            )


class TestCompositorConfigsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Role contract: the FIRST task is an `ansible.builtin.assert` requiring
        the install_dir seam extra-var — the identical verbatim copy of the
        2.5/2.6/2.7 assert (no aliasing into a var)."""
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert (role contract)"
        )
        assert_ = _module(first)
        that = str(assert_.get("that", ""))
        assert "install_dir is defined" in that
        assert "install_dir | trim | length > 0" in that

    def test_skeleton_files_templated_per_file_with_force_false(self) -> None:
        """AC 2 + repo-authoritative (owner decision 2026-08-26): the skeleton
        placement task loops over the skeleton FILES (per-file entries — a
        directory `copy` + `force: false` + pre-existing dest is a silent
        no-op, review finding 2026-08-12), each entry a `source` prefixed
        `{{ compositor_configs_assets_configs_dir }}/<dir>/<file>` (S2: the pinned
        assets configs class) and a
        `dest` under the config-in-spine home ({{ compositor_configs_spine_config_dir }},
        config-in-spine 2026-08-16), and the task renders via
        `ansible.builtin.template` with `force: true` — repo-authoritative,
        every bootstrap converges to the repo (owner decision 2026-08-26)."""
        task = _skeleton_task()
        module = _module(task)
        assert module.get("force") is True, (
            "skeleton placements must set force: true (repo-authoritative per owner decision 2026-08-26)"
        )
        assert "compositor_configs_skeleton_files" in str(task.get("loop", ""))

        data = _vars()
        files = list(data["compositor_configs_skeleton_files"])
        # capture tool files are NOT part of the compositor_configs skeletons
        # either: the app (GUI + Python backend) lives entirely in the pinned
        # ags-apps unit and deploys via the ags_apps role's live-capture link.
        # (The pre-hexagonal views + controllers were deleted by
        # refactor-capture-tool-hexagonal, task 1.4.)
        # EXACT count, deliberately. 65 on master, 66 once the battery panel's
        # pure presentation logic was registered, 71 once the panel's widget half
        # followed it, 83 once the audio hexagon was registered, and 84 once
        # finish-audio-bar-migration split audio/state.ts into ui-state.ts +
        # presentation/levels.ts + presentation/bar-indicators.ts and retired
        # audio/state.ts and services/mpris-service.ts (+3, -2), 86 once the
        # bar kit (kit/icon.ts + kit/widget.tsx) was registered, 90 once the
        # overlay coordinator + the network descriptor were added, and 91 once
        # the network domain read model (domains/network/read-model.ts) was added
        # to make the descriptor react to device property changes, and 106 once
        # the fix-deploy-bar-new-files coverage gate registered the reachable
        # sources the platform work added, 108 once surfaces-popup-host (AD-10)
        # added kit/surface.ts + kit/popup-host.tsx, and 114 once
        # preferences-notifier-theme (AD-11/AD-12/AD-13) added the three pure
        # ports and their three bar adapters, 116 once migrate-widgets-to-shapes
        # (AD-8/AD-9) added kit/layout.ts + bar/layout.default.ts + bar/registry.ts
        # and retired bar/widgets/network.tsx (-1, +3), 118 once
        # extract-platform-in-place (AD-17/AD-20) consolidated the platform, 103
        # once ags-consume-platform (AD-17/AD-23) deleted the 15 platform entries
        # and installed the platform as ONE versioned unit instead (-15), 106
        # once ags-bar-validate-at-install section 1 (AD-14/AD-15) registered the
        # bar-manifest + validators + install gate (+3).
        # 15 once ags-apps-bar-first slice 2 (AD-1/AD-17/AD-23) retired the
        # in-place bar bridge: the 91 `dotfiles/config/ags/` entries are DELETED
        # and the bar deploys WHOLE as the pinned ags-apps unit (the live
        # <install>/config/ags symlink into the unit's bar/). A stale per-file
        # bar entry would template INTO the unit tree through that link —
        # silently diverging the live bar from the pinned tag — so the
        # deploy-coverage gate FAILS on any of them and this test pins their
        # absence below. The remaining 15 are the non-bar skeletons
        # (13 hypr + hyprpaper + rofi launcher) this role still places per file.
        # Placement here is PER FILE, so an unregistered file silently never
        # deploys: this assertion is what makes that fail loudly at review time
        # instead of at runtime. Do NOT relax it to `>=`, a subset check, or
        # delete it — those all convert "deploys nothing" into "passes".
        assert len(files) == 15, (
            "expected exactly 15 skeleton files (13 hypr modules + "
            "hyprpaper.conf + rofi launcher config.rasi); the 91 bar bridge "
            f"entries are retired (slice 2 deploys the unit whole); found {len(files)}"
        )
        sources = sorted(str(f["source"]) for f in files)
        prefix = "{{ compositor_configs_assets_configs_dir }}/"
        expected = [
            prefix + "hypr/animations.lua",
            prefix + "hypr/autostart.lua",
            prefix + "hypr/colors.lua",
            prefix + "hypr/cursor.lua",
            prefix + "hypr/decoration.lua",
            prefix + "hypr/env-variables.lua",
            prefix + "hypr/general.lua",
            prefix + "hypr/gloview.lua",
            prefix + "hypr/hyprland.lua",
            prefix + "hypr/input.lua",
            prefix + "hypr/keybindings.lua",
            prefix + "hypr/monitors.lua",
            prefix + "hypr/window-rules.lua",
            prefix + "hyprpaper/hyprpaper.conf",
            prefix + "rofi/launcher/config.rasi",
        ]
        assert sources == expected, f"skeleton file sources must be exactly {expected}"
        for file_ in files:
            assert str(file_["source"]).startswith(prefix), (
                "skeleton file source must live in the pinned assets configs class "
                "(S2) — never a composition-repo tree"
            )
            assert "dotfiles/config" not in str(file_["source"])
            assert str(file_["dest"]).startswith("{{ compositor_configs_spine_config_dir }}/"), (
                "skeleton file dest must derive from compositor_configs_spine_config_dir"
            )
        # --check on a never-provisioned machine skips the render (the assets
        # clone is check-gated, so the checkout is absent); a real run reaches
        # the presence assert first and fails loud.
        assert str(task.get("when")) == (
            "not ansible_check_mode or compositor_configs_assets_configs_check.stat.isdir | default(false)"
        ), task.get("when")

    def test_skeleton_placements_carry_no_creates(self) -> None:
        """AC 5/6 idempotency: `force: false` already guarantees no re-transfer
        when the file exists — a `creates:` would be redundant and confusing."""
        assert _creates_value(_skeleton_task()) is None, (
            "skeleton placement task must not carry creates: "
            "(force: false already guarantees no re-transfer)"
        )

    def test_no_fragment_copies_remain(self) -> None:
        """Epic 4: no task loops over compositor_configs_fragment_copies —
        the palette fragment copies are deleted (the runtime seeder owns
        the R2 consumer symlink, rt-4-2)."""
        for task in _load_tasks():
            assert "compositor_configs_fragment_copies" not in str(task.get("loop", "")), (
                f"task {task.get('name')!r} still loops over fragment copies (Epic 4 removed them)"
            )
            assert "compositor_configs_fragment_stats" not in str(task), (
                f"task {task.get('name')!r} still consumes the retired classification register"
            )

    def test_no_bar_bridge_sources_remain(self) -> None:
        """Slice 2: the in-place bar bridge is retired as a deploy source — NO
        `dotfiles/config/ags/` entry may remain in the skeleton list. A stale
        one would template INTO the unit tree through the live-bar link and
        silently diverge the live bar from the pinned tag. (deploy-coverage
        asserts the same from the gate side; this pins it structurally.)"""
        data = _vars()
        for file_ in data["compositor_configs_skeleton_files"]:
            assert "/ags/" not in str(file_["source"]), (
                f"stale bridge entry {file_['source']!r}: the bar deploys whole "
                "via the ags_apps unit symlink"
            )

    def test_no_ags_config_dirs_remain(self) -> None:
        """Slice 2: the role no longer ensures the live-bar `ags` dir — it is
        owned by the ags_apps role as a symlink. Slice 5 retired the
        `ags-capture` dir the same way (the ags_apps live-capture link owns it).
        What remains in compositor_configs_config_dirs are the compositor dirs
        (hypr/hyprpaper/rofi), never an AGS app dir: the sibling AGS apps deploy
        WHOLE via the ags_apps live links (ags-capture, ags-icme, ...)."""
        import re

        data = _vars()
        for config_dir in data["compositor_configs_config_dirs"]:
            assert not re.search(r"/ags([\"'/]|$)", str(config_dir)), (
                f"stale ags dir ensure {config_dir!r}: the live bar link is "
                "owned by ags_apps"
            )
            assert not re.search(r"/ags-capture([\"'/]|$)", str(config_dir)), (
                f"stale ags-capture dir ensure {config_dir!r}: the live capture "
                "link is owned by ags_apps (slice 5)"
            )
            assert not re.search(r"/ags-icme([\"'/]|$)", str(config_dir)), (
                f"stale ags-icme dir ensure {config_dir!r}: the live icme link "
                "is owned by ags_apps (slice 7)"
            )

    def test_desktop_entries_placed_into_xdg_data_applications(self) -> None:
        """App desktop-entry overrides (e.g. TIDAL's Electron /dev/shm flag) are
        placed into $XDG_DATA_HOME/applications so rofi's drun mode shadows the
        package entry. The role owns both the dir ensure and the per-file copy."""
        data = _vars()
        entries = list(data["compositor_configs_desktop_entries"])
        assert entries, "expected at least one desktop entry override"
        for entry in entries:
            assert str(entry["source"]).startswith("dotfiles/applications/"), (
                "desktop entry sources live under dotfiles/applications/"
            )
            assert str(entry["dest"]).startswith(
                "{{ compositor_configs_xdg_data_home }}/applications/"
            ), "desktop entry dest must derive from compositor_configs_xdg_data_home"

        dir_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.file")
            if "applications" in str(_module(task).get("path", ""))
        ]
        assert dir_tasks, "no $XDG_DATA_HOME/applications dir ensure task found"

        copy_tasks = [
            task
            for task in _copy_tasks()
            if "compositor_configs_desktop_entries" in str(task.get("loop", ""))
        ]
        assert len(copy_tasks) == 1, (
            "expected exactly one desktop-entry copy task looping over "
            "compositor_configs_desktop_entries"
        )
        assert _module(copy_tasks[0]).get("force") is True, (
            "desktop entries are repo-authoritative (force: true)"
        )

    def test_tidal_desktop_entry_carries_dev_shm_workaround(self) -> None:
        """The repo-authored override must keep the packaged Wayland/Ozone flags
        and add --disable-dev-shm-usage (TIDAL's Castlabs Electron needs it)."""
        desktop = (
            _ANSIBLE_DIR.parents[2]
            / "dotfiles"
            / "applications"
            / "tidal-hifi.desktop"
        )
        text = desktop.read_text()
        assert "Exec=tidal-hifi --disable-dev-shm-usage" in text
        assert "--ozone-platform-hint=auto" in text
        assert "%U" in text

    def test_no_generated_palette_references_remain(self) -> None:
        """Epic 4: no task references generated/palettes or the deleted
        default-palette playbook."""
        text = (_ROLES_DIR / "tasks" / "main.yml").read_text()
        assert "generated/palettes" not in text, (
            "tasks must not reference generated/palettes (Epic 4 removed it)"
        )
        assert "default-palette" not in text and "default_palette" not in text, (
            "tasks must not reference the deleted default_palette role"
        )

    def test_config_dirs_ensured_via_file_directory(self) -> None:
        """Direct-run self-containment: a `file` `state: directory` task re-ensures
        the three compositor config dirs (copy does NOT create dest parents for
        file sources; the filesystem role created them on the bootstrap chain)."""
        dir_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.file")
            if "compositor_configs_config_dirs" in str(task.get("loop", ""))
        ]
        assert dir_tasks, "no config-dir ensure task found"
        for task in dir_tasks:
            assert _module(task)["state"] == "directory"
            assert task.get("when") is None, (
                "dir ensure is check-safe natively — must NOT be --check-gated"
            )

    def test_pinned_checkout_presence_is_asserted_before_rendering(self) -> None:
        """S2: the skeletons render FROM the pinned checkout, so a missing or
        mis-pinned corpus must fail loud and named (inside the role) rather than
        per-file with template's "Could not find". The stat is ungated (a probe)
        and the assert is real-run-only (a fresh --check has no checkout)."""
        stats = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if str(task.get("register")) == "compositor_configs_assets_configs_check"
        ]
        assert len(stats) == 1, "expected exactly one pinned-checkout stat"
        assert stats[0].get("when") is None
        assert "{{ compositor_configs_assets_configs_dir }}" in str(
            _module(stats[0]).get("path", "")
        )
        asserts = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if "compositor_configs_assets_configs_check" in str(_module(task).get("that", ""))
        ]
        assert len(asserts) == 1, "expected exactly one pinned-checkout assert"
        assert asserts[0].get("when") == "not ansible_check_mode"

    def test_invariant_documented_in_task_header(self) -> None:
        """Skeletons are repo-authoritative (owner decision 2026-08-26);
        palette fragments are runtime-owned (Epic 4 R2 symlinks — no copies)."""
        header = (_ROLES_DIR / "tasks" / "main.yml").read_text()
        assert "repo-authoritative" in header, (
            "task header must document 'repo-authoritative' (owner decision 2026-08-26)"
        )
        assert "R2" in header, (
            "task header must document the runtime R2 consumer symlinks (Epic 4)"
        )
        assert "1.12" in header, "task header must cite Story 1.12 for the guard"

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere —
        everything the role writes lives under the user's config dirs and
        install_dir."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path-bearing reference derives from the role vars
        (`{{ compositor_configs_repo_root }}`, `{{ install_dir | trim }}`,
        `{{ compositor_configs_xdg_config_home }}`) — no literal absolute path
        is baked into any task's module body OR into vars/main.yml."""
        safe_vars = (
            "compositor_configs_repo_root",
            "compositor_configs_assets_configs_dir",
            "compositor_configs_xdg_config_home",
            "install_dir",
            "ansible_facts.env",
        )
        for source_name, source_data in (
            ("tasks", _load_tasks()),
            ("vars", _vars()),
        ):
            text = str(source_data)
            for token in text.split():
                if token.startswith("/") and not any(var in token for var in safe_vars):
                    raise AssertionError(
                        f"{source_name}/main.yml hardcodes an absolute path: {token!r} (trim lock)"
                    )


class TestBarValidateGate:
    """Task 2.1: `ags-bar-validate` wired into provisioning as a STRICT gate.

    The gate runs the DEPLOYED validator over the DEPLOYED icons artifact and
    fails the install on any rule error — no `failed_when: false`, no
    `ignore_errors`. Version drift is a WARNING (task 2.3: warn and degrade,
    never crash), so only errors fail. There is no `bar.json` in the repo
    today (no user/runtime layout override exists), so the gate passes no
    `--layout` and validates the repo-default layout floor."""

    _GATE_NAME = "Validate the deployed bar artifacts (strict install gate)"

    def _gate(self) -> dict[str, object]:
        task = next((t for t in _load_tasks() if t.get("name") == self._GATE_NAME), None)
        assert task is not None, "missing the strict bar-validate gate task"
        return task

    def test_gate_runs_the_deployed_validator_over_the_deployed_artifact(
        self,
    ) -> None:
        """The gate must invoke the DEPLOYED `validate-cli.ts` against the
        DEPLOYED icons.json (the file the bar reads), with the role's OWNED
        schema version as the expectation — never the repo source, never a
        hardcoded version. The validator path is the realpath the resolution
        task produced (see test_gate_resolves_the_validator_real_path): the
        live bar is a symlink and node would otherwise no-op the CLI's
        `invokedAsMain` guard."""
        task = self._gate()
        assert _module_key(task) == "ansible.builtin.command", (
            "the gate must run the validator via ansible.builtin.command (no shell)"
        )
        cmd = _module_text(task)
        assert "compositor_configs_bar_validate_cli" in cmd, (
            "the gate must run the realpath-resolved validator (node realpaths "
            "the module URL but not argv[1], so the symlink path would no-op "
            "the CLI and pass the gate without validating anything)"
        )
        assert "compositor_configs_icon_manifest_dest" in cmd, (
            "the gate must validate the DEPLOYED icons.json (the file the bar reads)"
        )
        assert "compositor_configs_icon_manifest_schema_version" in cmd, (
            "the gate must pass the role's OWNED schema version (single owner)"
        )
        assert "--layout" not in cmd, (
            "no bar.json exists in the repo today — the gate validates the "
            "repo-default layout floor, it must not invent a layout path"
        )

    def test_gate_resolves_the_validator_real_path(self) -> None:
        """The live bar is a symlink; node realpaths `import.meta.url` but
        leaves `process.argv[1]` as given, so the deployed CLI's
        `invokedAsMain` guard is FALSE through the link and the strict gate
        silently exits 0. The role must resolve the real path (`readlink -f`)
        and gate on that instead — never the symlink path."""
        task = next(
            (
                t
                for t in _load_tasks()
                if t.get("name") == "Resolve the deployed bar validator's real path"
            ),
            None,
        )
        assert task is not None, "missing the validator realpath resolution task"
        assert _module_key(task) == "ansible.builtin.command"
        argv = _module(task).get("argv")
        assert isinstance(argv, list), (
            "the resolution must use argv (no shell string splitting)"
        )
        assert [str(a) for a in argv][:2] == ["readlink", "-f"], (
            "the task must resolve the symlink with `readlink -f`"
        )
        assert any(
            str(a).endswith("/ags/bar/validate-cli.ts") for a in argv
        ), "the task must resolve the deployed CLI through the live-bar link"
        assert task.get("changed_when") is False, "resolution writes nothing"
        assert "not ansible_check_mode" in str(task.get("when", "")), (
            "the deployed file does not exist yet under --check"
        )

    def test_gate_is_strict(self) -> None:
        """STRICT means ansible's default failure semantics: a non-zero
        validator exit fails the install. Any `failed_when: false`,
        `ignore_errors`, or swallowing `failed_when` would make a bad artifact
        a green install."""
        task = self._gate()
        assert "failed_when" not in task, "the strict gate must not set failed_when"
        assert "ignore_errors" not in task, "the strict gate must not set ignore_errors"

    def test_gate_writes_nothing_is_check_gated_and_unprivileged(self) -> None:
        """The gate is a read-only probe: `changed_when: false` (never counts
        as changed), `when: not ansible_check_mode` (the deployed files it
        reads do not exist yet under --check), and no become (user-scoped
        role, like every other task here)."""
        task = self._gate()
        assert task.get("changed_when") is False, "the gate must not report changed"
        assert "not ansible_check_mode" in str(task.get("when", "")), (
            "the gate must be skipped under --check"
        )
        assert "become" not in task, "the strict gate must not use become"

    def test_gate_runs_after_generation(self) -> None:
        """Ordering: the gate reads the GENERATED icons.json and the UNIT's
        validate-cli.ts (deployed by the ags_apps role BEFORE this role runs
        in bootstrap order — slice 2 retired the per-file CLI placement), so
        it must run after BOTH icons.json generations. A gate placed earlier
        would validate a missing icons.json."""
        names = [str(t.get("name", "")) for t in _load_tasks()]
        gate = names.index(self._GATE_NAME)
        assert gate > names.index("Generate AGS JSON manifest from icon mappings")
        assert gate > names.index("Generate capture AGS JSON manifest from icon mappings")

    def test_gate_fails_the_install_on_a_bad_icons_artifact(self) -> None:
        """Acceptance (task 2.1): a bad icons.json FAILS the install. Runs the
        real playbook with an icons.yaml declaring no group the bar reads, so
        the generated icons.json violates `missing-icon-key` and the strict
        gate aborts the run. The unit's CLI is pre-seeded exactly as the
        ags_apps role deploys it (live-bar link into the pinned unit —
        bootstrap order guarantees the unit is installed first)."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        if shutil.which("node") is None:
            pytest.skip("node not on PATH — the strict bar gate runs validate-cli.ts via node")
        playbook = _ANSIBLE_DIR / "playbooks" / "compositor-configs.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()
            # S2: the skeletons render FROM the pinned assets configs class; the
            # gate failure below must come from icons.json, not a missing source.
            _seed_assets_configs(install)
            (home / ".local" / "bin").mkdir(parents=True)
            icon_mappings = install / "icon-mappings"
            icon_mappings.mkdir(parents=True)
            (icon_mappings / "icons.yaml").write_text("test-group: {}\n")
            # The unit's CLI is what the strict gate runs: pre-seed the live
            # bar exactly as the ags_apps role deploys it.
            _preseed_bar_unit(install)

            env = dict(os.environ)
            env["HOME"] = str(home)
            env["XDG_CONFIG_HOME"] = str(xdg)
            env["XDG_DATA_HOME"] = str(home / ".local" / "share")
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(playbook),
                    "-e",
                    f"install_dir={install}",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            combined = result.stdout + result.stderr
            assert result.returncode != 0, (
                "a bad icons.json must fail the install (strict gate)\n" + combined[-4000:]
            )
            assert self._GATE_NAME in combined, (
                "the failure must come from the strict bar gate\n" + combined[-4000:]
            )
            assert "missing-icon-key" in combined, (
                "the gate must surface the validator's missing-icon-key error\n"
                + combined[-4000:]
            )


class TestCompositorConfigsVars:
    _REQUIRED_KEYS = {
        "compositor_configs_repo_root",
        "compositor_configs_assets_pinned_tag",
        "compositor_configs_assets_configs_dir",
        "compositor_configs_xdg_config_home",
        "compositor_configs_xdg_state_home",
        "compositor_configs_state_current_dir",
        "compositor_configs_spine_config_dir",
        "compositor_configs_config_dirs",
        "compositor_configs_skeleton_files",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_xdg_state_home_mirrors_verify_derivation(self) -> None:
        """Story 1.12 (don't-clobber guard): the state root derives EXACTLY
        like the existing non-deprecated env-fact precedents
        (verify_xdg_state_home / filesystem_xdg_state_home): honors
        $XDG_STATE_HOME with the spec default ~/.local/state via
        ansible_facts.env (F4 lock) — and state_current_dir derives from it
        with the trim lock (stray-whitespace XDG values bit Story 1.11). NO
        second XDG resolution is introduced."""
        data = _vars()
        value = str(data["compositor_configs_xdg_state_home"])
        assert "ansible_facts.env.XDG_STATE_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "'/.local/state'" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"
        current = str(data["compositor_configs_state_current_dir"])
        assert current == "{{ compositor_configs_xdg_state_home | trim }}/dotfiles/current", (
            "state_current_dir must derive from compositor_configs_xdg_state_home "
            "(trim-locked, AD-5: state root is ALWAYS <XDG_STATE_HOME>/dotfiles/)"
        )

    def test_repo_root_mirrors_assets_repo_root(self) -> None:
        """The repo root is still the source of the bin scripts and desktop
        entries (S2 moved only the skeletons to the pinned corpus)."""
        data = _vars()
        assert str(data["compositor_configs_repo_root"]) == "{{ playbook_dir }}/../../../.."

    def test_configs_dir_is_the_pinned_assets_checkout(self) -> None:
        """S2: the skeleton sources are the pinned assets configs class."""
        data = _vars()
        configs_dir = str(data["compositor_configs_assets_configs_dir"])
        assert configs_dir == (
            "{{ install_dir | trim }}/assets/"
            "{{ compositor_configs_assets_pinned_tag }}/configs"
        ), configs_dir
        assert "dotfiles/config" not in configs_dir

    def test_assets_pin_mirrors_the_assets_manifest(self) -> None:
        """AD-6: the role's pin mirror equals `assets.tag` in the manifest."""
        import yaml

        data = _vars()
        repo_root = _ANSIBLE_DIR.parents[2]
        manifest = yaml.safe_load(
            (repo_root / "dotfiles" / "provisioning" / "assets.yaml").read_text()
        )
        assert str(data["compositor_configs_assets_pinned_tag"]) == manifest["assets"]["tag"]

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The copy destinations must resolve to the SAME location the filesystem
        role (2.5) created: honors $XDG_CONFIG_HOME with the spec default
        `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["compositor_configs_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_no_fragment_copies_var(self) -> None:
        """Epic 4: the compositor_configs_fragment_copies var is gone."""
        data = _vars()
        assert "compositor_configs_fragment_copies" not in data, (
            "fragment copies var must not exist (Epic 4 removed it)"
        )

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        data = _vars()
        text = str(data)
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text


class TestCompositorConfigsPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "compositor-configs.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["compositor_configs"]
        assert "become" not in play, "compositor-configs playbook must not use become"
        assert "become_user" not in play, "compositor-configs playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the compositor-configs playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "compositor-configs playbook must not use group_by"
        assert "groups" not in play, "compositor-configs playbook must not group hosts"

    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = dict(os.environ)
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                ansible_playbook,
                "--syntax-check",
                str(self._PATH),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_executes_and_places_skeletons_only(self) -> None:
        """Regression guard (review finding 2026-08-12): the role must ACTUALLY
        place the skeleton files — a directory-source `copy` + `force: false` +
        pre-existing dest dir is a silent no-op, which the structural tests
        could not catch. Run the real playbook against a temp HOME/XDG home and
        install_dir, and assert every skeleton file lands in the config-in-spine
        home (<install>/config/{hypr,hyprpaper,ags}/). Epic 4: NO palette
        fragments are placed (the runtime seeder owns the R2 consumer
        symlink); assert the fragment paths are absent after the run."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        if shutil.which("node") is None:
            pytest.skip("node not on PATH — the strict bar gate runs validate-cli.ts via node")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()
            # S2: the skeletons render FROM the pinned assets configs class.
            _seed_assets_configs(install)
            # ansible's copy module does not create the bin dest parent.
            (home / ".local" / "bin").mkdir(parents=True)
            # Assets-role outputs this role consumes (inputs, not generated):
            # the icon manifest source for icons.json generation. Seeded from
            # the REAL authored icons.yaml — the strict bar gate (task 2.1)
            # validates the generated icons.json against the manifest
            # declarations, so the historical `test-group: {}` stub (which
            # declares no group the bar reads) would fail the install by
            # design. A real install always carries the full authored map.
            icon_mappings = install / "icon-mappings"
            icon_mappings.mkdir(parents=True)
            repo_icons = _authored_icons_yaml()
            if repo_icons is None:
                pytest.skip(
                    "authored icons.yaml not found: provision the spine "
                    "(DOTFILES_INSTALL_SPINE / XDG_DATA_HOME) or set "
                    "DOTFILES_ASSETS_ICONS_YAML to an assets checkout"
                )
            shutil.copy(repo_icons, icon_mappings / "icons.yaml")
            # Bootstrap order: the ags_apps role deploys the live bar BEFORE
            # this role runs (icons.json generates through the link and the
            # strict gate runs the unit's CLI).
            unit_bar = _preseed_bar_unit(install)

            env = dict(os.environ)
            env["HOME"] = str(home)
            env["XDG_CONFIG_HOME"] = str(xdg)
            env["XDG_DATA_HOME"] = str(home / ".local" / "share")
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(self._PATH),
                    "-e",
                    f"install_dir={install}",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stdout + result.stderr

            # The live bar is the unit, not a per-file copy: the link resolves
            # into the pinned unit and the generated icons.json lands through
            # it. The remaining per-file skeletons are the non-bar set only.
            live = install / "config" / "ags"
            assert live.is_symlink(), "the live bar must be a symlink"
            assert live.resolve() == unit_bar.resolve(), (
                "the live bar must point at the pinned unit's bar/"
            )

            expected_skeletons = [
                install / "config" / "hypr" / "hyprland.lua",
                install / "config" / "hypr" / "keybindings.lua",
                install / "config" / "hypr" / "monitors.lua",
                install / "config" / "hypr" / "autostart.lua",
                install / "config" / "hypr" / "window-rules.lua",
                install / "config" / "hypr" / "animations.lua",
                install / "config" / "hypr" / "input.lua",
                install / "config" / "hypr" / "decoration.lua",
                install / "config" / "hypr" / "cursor.lua",
                install / "config" / "hypr" / "env-variables.lua",
                install / "config" / "hyprpaper" / "hyprpaper.conf",
                # Slice 2: the bar deploys whole via the live-bar symlink — no
                # per-file bar entry is placed. The GENERATED icons.json lands
                # through the link into the pinned unit (asserted is-file
                # through the symlink, exactly as the strict gate reads it).
                install / "config" / "ags" / "icons.json",
            ]
            for path in expected_skeletons:
                assert path.is_file(), f"skeleton {path} was never placed (silent no-op?)"
            desktop_entry = (
                home / ".local" / "share" / "applications" / "tidal-hifi.desktop"
            )
            assert desktop_entry.is_file(), (
                "desktop entry override was not placed into "
                "$XDG_DATA_HOME/applications (rofi drun would miss it)"
            )
            assert "--disable-dev-shm-usage" in desktop_entry.read_text(), (
                "the TIDAL desktop override must carry the /dev/shm workaround flag"
            )
            assert not (install / "config" / "hypr" / "colors.conf").exists(), (
                "Epic 4: the role must NOT place a hypr/colors.conf fragment"
            )
            assert not (install / "config" / "ags" / "colors.css").exists(), (
                "Epic 4: the role must NOT place an ags/colors.css fragment "
                "(the runtime seeder owns the R2 consumer symlink)"
            )

            hypr_content = (install / "config" / "hypr" / "hyprland.lua").read_text()
            # The module include dir must render the resolved XDG config home
            # through which the ~/.config symlink resolves into the spine (P1).
            expected_cfg = f'local cfg = "{xdg}/hypr"'
            assert expected_cfg in hypr_content, (
                "hyprland.lua cfg variable must render the resolved XDG config home "
                "(P1)"
            )
            assert 'dofile(cfg .. "/keybindings.lua")' in hypr_content, (
                "hyprland.lua must include keybindings.lua via dofile"
            )

    def test_playbook_leaves_palette_paths_untouched(self) -> None:
        """Epic 4 migration contract: the role is hands-off palette paths.
        On a machine where the runtime owns the palette, an R2 symlink at
        <install>/config/ags/colors.css must survive re-provisioning
        UNCHANGED (islnk, same target). A stale pre-Epic-4 COPY is likewise
        left byte-identical (the role neither creates, updates, nor removes
        palette content — migration happens via the next `wallpaper set`,
        which replaces copies with R2 symlinks)."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        if shutil.which("node") is None:
            pytest.skip("node not on PATH — the strict bar gate runs validate-cli.ts via node")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            state = Path(tmp) / "state"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()
            # S2: the skeletons render FROM the pinned assets configs class.
            _seed_assets_configs(install)
            # ansible's copy module does not create the bin dest parent.
            (home / ".local" / "bin").mkdir(parents=True)
            # Assets-role outputs this role consumes (inputs, not generated).
            # Seeded from the REAL authored icons.yaml: the strict bar gate
            # (task 2.1) validates the generated icons.json, so the stub would
            # fail this run by design (see the gate-failure test below).
            icon_mappings = install / "icon-mappings"
            icon_mappings.mkdir(parents=True)
            repo_icons = _authored_icons_yaml()
            if repo_icons is None:
                pytest.skip(
                    "authored icons.yaml not found: provision the spine "
                    "(DOTFILES_INSTALL_SPINE / XDG_DATA_HOME) or set "
                    "DOTFILES_ASSETS_ICONS_YAML to an assets checkout"
                )
            shutil.copy(repo_icons, icon_mappings / "icons.yaml")

            # Bootstrap order: the live bar link exists before this role
            # runs (see _preseed_bar_unit). The runtime R2 colors.css pointer
            # lands THROUGH the link — inside the fixture unit, exactly as on
            # a host the ags_apps role upgraded.
            _preseed_bar_unit(install)
            current = state / "dotfiles" / "current"
            current.mkdir(parents=True)
            (current / "colors.gtk.css").write_text("@define-color color_00 #111111;\n")
            ags_colors = install / "config" / "ags" / "colors.css"
            runtime_target = current / "colors.gtk.css"
            ags_colors.symlink_to(runtime_target)
            # Stale pre-Epic-4 copy the role must not touch either way.
            stale_copy = install / "config" / "hypr" / "colors.conf"
            stale_copy.parent.mkdir(parents=True)
            stale_copy.write_text("$background = 0x000000\n")

            env = dict(os.environ)
            env["HOME"] = str(home)
            env["XDG_CONFIG_HOME"] = str(xdg)
            env["XDG_STATE_HOME"] = str(state)
            env["XDG_DATA_HOME"] = str(home / ".local" / "share")
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(self._PATH),
                    "-e",
                    f"install_dir={install}",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stdout + result.stderr

            assert ags_colors.is_symlink(), (
                "the runtime R2 symlink must survive re-provisioning untouched"
            )
            assert os.readlink(ags_colors) == str(runtime_target), (
                "the runtime symlink target must be unchanged after re-provisioning"
            )
            assert (current / "colors.gtk.css").read_text() == (
                "@define-color color_00 #111111;\n"
            ), "the state-owned palette file must be untouched (provisioning never writes under state_root)"
            assert stale_copy.is_file() and not stale_copy.is_symlink(), (
                "a stale pre-Epic-4 copy is left byte-identical (migration "
                "happens via the next `wallpaper set`, not provisioning)"
            )
            assert "$background = 0x000000" in stale_copy.read_text()


class TestDeployCoverageGate:
    """The deploy-coverage gate (scripts/deploy-coverage.py) asserts the
    provisioning SHAPE of the external bar + platform units.

    The bar deploys WHOLE via the pinned `ags_apps` unit and the platform is
    the external `ags-platform` bare specifier (spine AD-17), so the gate no
    longer diffs the in-repo tree's import closure against the manifest. It
    instead proves no stale per-file bar entry remains, the retired in-place
    `platform/` dir is gone, and both unit roles provision their pinned unit +
    shortcut. The in-repo `dotfiles/config/ags/` bridge is NOT required: the
    positive cases run both WITH the real tree and with it ABSENT. The negative
    cases are hermetic (a temp root whose ags tree is symlinked and whose
    manifest is a modified copy — the ags sources are read-only input).
    """

    _SCRIPT = _ANSIBLE_DIR.parents[2] / "scripts" / "deploy-coverage.py"
    _VARS = "src/provisioning/ansible/roles/compositor_configs/vars/main.yml"
    _AGS = "dotfiles/config/ags"
    _RETIRED_CAPTURE_DIR = "src/gui-tools/capture-tool"
    _RETIRED_CLI_OUTPUT = "src/shared/cli-output"
    _RETIRED_CONFIG_ASSEMBLER_ENGINE = "src/shared/config-assembler-engine"
    _RETIRED_OCI_RUNTIME = "src/shared/oci-runtime"
    _RETIRED_SHARED_ROOT = "src/shared"
    _RETIRED_ITR = "src/cli-tools/icon-templates-renderer"
    _RETIRED_WEG = "src/cli-tools/wallpaper-effects-generator"
    _RETIRED_CSG = "src/cli-tools/color-scheme-generator"
    _RETIRED_CLI_TOOLS = "src/cli-tools"
    _CLI_MANIFEST = "dotfiles/provisioning/cli-tools.yaml"
    _APPS_VARS = "src/provisioning/ansible/roles/ags_apps/vars/main.yml"

    def _run(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self._SCRIPT), "--root", str(root)],
            capture_output=True,
            text=True,
        )

    def _seed_root(
        self,
        root: Path,
        repo_root: Path,
        roles: tuple[str, ...] = (
            "ags_platform",
            "ags_apps",
            "gui_tools",
            "cli_tools",
        ),
    ) -> None:
        """Seed a hermetic temp root for the gate.

        The real compositor manifest plus the named unit/app roles. The
        capture-tool app (GUI + Python backend) now lives entirely in the
        ags-apps unit, so the gate asserts the in-repo app dir is GONE and that
        ags_apps provisions both links; cli_tools is copied because the gate
        also rejects a stale backend copy task there.
        """
        vars_dst = root / self._VARS
        vars_dst.parent.mkdir(parents=True, exist_ok=True)
        vars_dst.write_text((repo_root / self._VARS).read_text())
        manifest_src = repo_root / self._CLI_MANIFEST
        manifest_dst = root / self._CLI_MANIFEST
        manifest_dst.parent.mkdir(parents=True, exist_ok=True)
        manifest_dst.write_text(manifest_src.read_text())
        for role in roles:
            shutil.copytree(
                repo_root / "src/provisioning/ansible/roles" / role,
                root / "src/provisioning/ansible/roles" / role,
            )

    def test_gate_passes_on_the_real_tree(self) -> None:
        repo_root = _ANSIBLE_DIR.parents[2]
        result = self._run(repo_root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PASS" in result.stdout
        assert "'cli-output' is consumed from its pinned repo" in result.stdout, (
            "the gate must report the retired in-tree cli-output package; recap:\n"
            + result.stdout
        )
        assert (
            "'config-assembler-engine' is consumed from its pinned repo"
            in result.stdout
        ), (
            "the gate must report the retired in-tree config-assembler-engine "
            "package; recap:\n" + result.stdout
        )
        assert "'oci-runtime' is consumed from its pinned repo" in result.stdout, (
            "the gate must report the retired in-tree oci-runtime package and "
            "the now-empty src/shared/ root; recap:\n" + result.stdout
        )
        assert "'itr' is provisioned from its pinned manifest entry" in result.stdout, (
            "the gate must report itr's pinned manifest entry and tag-bearing "
            "checkout; recap:\n" + result.stdout
        )
        assert "'weg' is provisioned from its pinned manifest entry" in result.stdout, (
            "the gate must report weg's pinned manifest entry and tag-bearing "
            "checkout; recap:\n" + result.stdout
        )
        assert "'csg' is provisioned from its pinned manifest entry" in result.stdout, (
            "the gate must report csg's pinned manifest entry, tag-bearing "
            "checkout and env-delivered image tag; recap:\n" + result.stdout
        )
        assert "six packages are consumed from their pinned repos" in result.stdout, (
            "the gate must report the terminal state: six pinned packages, both "
            "parent roots retired and exactly one in-repo source; recap:\n"
            + result.stdout
        )

    def test_gate_fails_when_the_retired_cli_output_tree_returns(self) -> None:
        """cli-tools-repos S1: `cli-output` is consumed from its pinned repo
        (v0.1.0), so the in-tree package is retired. A surviving copy is a
        second source of truth that no consumer installs — it must FAIL even
        when every pin still resolves the tag."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / self._RETIRED_CLI_OUTPUT
            stray.mkdir(parents=True)
            (stray / "pyproject.toml").write_text(
                '[project]\nname = "cli-output"\nversion = "0.1.0"\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-tree cli-output package "
                f"returns; recap:\n{result.stdout}"
            )
            assert "src/shared/cli-output" in result.stdout, (
                "the failure must name the retired in-tree cli-output dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_pyproject_pins_cli_output_by_path(self) -> None:
        """A `path =` source would resolve the local checkout instead of the
        tag while still importing fine, silently undoing S1. The gate reads
        every authored `pyproject.toml` under `src/`, so the pin cannot drift
        back one package at a time."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            pyproject = root / "src" / "runtime" / "pyproject.toml"
            pyproject.parent.mkdir(parents=True)
            pyproject.write_text(
                '[project]\nname = "dotfiles-runtime"\n'
                'dependencies = ["cli-output"]\n\n'
                "[tool.uv.sources]\n"
                'cli-output = { path = "../shared/cli-output", editable = true }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a pyproject pins cli-output by path; "
                f"recap:\n{result.stdout}"
            )
            assert "src/runtime/pyproject.toml" in result.stdout, (
                "the failure must name the offending pyproject; recap:\n"
                + result.stdout
            )
            assert "path" in result.stdout and "cli-output" in result.stdout, (
                "the failure must name the path pin; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_retired_config_assembler_engine_tree_returns(
        self,
    ) -> None:
        """cli-tools-repos S2: `config-assembler-engine` is consumed from its
        pinned repo (v0.1.0), so the in-tree package is retired. A surviving
        copy is a second source of truth that csg/weg/itr do not install — it
        must FAIL even when every pin still resolves the tag."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / self._RETIRED_CONFIG_ASSEMBLER_ENGINE
            stray.mkdir(parents=True)
            (stray / "pyproject.toml").write_text(
                '[project]\nname = "config-assembler-engine"\nversion = "0.1.0"\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-tree "
                "config-assembler-engine package returns; recap:\n" + result.stdout
            )
            assert "src/shared/config-assembler-engine" in result.stdout, (
                "the failure must name the retired in-tree "
                "config-assembler-engine dir; recap:\n" + result.stdout
            )

    def test_gate_fails_when_a_pyproject_pins_config_assembler_engine_by_path(
        self,
    ) -> None:
        """A `path =` source would resolve the local checkout instead of the
        tag while still importing fine, silently undoing S2. The gate reads
        every authored `pyproject.toml` under `src/`, so the pin cannot drift
        back one package at a time."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            pyproject = root / "src" / "cli-tools" / "example" / "pyproject.toml"
            pyproject.parent.mkdir(parents=True)
            pyproject.write_text(
                '[project]\nname = "example"\n'
                'dependencies = ["config-assembler-engine"]\n\n'
                "[tool.uv.sources]\n"
                'config-assembler-engine = { path = "../../shared/config-assembler-engine", '
                "editable = true }\n"
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a pyproject pins config-assembler-engine "
                f"by path; recap:\n{result.stdout}"
            )
            assert "src/cli-tools/example/pyproject.toml" in result.stdout, (
                "the failure must name the offending pyproject; recap:\n"
                + result.stdout
            )
            assert "path" in result.stdout and "config-assembler-engine" in (
                result.stdout
            ), "the failure must name the path pin; recap:\n" + result.stdout

    def test_gate_fails_when_the_retired_static_config_tree_returns(self) -> None:
        """S2: the static config corpus (hypr, hyprpaper, nvim, rofi, starship)
        moved to the pinned dotfiles-assets repo. A surviving in-tree dir is a
        second, unowned source of truth that the roles no longer read — the gate
        must FAIL even when every other shape is intact."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / "dotfiles" / "config" / "hypr"
            stray.mkdir(parents=True)
            (stray / "hyprland.lua").write_text("-- stray copy\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a retired static config dir returns; "
                f"recap:\n{result.stdout}"
            )
            assert "dotfiles/config/hypr" in result.stdout, (
                "the failure must name the retired dir; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_copied_wlogout_layout_returns(self) -> None:
        """S2: wlogout's DIRECTORY survives (it keeps style.css.tpl for S3), so
        the guard keys on the copied FILE — `layout` must not come back."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / "dotfiles" / "config" / "wlogout"
            stray.mkdir(parents=True)
            (stray / "style.css.tpl").write_text("x\n")
            (stray / "layout").write_text("{}\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the copied wlogout layout returns; "
                f"recap:\n{result.stdout}"
            )
            assert "dotfiles/config/wlogout/layout" in result.stdout, (
                "the failure must name the copied file; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_retired_oci_runtime_tree_returns(self) -> None:
        """cli-tools-repos S3: `oci-runtime` is consumed from its pinned repo
        (v0.5.0), so the in-tree package is retired. A surviving copy is a
        second source of truth that csg/weg do not install — it must FAIL even
        when every pin still resolves the tag."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / self._RETIRED_OCI_RUNTIME
            stray.mkdir(parents=True)
            (stray / "pyproject.toml").write_text(
                '[project]\nname = "oci-runtime"\nversion = "0.5.0"\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-tree oci-runtime "
                f"package returns; recap:\n{result.stdout}"
            )
            assert "src/shared/oci-runtime" in result.stdout, (
                "the failure must name the retired in-tree oci-runtime dir; "
                "recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_retired_shared_root_returns(self) -> None:
        """S3 deleted the last shared library, so `src/shared/` itself must be
        gone. An empty leftover is the obvious home for a re-vendored copy that
        no consumer installs."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            (root / self._RETIRED_SHARED_ROOT).mkdir(parents=True)
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired src/shared/ root returns; "
                f"recap:\n{result.stdout}"
            )
            assert "src/shared/" in result.stdout and "still exists" in result.stdout, (
                "the failure must name the retired shared-library root; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_pyproject_pins_oci_runtime_by_path(self) -> None:
        """A `path =` source would resolve the local checkout instead of the tag
        while still importing fine, silently undoing S3. The gate reads every
        authored `pyproject.toml` under `src/`, so the pin cannot drift back one
        package at a time."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            pyproject = root / "src" / "cli-tools" / "example" / "pyproject.toml"
            pyproject.parent.mkdir(parents=True)
            pyproject.write_text(
                '[project]\nname = "example"\n'
                'dependencies = ["oci-runtime"]\n\n'
                "[tool.uv.sources]\n"
                'oci-runtime = { path = "../../shared/oci-runtime", editable = true }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a pyproject pins oci-runtime by path; "
                f"recap:\n{result.stdout}"
            )
            assert "src/cli-tools/example/pyproject.toml" in result.stdout, (
                "the failure must name the offending pyproject; recap:\n"
                + result.stdout
            )
            assert "path" in result.stdout and "oci-runtime" in result.stdout, (
                "the failure must name the path pin; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_retired_itr_tree_returns(self) -> None:
        """cli-tools-repos S4: `itr` is consumed from its pinned repo
        (v0.1.0), so the in-tree package is retired. A surviving copy is a
        second source of truth that no consumer installs — it must FAIL even
        when the manifest and every pin still resolve the tag."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / self._RETIRED_ITR
            stray.mkdir(parents=True)
            (stray / "pyproject.toml").write_text(
                '[project]\nname = "icon-templates-renderer"\nversion = "0.1.0"\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-tree itr package "
                f"returns; recap:\n{result.stdout}"
            )
            assert "src/cli-tools/icon-templates-renderer" in result.stdout, (
                "the failure must name the retired in-tree itr dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_itr_keeps_a_source_path(self) -> None:
        """AD-10: an entry with BOTH a source and repo/tag lets the local path
        silently shadow the pin for one consumer. The gate must reject it
        rather than accept the repo+tag half."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: itr\n",
                    "  - name: itr\n    source: src/cli-tools/icon-templates-renderer\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when itr carries a source path AND a pin; "
                f"recap:\n{result.stdout}"
            )
            assert "source" in result.stdout and "itr" in result.stdout, (
                "the failure must name the offending source path; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_itr_loses_its_tag(self) -> None:
        """A repo without a tag has no pin: the role would clone a branch head
        and verify could never assert the tag. The gate must fail closed."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: itr\n"
                    "    repo: https://github.com/RandomGenericUsername/"
                    "icon-templates-renderer\n"
                    "    tag: v0.2.0\n",
                    "  - name: itr\n"
                    "    repo: https://github.com/RandomGenericUsername/"
                    "icon-templates-renderer\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the itr entry has a repo but no tag; "
                f"recap:\n{result.stdout}"
            )
            assert "tag" in result.stdout, (
                "the failure must name the missing tag; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_retired_weg_tree_returns(self) -> None:
        """cli-tools-repos S5: `weg` is consumed from its pinned repo (v0.1.0),
        so the in-tree package is retired. A surviving copy is a second source
        of truth that no consumer installs — it must FAIL even when the
        manifest and every pin still resolve the tag."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / self._RETIRED_WEG
            stray.mkdir(parents=True)
            (stray / "pyproject.toml").write_text(
                '[project]\nname = "wallpaper-effects-generator"\nversion = "0.1.0"\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-tree weg package "
                f"returns; recap:\n{result.stdout}"
            )
            assert "src/cli-tools/wallpaper-effects-generator" in result.stdout, (
                "the failure must name the retired in-tree weg dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_weg_keeps_a_source_path(self) -> None:
        """AD-10: an entry with BOTH a source and repo/tag lets the local path
        silently shadow the pin for one consumer. The gate must reject it."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: weg\n",
                    "  - name: weg\n"
                    "    source: src/cli-tools/wallpaper-effects-generator\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when weg carries a source path AND a pin; "
                f"recap:\n{result.stdout}"
            )
            assert "source" in result.stdout and "weg" in result.stdout, (
                "the failure must name the offending source path; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_weg_loses_its_tag(self) -> None:
        """A repo without a tag has no pin: the role would clone a branch head,
        the image tag could not be the pin, and verify could never assert it.
        The gate must fail closed."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: weg\n"
                    "    repo: https://github.com/RandomGenericUsername/"
                    "wallpaper-effects-generator\n"
                    "    tag: v0.2.0\n",
                    "  - name: weg\n"
                    "    repo: https://github.com/RandomGenericUsername/"
                    "wallpaper-effects-generator\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the weg entry has a repo but no tag; "
                f"recap:\n{result.stdout}"
            )
            assert "tag" in result.stdout, (
                "the failure must name the missing tag; recap:\n" + result.stdout
            )
            assert "weg" in result.stdout, (
                "the failure must name weg; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_pinned_image_is_built_at_another_tag(self) -> None:
        """AD-7: the image tag is the pin. A build that tags the image with a
        literal (e.g. `latest`) while `verify`/settings resolve the pin would
        ship a machine whose container mode pulls the wrong image — and a pin
        bump could silently reuse the previous one. The gate must fail."""
        repo_root = _ANSIBLE_DIR.parents[2]
        tasks_rel = "src/provisioning/ansible/roles/cli_tools/tasks/main.yml"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            tasks = root / tasks_rel
            text = tasks.read_text()
            replaced = text.replace(
                "      - --image-tag\n      - \"{{ item.tag }}\"\n",
                "      - --image-tag\n      - v0.1.0\n",
            )
            assert replaced != text, "seed did not contain the pinned --image-tag argv"
            tasks.write_text(replaced)
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the image build tags a literal instead "
                f"of the manifest pin; recap:\n{result.stdout}"
            )
            assert "image-tag" in result.stdout or "image tagged" in result.stdout, (
                "the failure must name the image tag; recap:\n" + result.stdout
            )

    def test_gate_fails_when_the_retired_csg_tree_returns(self) -> None:
        """cli-tools-repos S6: `csg` is consumed from its pinned repo (v0.1.0),
        so the in-tree package is retired. A surviving copy is a second source
        of truth that no consumer installs."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / self._RETIRED_CSG
            stray.mkdir(parents=True)
            (stray / "pyproject.toml").write_text(
                '[project]\nname = "color-scheme-generator"\nversion = "0.1.0"\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-tree csg package "
                f"returns; recap:\n{result.stdout}"
            )
            assert "src/cli-tools/color-scheme-generator" in result.stdout, (
                "the failure must name the retired in-tree csg dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_csg_keeps_a_source_path(self) -> None:
        """AD-10: an entry with BOTH a source and repo/tag lets the local path
        silently shadow the pin for one consumer."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: csg\n",
                    "  - name: csg\n"
                    "    source: src/cli-tools/color-scheme-generator\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when csg carries a source path AND a pin; "
                f"recap:\n{result.stdout}"
            )
            assert "source" in result.stdout and "csg" in result.stdout, (
                "the failure must name the offending source path; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_csg_loses_its_tag(self) -> None:
        """A repo without a tag has no pin: the role would clone a branch head,
        the images could not be tagged with the pin, and verify could never
        assert them."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: csg\n"
                    "    repo: https://github.com/RandomGenericUsername/"
                    "color-scheme-generator\n"
                    "    tag: v0.2.0\n",
                    "  - name: csg\n"
                    "    repo: https://github.com/RandomGenericUsername/"
                    "color-scheme-generator\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the csg entry has a repo but no tag; "
                f"recap:\n{result.stdout}"
            )
            assert "tag" in result.stdout and "csg" in result.stdout, (
                "the failure must name the missing tag and csg; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_csg_image_tag_is_a_literal(self) -> None:
        """AD-7 for the ENV transport: csg's verb has no `--image-tag`, so the
        pin reaches it as COLORSCHEME__CONTAINER__IMAGE_TAG. A literal there
        (e.g. `latest`) would ship images the rendered settings never resolve."""
        repo_root = _ANSIBLE_DIR.parents[2]
        tasks_rel = "src/provisioning/ansible/roles/cli_tools/tasks/main.yml"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            tasks = root / tasks_rel
            text = tasks.read_text()
            replaced = text.replace(
                'COLORSCHEME__CONTAINER__IMAGE_TAG: "{{ item.tag }}"',
                'COLORSCHEME__CONTAINER__IMAGE_TAG: "v0.1.0"',
            )
            assert replaced != text, "seed did not contain the env-delivered tag"
            tasks.write_text(replaced)
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the env-delivered image tag is a "
                f"literal instead of the manifest pin; recap:\n{result.stdout}"
            )
            assert "image tag" in result.stdout or "literal image tag" in (
                result.stdout
            ), "the failure must name the image tag; recap:\n" + result.stdout

    def test_gate_fails_when_the_retired_cli_tools_root_returns(self) -> None:
        """S6 terminal catch-all: with the last CLI extracted, the parent
        `src/cli-tools/` root is retired. An empty leftover is the obvious home
        for a re-vendored copy that no consumer installs."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            (root / self._RETIRED_CLI_TOOLS).mkdir(parents=True)
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired src/cli-tools/ root "
                f"returns; recap:\n{result.stdout}"
            )
            assert "src/cli-tools/" in result.stdout and "still exists" in (
                result.stdout
            ), "the failure must name the retired CLI-tools root; recap:\n" + (
                result.stdout
            )

    def test_gate_fails_when_a_second_local_source_appears(self) -> None:
        """AD-11 (final, strict): `dotfiles-runtime -> src/runtime` is the ONE
        permitted in-repo source. A second one reopens the mixed-shape window
        the extraction closed."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text()
                + "  - name: stray-tool\n    source: src/stray-tool\n"
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the manifest carries a second local "
                f"source; recap:\n{result.stdout}"
            )
            assert "exactly ONE `source:`" in result.stdout or "one in-repo source" in (
                result.stdout
            ), "the failure must name the single-source rule; recap:\n" + result.stdout

    def test_gate_fails_when_the_only_source_is_not_the_runtime(self) -> None:
        """The permitted local source is the runtime this repo authors, not any
        other tree: a `source:` re-pointed at an extracted package would install
        it from a path while the manifest still looks pinned."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            manifest = root / self._CLI_MANIFEST
            manifest.write_text(
                manifest.read_text().replace(
                    "  - name: dotfiles-runtime\n    source: src/runtime\n",
                    "  - name: dotfiles-runtime\n"
                    "    source: src/cli-tools/color-scheme-generator\n",
                )
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the only local source is not "
                f"src/runtime; recap:\n{result.stdout}"
            )
            assert "dotfiles-runtime" in result.stdout and "src/runtime" in (
                result.stdout
            ), "the failure must name the permitted source; recap:\n" + result.stdout

    def test_gate_passes_when_the_in_repo_bridge_is_absent(self) -> None:
        """Slice 1: the gate asserts the provisioning SHAPE, so it must exit 0
        with NO in-repo `dotfiles/config/ags/` tree at all (the bridge is
        retired). Hermetic: a temp root carrying only the real manifest and both
        unit roles, with the ags tree deliberately absent."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            assert not (root / self._AGS).exists()
            result = self._run(root)
            assert result.returncode == 0, result.stdout + result.stderr
            assert "PASS" in result.stdout
            assert "bridge retired" in result.stdout, result.stdout

    def test_gate_fails_when_a_stale_hypr_pano_entry_returns(self) -> None:
        """Slice 3: a per-file hypr-pano entry in the gui_tools manifest must
        FAIL. The overlay deploys WHOLE via the unit symlink, so any
        ags-hypr-pano/ source would template INTO the unit tree through the
        live-pano link and silently diverge the live app from the pinned tag.
        Hermetic: a temp root whose gui_tools vars re-add the retired
        gui_tools_hypr_pano_app_files — plus both unit roles, which the gate
        asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            gui_vars = (
                root / "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
            )
            gui_vars.write_text(
                gui_vars.read_text()
                + "\ngui_tools_hypr_pano_app_files:\n"
                + "  - { name: stale-pano-app, "
                + "source: src/gui-tools/hypr-pano/app.tsx, "
                + "dest: \"{{ gui_tools_spine_config_dir }}/ags-hypr-pano/app.tsx\" }\n"
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file hypr-pano entry is "
                f"listed; recap:\n{result.stdout}"
            )
            assert "gui_tools_hypr_pano_app_files" in result.stdout, (
                "the failure must name the stale hypr-pano entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_stale_notifications_entry_returns(self) -> None:
        """Slice 4: a per-file notifications entry in the gui_tools manifest must
        FAIL. The daemon deploys WHOLE via the unit symlink, so any
        ags-notifications/ source would template INTO the unit tree through the
        live-notifications link and silently diverge the live daemon from the
        pinned tag. Hermetic: a temp root whose gui_tools vars re-add the retired
        gui_tools_notifications_app_files — plus both unit roles, which the gate
        asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            gui_vars = (
                root / "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
            )
            gui_vars.write_text(
                gui_vars.read_text()
                + "\ngui_tools_notifications_app_files:\n"
                + "  - { name: stale-notifications-app, "
                + "source: src/gui-tools/notifications/app.tsx, "
                + 'dest: "{{ gui_tools_spine_config_dir }}/ags-notifications/app.tsx" }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file notifications entry is "
                f"listed; recap:\n{result.stdout}"
            )
            assert "gui_tools_notifications_app_files" in result.stdout, (
                "the failure must name the stale notifications entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_stale_bar_entry_returns(self) -> None:
        """Slice 2: a per-file bar entry in the skeleton list must FAIL. The
        bar deploys WHOLE via the unit symlink, so any `dotfiles/config/ags/`
        source would template INTO the unit tree through the live-bar link and
        silently diverge the live bar from the pinned tag. Hermetic: a temp
        root whose ags tree is symlinked and whose manifest is a modified copy
        carrying one stale bar entry — plus both unit roles, which the gate
        asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dotfiles" / "config").mkdir(parents=True)
            (root / "dotfiles" / "config" / "ags").symlink_to(
                repo_root / self._AGS, target_is_directory=True
            )
            vars_src = (repo_root / self._VARS).read_text()
            # Smuggle a STALE per-file bar entry back into the manifest copy.
            # bar/Bar.tsx is the composition root's first import — the
            # archetypal entry the retired bridge used to carry.
            rofi_line = next(
                line
                for line in vars_src.splitlines()
                if "name: rofi-launcher-config-rasi" in line
            )
            stale_line = (
                "  - { name: stale-bar-backdrop, "
                "source: dotfiles/config/ags/bar/Bar.tsx, "
                "dest: \"{{ compositor_configs_spine_config_dir }}/ags/bar/Bar.tsx\" }"
            )
            vars_dst = root / self._VARS
            vars_dst.parent.mkdir(parents=True)
            vars_dst.write_text(vars_src.replace(rofi_line, rofi_line + "\n" + stale_line, 1))
            # The gate also asserts both unit roles exist (the platform unit +
            # shared-ancestor shortcut, and the bar unit + live link), so copy
            # them into the temp root.
            for role in ("ags_platform", "ags_apps"):
                shutil.copytree(
                    repo_root / "src/provisioning/ansible/roles" / role,
                    root / "src/provisioning/ansible/roles" / role,
                )

            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file bar entry is listed; "
                f"recap:\n{result.stdout}"
            )
            assert "dotfiles/config/ags/bar/Bar.tsx" in result.stdout, (
                "the failure must name the stale bar entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_relative_import_targets_the_retired_platform(self) -> None:
        """A relative import into the deleted in-place platform copy must FAIL,
        not be skipped: `_resolve` cannot see a missing module, so the gate
        rejects the retired `platform/` segment explicitly. Hermetic: a minimal
        temp ags tree whose entry imports the retired path."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ags = root / self._AGS
            ags.mkdir(parents=True)
            (ags / "app.tsx").write_text(
                'import { theme } from "./platform/adapters/theme"\nexport default theme\n'
            )
            # The manifest and the platform-role vars are real inputs (read-only).
            (root / self._VARS).parent.mkdir(parents=True)
            (root / self._VARS).write_text((repo_root / self._VARS).read_text())
            role = root / "src" / "provisioning" / "ansible" / "roles" / "ags_platform"
            role.mkdir(parents=True)
            (role / "vars").mkdir()
            (role / "vars" / "main.yml").write_text(
                (
                    repo_root
                    / "src/provisioning/ansible/roles/ags_platform/vars/main.yml"
                ).read_text()
            )
            (role / "tasks").mkdir()
            (role / "tasks" / "main.yml").write_text(
                (
                    repo_root
                    / "src/provisioning/ansible/roles/ags_platform/tasks/main.yml"
                ).read_text()
            )

            result = self._run(root)
            assert result.returncode != 0, (
                "a relative import into the retired platform must FAIL; recap:\n"
                + result.stdout
            )
            assert "retired in-place platform" in result.stdout, (
                "the failure must name the retired platform path; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_stale_capture_gui_entry_returns(self) -> None:
        """Slice 5: a per-file capture GUI entry in the gui_tools manifest must
        FAIL. The GUI deploys WHOLE via the unit symlink, so any ags-capture/
        source would template INTO the unit tree through the live-capture link and
        silently diverge the live GUI from the pinned tag. Hermetic: a temp root
        whose gui_tools vars re-add a retired gui_tools_app_files — plus both unit
        roles and cli_tools, which the gate asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            gui_vars = root / "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
            gui_vars.write_text(
                gui_vars.read_text()
                + "\ngui_tools_app_files:\n"
                + "  - { name: stale-capture-app, "
                + "source: src/gui-tools/capture-tool/app.tsx, "
                + 'dest: "{{ gui_tools_spine_config_dir }}/ags-capture/app.tsx" }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file capture GUI entry is "
                f"listed; recap:\n{result.stdout}"
            )
            assert "ags-capture/" in result.stdout, (
                "the failure must name the stale capture entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_retired_capture_tool_dir_returns(self) -> None:
        """v0.4.0: capture-tool is a WHOLE package — the GUI AND the Python
        backend ship in the ags-apps unit (capture-tool/bin/capture-tool +
        tests/python/), so the entire in-repo dir must be gone. A surviving
        backend is a second source of truth the ags_apps symlink would bypass."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stale = root / self._RETIRED_CAPTURE_DIR / "bin"
            stale.mkdir(parents=True)
            (stale / "capture-tool").write_text("#!/usr/bin/env python3\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-repo capture-tool dir "
                f"returns; recap:\n{result.stdout}"
            )
            assert "capture-tool" in result.stdout, (
                "the failure must name the retired capture-tool dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_retired_gui_tools_root_returns(self) -> None:
        """The in-repo GUI source ROOT is retired: every app deploys WHOLE from
        the ags-apps unit, so `src/gui-tools/` must not exist even as an empty
        leftover. The per-app checks catch a known app name; this catch-all
        proves an UNKNOWN leftover cannot make the emptied directory look like a
        legitimate home for a future in-repo GUI source."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stray = root / "src" / "gui-tools"
            stray.mkdir(parents=True)
            (stray / "README.md").write_text("# stray in-repo GUI source\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-repo GUI source root "
                f"returns; recap:\n{result.stdout}"
            )
            assert "src/gui-tools" in result.stdout, (
                "the failure must name the retired GUI source root; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_capture_cli_symlink_is_not_provisioned(self) -> None:
        """The CLI must be installed from the unit. If ags_apps stops declaring
        the bin-dir symlink (backend source + entry point), deleting the in-repo
        app would leave the gate green with no `capture-tool` on PATH — the
        silent-coverage-loss this gate exists to prevent."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            apps_vars = root / self._APPS_VARS
            text = apps_vars.read_text()
            removed = "\n".join(
                line
                for line in text.splitlines()
                if "ags_apps_capture_tool_bin_link" not in line
            )
            apps_vars.write_text(removed + "\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the bin-dir CLI symlink is no longer "
                f"declared; recap:\n{result.stdout}"
            )
            assert "bin" in result.stdout.lower(), (
                "the failure must name the missing CLI link; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_stale_wallpaper_selector_entry_returns(self) -> None:
        """Slice 6: a per-file wallpaper-selector entry in the gui_tools manifest
        must FAIL. The selector deploys WHOLE via the unit symlink, so any
        ags-wallpaper-selector/ source would template INTO the unit tree through the
        live-wallpaper-selector link and silently diverge the live selector from the
        pinned tag. Hermetic: a temp root whose gui_tools vars re-add a retired
        gui_tools_wallpaper_selector_app_files — plus both unit roles, which the
        gate asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            gui_vars = root / "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
            gui_vars.write_text(
                gui_vars.read_text()
                + "\ngui_tools_wallpaper_selector_app_files:\n"
                + "  - { name: stale-selector-app, "
                + "source: src/gui-tools/wallpaper-selector/app.tsx, "
                + 'dest: "{{ gui_tools_spine_config_dir }}/ags-wallpaper-selector/app.tsx" }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file wallpaper-selector entry "
                f"is listed; recap:\n{result.stdout}"
            )
            assert "wallpaper-selector" in result.stdout, (
                "the failure must name the stale selector entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_retired_wallpaper_selector_dir_returns(self) -> None:
        """Slice 6: the wallpaper selector is a WHOLE package — the entire in-repo
        src/gui-tools/wallpaper-selector/ dir must be gone. A surviving copy is a
        second source of truth that no gate deploys, so the gate must FAIL when it
        exists even with the per-file manifest correctly retired."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stale = root / "src" / "gui-tools" / "wallpaper-selector"
            stale.mkdir(parents=True)
            (stale / "app.tsx").write_text("export {}\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-repo wallpaper-selector "
                f"dir returns; recap:\n{result.stdout}"
            )
            assert "wallpaper-selector" in result.stdout, (
                "the failure must name the retired selector dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_stale_icme_entry_returns(self) -> None:
        """Slice 7: a per-file icme entry in the gui_tools manifest must FAIL.
        The editor deploys WHOLE via the unit symlink, so any ags-icme/ source
        would template INTO the unit tree through the live-icme link and silently
        diverge the live editor from the pinned tag. Hermetic: a temp root whose
        gui_tools vars re-add a retired gui_tools_icme_app_files — plus both unit
        roles, which the gate asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            gui_vars = root / "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
            gui_vars.write_text(
                gui_vars.read_text()
                + "\ngui_tools_icme_app_files:\n"
                + "  - { name: stale-icme-app, "
                + "source: src/gui-tools/icon-color-mapping-editor/app.tsx, "
                + 'dest: "{{ gui_tools_spine_config_dir }}/ags-icme/app.tsx" }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file icme entry is listed; "
                f"recap:\n{result.stdout}"
            )
            assert "gui_tools_icme_app_files" in result.stdout, (
                "the failure must name the stale icme entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_retired_icme_dir_returns(self) -> None:
        """Slice 7: icme is a WHOLE package — the entire in-repo
        src/gui-tools/icon-color-mapping-editor/ dir must be gone. A surviving
        copy is a second source of truth that no gate deploys, so the gate must
        FAIL when it exists even with the per-file manifest correctly retired."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stale = root / "src" / "gui-tools" / "icon-color-mapping-editor"
            stale.mkdir(parents=True)
            (stale / "app.tsx").write_text("export {}\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-repo icme dir returns; "
                f"recap:\n{result.stdout}"
            )
            assert "icon-color-mapping-editor" in result.stdout, (
                "the failure must name the retired icme dir; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_a_stale_btop_studio_entry_returns(self) -> None:
        """Slice 8: a per-file btop Theme Studio entry in the gui_tools manifest
        must FAIL. The studio deploys WHOLE via the unit symlink, so any
        ags-btop-studio/ source would template INTO the unit tree through the
        live-btop-studio link and silently diverge the live studio from the
        pinned tag. Hermetic: a temp root whose gui_tools vars re-add a retired
        gui_tools_btop_studio_app_files — plus both unit roles, which the gate
        asserts."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            gui_vars = root / "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
            gui_vars.write_text(
                gui_vars.read_text()
                + "\ngui_tools_btop_studio_app_files:\n"
                + "  - { name: stale-studio-app, "
                + "source: src/gui-tools/btop-theme-studio/app.tsx, "
                + 'dest: "{{ gui_tools_spine_config_dir }}/ags-btop-studio/app.tsx" }\n'
            )
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a stale per-file studio entry is listed; "
                f"recap:\n{result.stdout}"
            )
            assert "gui_tools_btop_studio_app_files" in result.stdout, (
                "the failure must name the stale studio entry; recap:\n"
                + result.stdout
            )

    def test_gate_fails_when_the_retired_btop_studio_dir_returns(self) -> None:
        """Slice 8: the studio is a WHOLE package — the entire in-repo
        src/gui-tools/btop-theme-studio/ dir must be gone, including its live/
        preview engine. A surviving copy is a second source of truth that no gate
        deploys, so the gate must FAIL when it exists even with the per-file
        manifest correctly retired."""
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_root(root, repo_root)
            stale = root / "src" / "gui-tools" / "btop-theme-studio"
            stale.mkdir(parents=True)
            (stale / "app.tsx").write_text("export {}\n")
            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when the retired in-repo studio dir returns; "
                f"recap:\n{result.stdout}"
            )
            assert "btop-theme-studio" in result.stdout, (
                "the failure must name the retired studio dir; recap:\n"
                + result.stdout
            )
