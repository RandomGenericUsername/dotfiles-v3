"""Structural tests for the gui_tools role (extract-capture-gui-tool).

Mirrors test_compositor_configs_role.py, trimmed to the instance/launch
plumbing that remains: every GUI app now deploys WHOLE from the `ags-apps`
unit (slices 3-8), so the role carries NO per-file app manifests and the old
in-repo `src/gui-tools/` source root is retired.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "gui_tools"
# _ANSIBLE_DIR is <repo>/src/provisioning/ansible → repo root is 3 up.
_REPO_ROOT = _ANSIBLE_DIR.parent.parent.parent


def _assets_configs_file(relative: str) -> Path | None:
    """Resolve a file inside the pinned assets `configs/` class (S2).

    The hypr skeletons moved to the pinned corpus, so a cross-check that reads
    them can only run where that checkout exists. Resolution mirrors
    `_authored_icons_yaml` in the compositor suite: explicit
    ``DOTFILES_ASSETS_CONFIGS_DIR``, else the provisioned spine's pinned
    checkout. ``None`` means "not provided" — the caller skips loudly rather
    than pinning a copy of the bytes here.
    """
    explicit = os.environ.get("DOTFILES_ASSETS_CONFIGS_DIR")
    candidates: list[Path] = [Path(explicit).expanduser()] if explicit else []
    manifest = yaml.safe_load(
        (_REPO_ROOT / "dotfiles" / "provisioning" / "assets.yaml").read_text()
    )
    tag = str(manifest["assets"]["tag"])
    spine = os.environ.get("DOTFILES_INSTALL_SPINE")
    if spine:
        candidates.append(Path(spine).expanduser() / "assets" / tag / "configs")
    else:
        xdg_data = Path(
            os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
        )
        candidates.append(xdg_data / "dotfiles" / "assets" / tag / "configs")
    return next((base / relative for base in candidates if (base / relative).is_file()), None)


def _tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLES_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return [dict(task) for task in data]


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return dict(data)


def _module(task: dict[str, object]) -> dict[str, Any]:
    for key, value in task.items():
        if key == "name":
            continue
        if isinstance(value, dict):
            return dict(value)
    raise AssertionError(f"task has no module args: {task!r}")


class TestGuiToolsTasks:
    def test_seam_assert_is_first_task(self) -> None:
        """Fail-loud install_dir seam assert (mirror of the sibling roles)."""
        first = _tasks()[0]
        module = _module(first)
        assert "install_dir" in str(module.get("that", ""))

    def test_app_dirs_ensured_via_file_directory(self) -> None:
        """Direct-run self-containment: `file` `state: directory` re-ensures
        gui_tools_config_dirs (copy does NOT create dest parents)."""
        dir_tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.file"}
            and "gui_tools_config_dirs" in str(task.get("loop", ""))
        ]
        assert dir_tasks, "no app-dir ensure task found"
        for task in dir_tasks:
            assert _module(task)["state"] == "directory"

    def test_no_wallpaper_selector_placement_task_remains(self) -> None:
        """Slice 6: the wallpaper selector's per-file placement is RETIRED. The
        selector deploys WHOLE via the ags_apps live-wallpaper-selector link, so no
        task may loop the retired gui_tools_wallpaper_selector_app_files manifest —
        a stale one would template INTO the unit tree through the link and diverge
        the live selector from the pinned tag."""
        for task in _tasks():
            loop = str(task.get("loop", ""))
            assert "gui_tools_wallpaper_selector_app_files" not in loop, (
                f"task {task.get('name')!r} still loops the retired "
                "gui_tools_wallpaper_selector_app_files manifest"
            )

    def test_no_legacy_capture_removal_or_placement_tasks_remain(self) -> None:
        """Slice 5: the capture-tool GUI's per-file placement AND its legacy
        in-bar `ags/capture` subtree removal are BOTH retired. The GUI deploys
        WHOLE via the ags_apps live-capture link, and the legacy path now resolves
        THROUGH the live-bar symlink into the unit tree — an `absent` there would
        mutate the unit, not a bridge. No task may loop a capture manifest or
        target `ags/capture`."""
        for task in _tasks():
            loop = str(task.get("loop", ""))
            assert "gui_tools_app_files" not in loop, (
                f"task {task.get('name')!r} still loops the retired "
                "gui_tools_app_files capture manifest"
            )
            assert "gui_tools_capture_obsolete" not in loop, (
                f"task {task.get('name')!r} still loops the retired "
                "gui_tools_capture_obsolete list"
            )
            assert "/ags/capture" not in str(_module(task).get("path", "")), (
                f"task {task.get('name')!r} still targets the legacy ags/capture "
                "subtree — through the live-bar symlink that is the unit tree"
            )

    def test_state_dirs_ensured_via_file_directory(self) -> None:
        """Runtime state dirs (e.g. the AGS log dir) are ensured by the role —
        directory setup is provisioning's responsibility, never the login
        launcher's."""
        tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.file"}
            and "gui_tools_state_dirs" in str(task.get("loop", ""))
        ]
        assert tasks, "no state-dir ensure task found"
        for task in tasks:
            assert _module(task).get("state") == "directory"

    def test_no_become_anywhere(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere."""
        for task in _tasks():
            assert "become" not in task and "become_user" not in task, (
                f"task must not use become: {task.get('name')}"
            )

    def _always_on_restart_task(self) -> dict[str, object]:
        matches = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.shell"}
            and "gui_tools_ags_always_on_instances" in str(task.get("loop", ""))
        ]
        assert len(matches) == 1, (
            f"expected exactly one always-on start-if-down task; found {len(matches)}"
        )
        return matches[0]

    def test_quit_loop_iterates_instance_names(self) -> None:
        """The quit loop now iterates mappings, so it must address `item.name`
        (not the mapping itself)."""
        matches = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.command"}
            and "gui_tools_ags_instances" in str(task.get("loop", ""))
        ]
        assert len(matches) == 1, f"expected exactly one quit loop; found {len(matches)}"
        cmd = str(_module(matches[0]).get("cmd", ""))
        assert "ags quit -i {{ item.name }}" in cmd, (
            f"quit loop must run `ags quit -i item.name`; got {cmd}"
        )

    def test_always_on_instances_are_restarted_start_if_down(self) -> None:
        """The always-on instances (bar + notification overlay) are brought back
        up on the spot after the quit loop — a provision run must never leave
        the session without its status bar or its only notification daemon. The
        guard mirrors the cli_tools launchers: skip when already on the bus
        (`ags list | grep -qx`), so re-running is a no-op."""
        task = self._always_on_restart_task()
        text = str(_module(task).get("cmd", ""))
        assert "ags list" in text and "grep -qx" in text, (
            "the restart must use the launcher start-if-down guard "
            "(ags list | grep -qx <name>) so an already-running instance is a no-op"
        )
        assert "setsid" in text, (
            "the restart must fully detach (setsid + redirected stdio) so the "
            "process survives the playbook exiting"
        )
        assert ">/dev/null 2>&1 </dev/null &" in text, (
            "the detached launch must redirect stdio and background"
        )

    def test_always_on_restart_is_check_gated_and_non_fatal(self) -> None:
        """Starting a process is a state mutation: --check must not do it. The
        task is `failed_when: false` (a machine without a live AGS session must
        not break provisioning) and `changed_when: false` (start-if-down is
        idempotent by design) — the verify gate is what makes failure loud."""
        task = self._always_on_restart_task()
        assert task.get("when") == "not ansible_check_mode", (
            "the restart must be gated when: not ansible_check_mode"
        )
        assert task.get("failed_when") is False
        assert task.get("changed_when") is False


class TestGuiToolsVars:
    _REQUIRED_KEYS = {
        "gui_tools_repo_root",
        "gui_tools_xdg_state_home",
        "gui_tools_state_dirs",
        "gui_tools_spine_config_dir",
        "gui_tools_config_dirs",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_capture_tool_is_retired_as_a_gui_tools_app(self) -> None:
        """ags-apps-bar-first slice 5: the capture-tool AGS GUI moved into the
        ags-apps unit and deploys WHOLE via the ags_apps role's live-capture link
        (<install>/config/ags-capture -> <unit>/capture-tool). gui_tools must
        carry NO per-file capture manifest, NO ags-capture spine dir, and NO
        placement/cleanup task — a stale entry would template INTO the unit tree
        through the live-capture link and diverge the live GUI from the pinned
        tag. The in-repo app tree is gone entirely (v0.4.0 moved the Python
        backend into the same unit)."""
        data = _vars()
        assert "gui_tools_app_files" not in data, (
            "gui_tools_app_files must be retired — the GUI deploys WHOLE via the "
            "ags_apps live-capture link"
        )
        assert "gui_tools_capture_obsolete" not in data, (
            "gui_tools_capture_obsolete must be retired — placement is per-file "
            "only for the remaining apps, and the capture GUI is not one"
        )
        # No app-file list may still target the retired ags-capture/ spine.
        for key, value in data.items():
            if key.endswith("_app_files") and isinstance(value, list):
                for entry in value:
                    dest = str(entry.get("dest", ""))
                    assert "/ags-capture/" not in dest, (
                        f"{key} still deploys into the retired ags-capture/ "
                        f"spine: {dest}"
                    )
        assert not any(
            "ags-capture" in str(d) for d in data["gui_tools_config_dirs"]
        ), "the retired ags-capture/ spine dir must not be ensured as a dir"
        assert not any(
            "capture" in str(t.get("loop", "")) for t in _tasks()
        ), "no gui_tools task may loop a capture manifest"
        # The whole app is gone from this repo (ags-apps v0.4.0): the GUI and the
        # Python backend both ship in the unit, and the ags_apps role links the
        # backend into the user bin dir.
        assert not (_REPO_ROOT / "src" / "gui-tools" / "capture-tool").exists(), (
            "the in-repo capture-tool tree (GUI + Python backend) must be "
            "deleted — it all lives in the ags-apps unit now"
        )

    def test_capture_ags_instance_still_launches_from_the_symlink(self) -> None:
        """The GUI still launches: the on-demand `capture` AGS instance entry
        stays in gui_tools_ags_instances, so the provisioned `capture-ui` launcher
        and autostart.lua start it from ~/.config/ags-capture (the config-links
        symlink to the live-capture link), never the unit path."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "capture" in instances, (
            f"the capture AGS instance must stay in gui_tools_ags_instances; "
            f"got {instances}"
        )

    def test_icme_is_retired_as_a_gui_tools_app(self) -> None:
        """ags-apps-bar-first slice 7: the icon color mapping editor moved into
        the ags-apps unit and deploys WHOLE via the ags_apps role's live-icme
        link (<install>/config/ags-icme -> <unit>/icme). gui_tools must carry NO
        per-file icme manifest, NO ags-icme spine dir, and NO placement task — a
        stale entry would template INTO the unit tree through the live-icme link
        and diverge the live editor from the pinned tag. The in-repo source is
        gone (it lives in ags-apps now); like the selector, icme is a WHOLE
        package, so nothing stays in-repo."""
        data = _vars()
        assert "gui_tools_icme_app_files" not in data, (
            "gui_tools_icme_app_files must be retired — the editor deploys WHOLE "
            "via the ags_apps live-icme link"
        )
        # No app-file list may still target the retired ags-icme/ spine.
        for key, value in data.items():
            if key.endswith("_app_files") and isinstance(value, list):
                for entry in value:
                    dest = str(entry.get("dest", ""))
                    assert "/ags-icme/" not in dest, (
                        f"{key} still deploys into the retired ags-icme/ "
                        f"spine: {dest}"
                    )
        assert not any(
            "ags-icme" in str(d) for d in data["gui_tools_config_dirs"]
        ), "the retired ags-icme/ spine dir must not be ensured as a dir"
        assert not any(
            "icme" in str(t.get("loop", "")) for t in _tasks()
        ), "no gui_tools task may loop an icme manifest"
        assert not (
            _REPO_ROOT / "src" / "gui-tools" / "icon-color-mapping-editor"
        ).exists(), (
            "the in-repo icme source must be deleted (it lives in the ags-apps "
            "unit now)"
        )

    def test_icme_ags_instance_still_launches_from_the_symlink(self) -> None:
        """The editor still launches: the on-demand
        `icon-color-mapping-editor` AGS instance entry stays in
        gui_tools_ags_instances, so the provisioned launcher starts it from
        ~/.config/ags-icme (the config-links symlink to the live-icme link),
        never the unit path."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "icon-color-mapping-editor" in instances, (
            "the icme AGS instance must stay in gui_tools_ags_instances; "
            f"got {instances}"
        )

    def test_hypr_pano_is_retired_as_a_gui_tools_app(self) -> None:
        """ags-apps-bar-first slice 3: the clipboard overlay moved into the
        ags-apps unit and deploys WHOLE via the ags_apps role's live-pano link
        (<install>/config/ags-hypr-pano -> <unit>/hypr-pano). gui_tools must
        carry NO per-file hypr-pano manifest, NO ags-hypr-pano spine dir, and
        NO placement task — a stale entry would template INTO the unit tree
        through the live-pano link and diverge the live app from the pinned
        tag. The in-repo source is gone (it lives in ags-apps now)."""
        data = _vars()
        assert "gui_tools_hypr_pano_app_files" not in data, (
            "gui_tools_hypr_pano_app_files must be retired — the overlay "
            "deploys WHOLE via the ags_apps live-pano link"
        )
        # No app-file list may still target the retired ags-hypr-pano/ spine.
        for key, value in data.items():
            if key.endswith("_app_files") and isinstance(value, list):
                for entry in value:
                    dest = str(entry.get("dest", ""))
                    assert "/ags-hypr-pano/" not in dest, (
                        f"{key} still deploys into the retired ags-hypr-pano/ "
                        f"spine: {dest}"
                    )
        assert not any(
            "ags-hypr-pano" in str(d) for d in data["gui_tools_config_dirs"]
        ), "the retired ags-hypr-pano/ spine dir must not be ensured as a dir"
        assert not any(
            "hypr_pano" in str(t.get("loop", "")) for t in _tasks()
        ), "no gui_tools task may loop a hypr-pano manifest"
        assert not (_REPO_ROOT / "src" / "gui-tools" / "hypr-pano").exists(), (
            "the in-repo hypr-pano source must be deleted (it lives in the "
            "ags-apps unit now)"
        )

    def test_hypr_pano_ags_instance_still_launches_from_the_symlink(self) -> None:
        """The app still launches: the AGS instance entry stays, so the quit
        loop restarts it after placement. It runs from ~/.config/ags-hypr-pano
        (the config-links symlink to the live-pano link), never the unit path."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "hypr-pano" in instances, (
            f"the hypr-pano AGS instance must stay in gui_tools_ags_instances; "
            f"got {instances}"
        )

    def test_wallpaper_selector_is_retired_as_a_gui_tools_app(self) -> None:
        """ags-apps-bar-first slice 6: the wallpaper selector moved into the
        ags-apps unit and deploys WHOLE via the ags_apps role's
        live-wallpaper-selector link (<install>/config/ags-wallpaper-selector ->
        <unit>/wallpaper-selector). gui_tools must carry NO per-file selector
        manifest, NO ags-wallpaper-selector spine dir, and NO placement task — a
        stale entry would template INTO the unit tree through the
        live-wallpaper-selector link and diverge the live selector from the pinned
        tag. The in-repo source is gone (it lives in ags-apps now); unlike
        capture-tool the selector is a WHOLE package, so nothing stays in-repo."""
        data = _vars()
        assert "gui_tools_wallpaper_selector_app_files" not in data, (
            "gui_tools_wallpaper_selector_app_files must be retired — the selector "
            "deploys WHOLE via the ags_apps live-wallpaper-selector link"
        )
        # No app-file list may still target the retired ags-wallpaper-selector/
        # spine.
        for key, value in data.items():
            if key.endswith("_app_files") and isinstance(value, list):
                for entry in value:
                    dest = str(entry.get("dest", ""))
                    assert "/ags-wallpaper-selector/" not in dest, (
                        f"{key} still deploys into the retired "
                        f"ags-wallpaper-selector/ spine: {dest}"
                    )
        assert not any(
            "ags-wallpaper-selector" in str(d) for d in data["gui_tools_config_dirs"]
        ), "the retired ags-wallpaper-selector/ spine dir must not be ensured as a dir"
        assert not any(
            "wallpaper_selector" in str(t.get("loop", "")) for t in _tasks()
        ), "no gui_tools task may loop a wallpaper-selector manifest"
        assert not (_REPO_ROOT / "src" / "gui-tools" / "wallpaper-selector").exists(), (
            "the in-repo wallpaper-selector source must be deleted (it lives in "
            "the ags-apps unit now)"
        )

    def test_ags_instances_include_wallpaper_selector(self) -> None:
        """The selector instance must be quit after placement (bundles TS at
        startup and holds it in memory — same lifecycle as the siblings). The
        entry STAYS: the provisioned `wallpaper-selector-ui` launcher and
        autostart.lua start the selector from ~/.config/ags-wallpaper-selector
        (the config-links symlink to the live-wallpaper-selector link), never the
        unit path."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "wallpaper-selector" in instances, (
            f"gui_tools_ags_instances must include wallpaper-selector; got {instances}"
        )

    def test_notifications_is_retired_as_a_gui_tools_app(self) -> None:
        """ags-apps-bar-first slice 4: the notification daemon moved into the
        ags-apps unit and deploys WHOLE via the ags_apps role's
        live-notifications link (<install>/config/ags-notifications ->
        <unit>/notifications). gui_tools must carry NO per-file notifications
        manifest, NO ags-notifications spine dir, and NO placement task — a stale
        entry would template INTO the unit tree through the live-notifications
        link and diverge the live daemon from the pinned tag. The in-repo source
        is gone (it lives in ags-apps now)."""
        data = _vars()
        assert "gui_tools_notifications_app_files" not in data, (
            "gui_tools_notifications_app_files must be retired — the daemon "
            "deploys WHOLE via the ags_apps live-notifications link"
        )
        # No app-file list may still target the retired ags-notifications/ spine.
        for key, value in data.items():
            if key.endswith("_app_files") and isinstance(value, list):
                for entry in value:
                    dest = str(entry.get("dest", ""))
                    assert "/ags-notifications/" not in dest, (
                        f"{key} still deploys into the retired ags-notifications/ "
                        f"spine: {dest}"
                    )
        assert not any(
            "ags-notifications" in str(d) for d in data["gui_tools_config_dirs"]
        ), "the retired ags-notifications/ spine dir must not be ensured as a dir"
        assert not any(
            "notifications_app_files" in str(t.get("loop", "")) for t in _tasks()
        ), "no gui_tools task may loop a notifications manifest"
        assert not (_REPO_ROOT / "src" / "gui-tools" / "notifications").exists(), (
            "the in-repo notifications source must be deleted (it lives in the "
            "ags-apps unit now)"
        )

    def test_notifications_ags_instance_still_launches_from_the_symlink(self) -> None:
        """The daemon still launches: the AGS instance entry STAYS (it is the
        mechanism that starts it and restarts it after the quit loop). It runs
        from ~/.config/ags-notifications (the config-links symlink to the
        live-notifications link), never the unit path."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "notifications" in instances, (
            f"the notifications AGS instance must stay in gui_tools_ags_instances; "
            f"got {instances}"
        )

    def test_ags_instances_include_notifications(self) -> None:
        """The notifications instance must be quit after placement (bundles
        TS at startup and holds it in memory — same lifecycle as the
        siblings)."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "notifications" in instances, (
            f"gui_tools_ags_instances must include notifications; got {instances}"
        )

    def test_ags_instances_are_mappings_tagged_always_on(self) -> None:
        """Each instance is a mapping carrying a name and a boolean always_on
        flag (the single source of truth for the lifecycle split)."""
        instances = [dict(i) for i in _vars()["gui_tools_ags_instances"]]
        names = [str(i["name"]) for i in instances]
        assert len(names) == len(set(names)), f"duplicate AGS instance names: {names}"
        for entry in instances:
            assert "name" in entry and str(entry["name"]).strip(), (
                f"every gui_tools_ags_instances entry needs a name: {entry}"
            )
            assert isinstance(entry.get("always_on"), bool), (
                f"every entry needs a boolean always_on flag: {entry}"
            )

    def test_always_on_instances_are_the_bar_and_overlay(self) -> None:
        """The always-on set is exactly the status bar and the notification
        overlay; the four keybind tools are on-demand (quit and left down)."""
        data = _vars()
        always_on = [
            str(i["name"]) for i in data["gui_tools_ags_instances"] if i["always_on"]
        ]
        assert always_on == ["ags", "notifications"], (
            f"the always-on set must be the bar + overlay; got {always_on}"
        )
        on_demand = sorted(
            str(i["name"]) for i in data["gui_tools_ags_instances"] if not i["always_on"]
        )
        assert on_demand == [
            "btop-theme-studio",
            "capture",
            "hypr-pano",
            "icon-color-mapping-editor",
            "wallpaper-selector",
        ], f"the on-demand set drifted: {on_demand}"

    def test_always_on_entries_carry_a_launch_and_on_demand_do_not(self) -> None:
        """Only always-on entries carry the `ags run` command the role re-issues
        when they are down; on-demand entries must not (their keybind launchers
        start them, so provisioning never opens an unrequested window)."""
        for entry in _vars()["gui_tools_ags_instances"]:
            if entry["always_on"]:
                launch = str(entry.get("launch", "")).strip()
                assert launch.startswith("ags run"), (
                    f"always-on {entry['name']!r} needs an `ags run` launch command: {entry}"
                )
            else:
                assert not entry.get("launch"), (
                    f"on-demand {entry['name']!r} must not carry a launch: {entry}"
                )

    def test_always_on_view_is_derived_not_duplicated(self) -> None:
        """gui_tools_ags_always_on_instances must be DERIVED from
        gui_tools_ags_instances (selectattr always_on) — never a second
        hand-maintained list (the single-source-of-truth rule)."""
        value = str(_vars()["gui_tools_ags_always_on_instances"])
        assert "gui_tools_ags_instances" in value and "selectattr('always_on')" in value, (
            f"the always-on view must be derived from the instance list; got {value}"
        )

    def test_notifications_launch_matches_autostart(self) -> None:
        """The overlay's launch command points at the ~/.config symlink
        (config_links) with the same stagger-free log file autostart uses, so a
        provisioning restart is indistinguishable from a login start."""
        data = _vars()
        entry = next(
            i for i in data["gui_tools_ags_instances"] if i["name"] == "notifications"
        )
        launch = str(entry["launch"])
        assert "{{ gui_tools_xdg_config_home }}/ags-notifications" in launch, (
            f"the overlay must launch from the ~/.config symlink; got {launch}"
        )
        assert (
            "--log-file {{ gui_tools_xdg_state_home }}/ags/notifications.log" in launch
        ), f"the overlay must log to the state dir like autostart; got {launch}"


class TestBtopStudioRegistration:
    """btop-theme-studio stays provisioned as its OWN AGS instance,
    launch-on-demand only — never autostarted (capability `btop-theme-studio`,
    tasks 1.1-1.3). Since slice 8 its SOURCES deploy WHOLE from the pinned
    `ags-apps` unit via the ags_apps role's live-btop-studio link; gui_tools only
    keeps the instance lifecycle entry."""

    def test_btop_studio_is_retired_as_a_gui_tools_app(self) -> None:
        """Slice 8: the btop Theme Studio moved into the ags-apps unit and
        deploys WHOLE via the ags_apps role's live-btop-studio link
        (<install>/config/ags-btop-studio -> <unit>/btop-theme-studio). gui_tools
        must carry NO per-file studio manifest, NO ags-btop-studio spine dir, and
        NO placement task — a stale entry would template INTO the unit tree
        through the live-btop-studio link and diverge the live studio from the
        pinned tag. The studio is a WHOLE package: nothing stays in-repo,
        including its live/btop_live.py preview engine."""
        data = _vars()
        assert "gui_tools_btop_studio_app_files" not in data, (
            "gui_tools_btop_studio_app_files must be retired — the studio deploys "
            "WHOLE via the ags_apps live-btop-studio link"
        )
        # No app-file list may still target the retired ags-btop-studio/ spine.
        for key, value in data.items():
            if key.endswith("_app_files") and isinstance(value, list):
                for entry in value:
                    dest = str(entry.get("dest", "")) if isinstance(entry, dict) else ""
                    assert "/ags-btop-studio/" not in dest, (
                        f"{key} still deploys into the retired ags-btop-studio/ "
                        f"spine: {dest}"
                    )
        assert not any(
            "ags-btop-studio" in str(d) for d in data["gui_tools_config_dirs"]
        ), "the retired ags-btop-studio/ spine dir must not be ensured as a dir"
        assert not any(
            "btop_studio" in str(t.get("loop", "")) for t in _tasks()
        ), "no gui_tools task may loop a studio manifest"
        assert not (
            _REPO_ROOT / "src" / "gui-tools" / "btop-theme-studio"
        ).exists(), (
            "the in-repo studio source must be deleted (it lives in the ags-apps "
            "unit now, including its live/ preview engine)"
        )

    def test_btop_studio_ags_instance_still_launches_from_the_symlink(self) -> None:
        """The studio still launches: the on-demand `btop-theme-studio` AGS
        instance entry stays in gui_tools_ags_instances, so the provisioned
        launcher starts it from ~/.config/ags-btop-studio (the config-links
        symlink to the live-btop-studio link), never the unit path."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "btop-theme-studio" in instances, (
            f"gui_tools_ags_instances must include btop-theme-studio; got {instances}"
        )

    def test_btop_studio_is_never_autostarted_and_has_a_keybind(self) -> None:
        """Task 1.3: the studio is launch-on-demand only. It must not appear in
        the login autostart, and it must have a provisioned keybind launcher.
        (The bar's app.tsx no longer exists in-repo — the bar deploys whole as
        the pinned external `ags-apps` unit, and the "not registered in the
        bar" assertion is owned there.)"""
        autostart_path = _assets_configs_file("hypr/autostart.lua")
        keybinds_path = _assets_configs_file("hypr/keybindings.lua")
        if autostart_path is None or keybinds_path is None:
            pytest.skip(
                "the hypr skeletons are in the pinned corpus (S2): set "
                "DOTFILES_ASSETS_CONFIGS_DIR=<v0.3.1 checkout>/configs or "
                "provision the spine, then re-run this cross-check"
            )
        autostart = autostart_path.read_text(encoding="utf-8")
        assert "btop-theme-studio" not in autostart and "ags-btop-studio" not in autostart, (
            "the studio must not be autostarted (launch-on-demand only)"
        )
        keybinds = keybinds_path.read_text(encoding="utf-8")
        assert "btop-theme-studio" in keybinds, (
            "the studio must have a provisioned keybind launcher"
        )


class TestRetiredGuiSourceRoot:
    def test_retired_gui_source_root_is_gone(self) -> None:
        """Every app moved into the `ags-apps` unit (slices 3-8), so the in-repo
        GUI source root has no remaining purpose. It must not exist even as an
        empty leftover: an empty directory is the obvious place for a future
        in-repo source that no gate deploys. `deploy-coverage` asserts the same
        absence; this pins the repo state directly."""
        retired = _REPO_ROOT / "src" / "gui-tools"
        assert not retired.exists(), (
            "the retired in-repo GUI source root src/gui-tools/ must be deleted "
            "— every app deploys WHOLE from the ags-apps unit"
        )
