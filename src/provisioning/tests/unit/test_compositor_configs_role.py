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


class TestCompositorConfigsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_icme_chooser_rule_matches_every_editor_dialog(self) -> None:
        """The icme-filechooser-replaces-editor rule must match EVERY file
        chooser the editor can open — Mappings inputs + Templates picker —
        so all of them float centered at editor size instead of tiling.

        The rule matches portal-window TITLES, and those titles are the
        GUI dialogs' own label strings: renaming a dialog (as happened to
        'SVG template root (read-only)' and to the new Templates 'Template
        file') silently drops the rule for that chooser. Lock the rule to
        the GUI source."""
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

        gui = (
            _ANSIBLE_DIR.parents[2]
            / "src"
            / "gui-tools"
            / "icon-color-mapping-editor"
            / "ui"
        )
        inputs = (gui / "InputsPanel.tsx").read_text()
        templates = (gui / "TemplatesTab.tsx").read_text()
        # InputsPanel: chooser titles are the InputRow labels — the '⋯' pick-button
        # label is not a dialog title. Scope to the rows array literal only.
        rows_src = inputs[inputs.index("const rows") :]
        rows_src = rows_src[: rows_src.index("];") + 2]
        inputs_titles = [
            t for t in re.findall(r'label: "([^"]+)"', rows_src) if t != "⋯"
        ]
        tpl_titles = re.findall(r'title: "([^"]+)"', templates)
        all_titles = inputs_titles + tpl_titles
        assert all_titles, "no editor file-chooser titles found in GUI source"
        for title in all_titles:
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
        `{{ compositor_configs_repo_root }}/dotfiles/config/<dir>/<file>` and a
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
        # capture tool files (CaptureWindow.tsx, types.ts, app.tsx, style.css)
        # are standalone under src/gui-tools/capture-tool/ and deploy via the
        # gui_tools role — no longer part of the compositor_configs skeletons.
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
        # sources the platform work added but the manifest missed: kit/icon-source
        # + kit/shapes, the reactive domain port/binding and the network/battery/
        # bluetooth/audio Astal adapters, and the Bluetooth widget/popup/state +
        # settings SubviewHeader that had silently never deployed. Placement here is
        # PER FILE, so an unregistered file silently never deploys and the panel
        # imports a module that is not there on the desktop: this assertion is
        # what makes that fail loudly at review time instead of at runtime. Do NOT
        # relax it to `>=`, a subset check, or delete it — those all convert
        # "deploys nothing" into "passes".
        # 108 once surfaces-popup-host (AD-10) added kit/surface.ts (the pure
        # SurfaceSpec/registry/mount policy) and kit/popup-host.tsx (the shipped
        # PopupHost/PopupCatcher the five popups render through), and 114 once
        # preferences-notifier-theme (AD-11/AD-12/AD-13) added the three pure
        # ports (platform/preferences, platform/notifier, platform/theme) and
        # their three bar adapters (lib/preferences, lib/notifier, lib/theme).
        # 116 once migrate-widgets-to-shapes (AD-8/AD-9) added kit/layout.ts (the
        # pure layout vocabulary + chain), bar/layout.default.ts (the repo-default
        # provider) and bar/registry.ts (entry id -> shape spec), and retired
        # bar/widgets/network.tsx in favour of the descriptor (-1, +3).
        # 118 once extract-platform-in-place (AD-17/AD-20) consolidated the ports,
        # the shared adapters and the event client into the ags-platform package:
        # the package identity + entry point (+2) and the 13 relocated sources
        # re-homed under platform/{ports,adapters} (+13), against the 13 sources
        # they replace (-13).
        assert len(files) == 118, (
            f"expected exactly 118 skeleton files (hyprland.lua + gloview.lua + "
            f"8 hypr modules/hyprpaper.conf/ags app.tsx+style.css+overlays.ts+"
            f"7 lib (incl. wifi-signal/network-icon)+6 kit "
            f"(icon/overlay/widget + surface/popup-host + layout)+"
            f"1 domain (network read-model)+"
            f"Bar.tsx+layout.default.ts+registry.ts+11 "
            f"bar widgets (incl. audio) + the settings panel (SettingsPanel/state/"
            f"primitives/bluetooth-agent + 5 controls + 3 views) + the 3 relocated "
            f"D-Bus services + speedtest service + the MPRIS core file "
            f"+ the power-options service (moved out of the battery bar widget) "
            f"+ 15 shared components "
            f"(3 primitives (incl. WifiSwitch) + 3 wifi + 1 bluetooth + 2 sliders "
            f"+ the battery panel's 5 modules: presentation (pure decisions), state "
            f"(popup visibility/anchor), battery-icon (state key), BatteryPopup (the "
            f"two windows) and BatteryContent (the body)) "
    f"+ the audio surface "
            f"(ui-state + AudioPopup + the hexagonal boundary wired in by "
            f"redesign-ags-audio-panel and extended by finish-audio-bar-migration: "
            f"composition, the domain model, ports, actions, the session runtime, "
            f"three PipeWire adapter modules, the MPRIS adapter, the view model, "
            f"presentation/levels, presentation/bar-indicators and audio-panel.css, "
            f"plus the ags types.d.ts ambient declarations) "
            f"+ ags wifi-speedtest.json + rofi launcher config.rasi); found {len(files)}"
        )
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "dotfiles/config/ags/app.tsx",
            "dotfiles/config/ags/audio/AudioPopup.tsx",
            "dotfiles/config/ags/audio/adapters/mpris/mpris-adapter.ts",
            "dotfiles/config/ags/audio/adapters/pipewire/pipewire-commands.ts",
            "dotfiles/config/ags/audio/adapters/pipewire/pipewire-observation.ts",
            "dotfiles/config/ags/audio/adapters/pipewire/project-pipewire-session.ts",
            "dotfiles/config/ags/audio/application/audio-actions.ts",
            "dotfiles/config/ags/audio/application/ports.ts",
            "dotfiles/config/ags/audio/application/runtime/audio-session-runtime.ts",
            "dotfiles/config/ags/audio/audio-panel.css",
            "dotfiles/config/ags/audio/composition.ts",
            "dotfiles/config/ags/audio/domain/audio-model.ts",
            "dotfiles/config/ags/audio/presentation/audio-panel-view-model.ts",
            "dotfiles/config/ags/audio/presentation/bar-indicators.ts",
            "dotfiles/config/ags/audio/presentation/levels.ts",
            "dotfiles/config/ags/audio/ui-state.ts",
            "dotfiles/config/ags/bar/Bar.tsx",
            "dotfiles/config/ags/bar/layout.default.ts",
            "dotfiles/config/ags/bar/registry.ts",
            "dotfiles/config/ags/bar/widgets/audio.tsx",
            "dotfiles/config/ags/bar/widgets/battery.tsx",
            "dotfiles/config/ags/bar/widgets/bluetooth.tsx",
            "dotfiles/config/ags/bar/widgets/btop.tsx",
            "dotfiles/config/ags/bar/widgets/clock.tsx",
            "dotfiles/config/ags/bar/widgets/network-descriptor.tsx",
            "dotfiles/config/ags/bar/widgets/power-menu.tsx",
            "dotfiles/config/ags/bar/widgets/recording.tsx",
            "dotfiles/config/ags/bar/widgets/settings.tsx",
            "dotfiles/config/ags/bar/widgets/thunderbird.tsx",
            "dotfiles/config/ags/bar/widgets/tray.tsx",
            "dotfiles/config/ags/bar/widgets/workspaces.tsx",
            "dotfiles/config/ags/components/battery/BatteryContent.tsx",
            "dotfiles/config/ags/components/battery/BatteryPopup.tsx",
            "dotfiles/config/ags/components/battery/battery-icon.ts",
            "dotfiles/config/ags/components/battery/presentation.ts",
            "dotfiles/config/ags/components/battery/state.ts",
            "dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx",
            "dotfiles/config/ags/components/bluetooth/BluetoothPopup.tsx",
            "dotfiles/config/ags/components/bluetooth/state.ts",
            "dotfiles/config/ags/components/primitives/IconToggle.tsx",
            "dotfiles/config/ags/components/primitives/LevelSlider.tsx",
            "dotfiles/config/ags/components/primitives/WifiSwitch.tsx",
            "dotfiles/config/ags/components/sliders/BrightnessSlider.tsx",
            "dotfiles/config/ags/components/sliders/VolumeSlider.tsx",
            "dotfiles/config/ags/components/wifi/WifiContent.tsx",
            "dotfiles/config/ags/components/wifi/WifiPopup.tsx",
            "dotfiles/config/ags/components/wifi/state.ts",
            "dotfiles/config/ags/domains/audio/astal.ts",
            "dotfiles/config/ags/domains/audio/read-model.ts",
            "dotfiles/config/ags/domains/battery/astal.ts",
            "dotfiles/config/ags/domains/battery/read-model.ts",
            "dotfiles/config/ags/domains/bluetooth/astal.ts",
            "dotfiles/config/ags/domains/bluetooth/read-model.ts",
            "dotfiles/config/ags/domains/network/astal.ts",
            "dotfiles/config/ags/domains/network/read-model.ts",
            "dotfiles/config/ags/kit/layout.ts",
            "dotfiles/config/ags/kit/overlay.ts",
            "dotfiles/config/ags/kit/popup-host.tsx",
            "dotfiles/config/ags/kit/shapes.ts",
            "dotfiles/config/ags/kit/surface.ts",
            "dotfiles/config/ags/kit/widget.tsx",
            "dotfiles/config/ags/lib/bar-backdrop.ts",
            "dotfiles/config/ags/lib/network-icon.ts",
            "dotfiles/config/ags/lib/status-notifier.ts",
            "dotfiles/config/ags/lib/wifi-signal.ts",
            "dotfiles/config/ags/overlays.ts",
            "dotfiles/config/ags/platform/adapters/astal.ts",
            "dotfiles/config/ags/platform/adapters/event-bus.ts",
            "dotfiles/config/ags/platform/adapters/icon-registry.ts",
            "dotfiles/config/ags/platform/adapters/icon.ts",
            "dotfiles/config/ags/platform/adapters/notifier.ts",
            "dotfiles/config/ags/platform/adapters/preferences.ts",
            "dotfiles/config/ags/platform/adapters/theme.ts",
            "dotfiles/config/ags/platform/index.ts",
            "dotfiles/config/ags/platform/package.json",
            "dotfiles/config/ags/platform/ports/event-client.ts",
            "dotfiles/config/ags/platform/ports/icon-source.ts",
            "dotfiles/config/ags/platform/ports/notifier.ts",
            "dotfiles/config/ags/platform/ports/preferences.ts",
            "dotfiles/config/ags/platform/ports/reactive.ts",
            "dotfiles/config/ags/platform/ports/theme.ts",
            "dotfiles/config/ags/services/bluetooth-service.ts",
            "dotfiles/config/ags/services/mpris-core.ts",
            "dotfiles/config/ags/services/nm-client.ts",
            "dotfiles/config/ags/services/power-service.ts",
            "dotfiles/config/ags/services/speedtest-service.ts",
            "dotfiles/config/ags/services/wifi-service.ts",
            "dotfiles/config/ags/settings-panel/SettingsPanel.tsx",
            "dotfiles/config/ags/settings-panel/bluetooth-agent.ts",
            "dotfiles/config/ags/settings-panel/controls/bluetooth.tsx",
            "dotfiles/config/ags/settings-panel/controls/brightness.tsx",
            "dotfiles/config/ags/settings-panel/controls/hyprmod.tsx",
            "dotfiles/config/ags/settings-panel/controls/volume.tsx",
            "dotfiles/config/ags/settings-panel/controls/wifi.tsx",
            "dotfiles/config/ags/settings-panel/primitives.tsx",
            "dotfiles/config/ags/settings-panel/state.ts",
            "dotfiles/config/ags/settings-panel/views/BluetoothView.tsx",
            "dotfiles/config/ags/settings-panel/views/MainView.tsx",
            "dotfiles/config/ags/settings-panel/views/SubviewHeader.tsx",
            "dotfiles/config/ags/settings-panel/views/WifiView.tsx",
            "dotfiles/config/ags/style.css",
            "dotfiles/config/ags/types.d.ts",
            "dotfiles/config/ags/wifi-speedtest.json",
            "dotfiles/config/hypr/animations.lua",
            "dotfiles/config/hypr/autostart.lua",
            "dotfiles/config/hypr/colors.lua",
            "dotfiles/config/hypr/cursor.lua",
            "dotfiles/config/hypr/decoration.lua",
            "dotfiles/config/hypr/env-variables.lua",
            "dotfiles/config/hypr/general.lua",
            "dotfiles/config/hypr/gloview.lua",
            "dotfiles/config/hypr/hyprland.lua",
            "dotfiles/config/hypr/input.lua",
            "dotfiles/config/hypr/keybindings.lua",
            "dotfiles/config/hypr/monitors.lua",
            "dotfiles/config/hypr/window-rules.lua",
            "dotfiles/config/hyprpaper/hyprpaper.conf",
            "dotfiles/config/rofi/launcher/config.rasi",
        ]
        assert sources == expected, f"skeleton file sources must be exactly {expected}"
        for file_ in files:
            assert str(file_["source"]).startswith("dotfiles/config/"), (
                "skeleton file source must live under dotfiles/config/"
            )
            assert str(file_["dest"]).startswith("{{ compositor_configs_spine_config_dir }}/"), (
                "skeleton file dest must derive from compositor_configs_spine_config_dir"
            )

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


class TestCompositorConfigsVars:
    _REQUIRED_KEYS = {
        "compositor_configs_repo_root",
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
        data = _vars()
        assert str(data["compositor_configs_repo_root"]) == "{{ playbook_dir }}/../../../.."

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
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()
            # ansible's copy module does not create the bin dest parent.
            (home / ".local" / "bin").mkdir(parents=True)
            # Assets-role outputs this role consumes (inputs, not generated):
            # the icon manifest source for icons.json generation.
            icon_mappings = install / "icon-mappings"
            icon_mappings.mkdir(parents=True)
            (icon_mappings / "icons.yaml").write_text("test-group: {}\n")

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
                install / "config" / "ags" / "app.tsx",
                install / "config" / "ags" / "style.css",
                install / "config" / "ags" / "icons.json",
                install / "config" / "ags" / "platform" / "package.json",
                install / "config" / "ags" / "platform" / "index.ts",
                install / "config" / "ags" / "platform" / "ports" / "event-client.ts",
                install / "config" / "ags" / "platform" / "adapters" / "event-bus.ts",
                install / "config" / "ags" / "platform" / "adapters" / "icon-registry.ts",
                install / "config" / "ags" / "bar" / "Bar.tsx",
                install / "config" / "ags" / "bar" / "layout.default.ts",
                install / "config" / "ags" / "bar" / "registry.ts",
                install / "config" / "ags" / "bar" / "widgets" / "workspaces.tsx",
                install / "config" / "ags" / "bar" / "widgets" / "clock.tsx",
                install / "config" / "ags" / "bar" / "widgets" / "battery.tsx",
                install / "config" / "ags" / "bar" / "widgets" / "power-menu.tsx",
                install / "config" / "ags" / "bar" / "widgets" / "settings.tsx",
                install / "config" / "ags" / "settings-panel" / "state.ts",
                install / "config" / "ags" / "settings-panel" / "primitives.tsx",
                install / "config" / "ags" / "settings-panel" / "SettingsPanel.tsx",
                install / "config" / "ags" / "settings-panel" / "bluetooth-agent.ts",
                install / "config" / "ags" / "settings-panel" / "controls" / "wifi.tsx",
                install / "config" / "ags" / "settings-panel" / "controls" / "bluetooth.tsx",
                install / "config" / "ags" / "settings-panel" / "controls" / "brightness.tsx",
                install / "config" / "ags" / "settings-panel" / "controls" / "volume.tsx",
                install / "config" / "ags" / "settings-panel" / "controls" / "hyprmod.tsx",
                install / "config" / "ags" / "settings-panel" / "views" / "MainView.tsx",
                install / "config" / "ags" / "settings-panel" / "views" / "WifiView.tsx",
                install / "config" / "ags" / "settings-panel" / "views" / "BluetoothView.tsx",
                install / "config" / "ags" / "services" / "nm-client.ts",
                install / "config" / "ags" / "services" / "wifi-service.ts",
                install / "config" / "ags" / "services" / "bluetooth-service.ts",
                install / "config" / "ags" / "components" / "primitives" / "IconToggle.tsx",
                install / "config" / "ags" / "components" / "primitives" / "LevelSlider.tsx",
                install / "config" / "ags" / "components" / "wifi" / "state.ts",
                install / "config" / "ags" / "components" / "wifi" / "WifiContent.tsx",
                install / "config" / "ags" / "components" / "wifi" / "WifiPopup.tsx",
                install / "config" / "ags" / "components" / "bluetooth" / "BluetoothContent.tsx",
                install / "config" / "ags" / "components" / "sliders" / "VolumeSlider.tsx",
                install / "config" / "ags" / "components" / "sliders" / "BrightnessSlider.tsx",
                install / "config" / "ags" / "bar" / "widgets" / "audio.tsx",
                install / "config" / "ags" / "audio" / "ui-state.ts",
                install / "config" / "ags" / "audio" / "presentation" / "levels.ts",
                install / "config" / "ags" / "audio" / "presentation" / "bar-indicators.ts",
                install / "config" / "ags" / "audio" / "AudioPopup.tsx",
                # Battery panel (add-battery-status-panel): all five modules plus
                # the power-options service the bar widget used to build at its
                # own module scope. Placement is per-file, so an unregistered
                # one deploys nothing and the panel imports a missing module.
                install / "config" / "ags" / "components" / "battery" / "presentation.ts",
                install / "config" / "ags" / "components" / "battery" / "state.ts",
                install / "config" / "ags" / "components" / "battery" / "battery-icon.ts",
                install / "config" / "ags" / "components" / "battery" / "BatteryPopup.tsx",
                install / "config" / "ags" / "components" / "battery" / "BatteryContent.tsx",
                install / "config" / "ags" / "services" / "power-service.ts",
                # fix-deploy-bar-new-files: the reachable sources the platform
                # work added but the manifest missed. Placement is per-file, so
                # these assert the registration actually copies each one.
                install / "config" / "ags" / "platform" / "ports" / "icon-source.ts",
                install / "config" / "ags" / "platform" / "ports" / "reactive.ts",
                install / "config" / "ags" / "platform" / "adapters" / "astal.ts",
                install / "config" / "ags" / "kit" / "shapes.ts",
                install / "config" / "ags" / "kit" / "layout.ts",
                install / "config" / "ags" / "domains" / "network" / "astal.ts",
                install / "config" / "ags" / "domains" / "battery" / "read-model.ts",
                install / "config" / "ags" / "domains" / "battery" / "astal.ts",
                install / "config" / "ags" / "domains" / "bluetooth" / "read-model.ts",
                install / "config" / "ags" / "domains" / "bluetooth" / "astal.ts",
                install / "config" / "ags" / "domains" / "audio" / "read-model.ts",
                install / "config" / "ags" / "domains" / "audio" / "astal.ts",
                install / "config" / "ags" / "bar" / "widgets" / "bluetooth.tsx",
                install / "config" / "ags" / "components" / "bluetooth" / "BluetoothPopup.tsx",
                install / "config" / "ags" / "components" / "bluetooth" / "state.ts",
                install / "config" / "ags" / "settings-panel" / "views" / "SubviewHeader.tsx",
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
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            state = Path(tmp) / "state"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()
            # ansible's copy module does not create the bin dest parent.
            (home / ".local" / "bin").mkdir(parents=True)
            # Assets-role outputs this role consumes (inputs, not generated).
            icon_mappings = install / "icon-mappings"
            icon_mappings.mkdir(parents=True)
            (icon_mappings / "icons.yaml").write_text("test-group: {}\n")

            current = state / "dotfiles" / "current"
            current.mkdir(parents=True)
            (current / "colors.gtk.css").write_text("@define-color color_00 #111111;\n")
            ags_colors = install / "config" / "ags" / "colors.css"
            ags_colors.parent.mkdir(parents=True)
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
    """The deploy-coverage gate (scripts/deploy-coverage.py) is the guard that
    turns "reachable from app.tsx but not deployed" into a failed run.

    The structural test above pins the manifest's CONTENTS; this gate derives
    the REQUIREMENT from the source tree, so a new relative import cannot be
    added without its per-file deploy entry. The positive case runs on the real
    tree. The negative case removes one entry and proves the gate bites
    (hermetic: a temp root whose ags tree is symlinked and whose manifest is a
    modified copy — the ags sources are read-only input to the gate).
    """

    _SCRIPT = _ANSIBLE_DIR.parents[2] / "scripts" / "deploy-coverage.py"
    _VARS = "src/provisioning/ansible/roles/compositor_configs/vars/main.yml"
    _AGS = "dotfiles/config/ags"

    def _run(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self._SCRIPT), "--root", str(root)],
            capture_output=True,
            text=True,
        )

    def test_gate_passes_on_the_real_tree(self) -> None:
        repo_root = _ANSIBLE_DIR.parents[2]
        result = self._run(repo_root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PASS" in result.stdout

    def test_gate_fails_when_a_reachable_module_is_removed(self) -> None:
        repo_root = _ANSIBLE_DIR.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dotfiles" / "config").mkdir(parents=True)
            (root / "dotfiles" / "config" / "ags").symlink_to(
                repo_root / self._AGS, target_is_directory=True
            )
            vars_src = (repo_root / self._VARS).read_text()
            removed_line = next(
                line
                for line in vars_src.splitlines()
                if "name: ags-platform-port-icon-source" in line
            )
            vars_dst = root / self._VARS
            vars_dst.parent.mkdir(parents=True)
            vars_dst.write_text(vars_src.replace(removed_line + "\n", "", 1))

            result = self._run(root)
            assert result.returncode != 0, (
                "the gate must FAIL when a reachable module is not deployed; "
                f"recap:\n{result.stdout}"
            )
            assert "platform/ports/icon-source.ts" in result.stdout, (
                "the failure must name the undeployed reachable module; recap:\n"
                + result.stdout
            )
