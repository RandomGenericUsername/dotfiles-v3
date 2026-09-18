"""Structural tests for the gui_tools role (extract-capture-gui-tool).

Mirrors test_compositor_configs_role.py, trimmed to app placement: the role
places standalone GUI app sources (src/gui-tools/<tool>/) into their own
config-in-spine dirs via per-file template copies, repo-authoritative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

    def test_app_files_placed_via_template_force(self) -> None:
        """Per-file `template` + `force: true` (repo-authoritative, mirror of
        the compositor_configs decision 2026-08-26 — never a directory src)."""
        tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.template"}
            and "gui_tools_app_files" in str(task.get("loop", ""))
        ]
        assert tasks, "no app-file placement task found"
        for task in tasks:
            assert _module(task).get("force") is True

    def test_wallpaper_selector_files_placed_via_template_force(self) -> None:
        """Per-file `template` + `force: true` (repo-authoritative) for the
        selector list — same placement discipline as the sibling apps."""
        tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.template"}
            and "gui_tools_wallpaper_selector_app_files" in str(task.get("loop", ""))
        ]
        assert tasks, "no selector placement task found"
        for task in tasks:
            assert _module(task).get("force") is True

    def test_notifications_files_placed_via_template_force(self) -> None:
        """Per-file `template` + `force: true` (repo-authoritative) for the
        notifications list — same placement discipline as the sibling apps."""
        tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.template"}
            and "gui_tools_notifications_app_files" in str(task.get("loop", ""))
        ]
        assert tasks, "no notifications placement task found"
        for task in tasks:
            assert _module(task).get("force") is True

    def test_legacy_capture_subtree_removed(self) -> None:
        """Reprovision convergence: the bar spine's old ags/capture/ subtree
        is removed (superseded by ags-capture/)."""
        tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.file"}
            and "ags/capture" in str(_module(task).get("path", ""))
        ]
        assert tasks, "no legacy capture-subtree removal task found"
        for task in tasks:
            assert _module(task).get("state") == "absent"

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
        "gui_tools_app_files",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_app_files_exact_list(self) -> None:
        """The capture app file set, exactly: entry point, stylesheet,
        types, dialog + kept scaffolding (views + controllers), plus the
        capture-owned icon registry (hypr-pano pattern) deployed beside the
        app sources so the instance resolves palette-aware icons with
        fallback to the shared bar manifest."""
        files = list(_vars()["gui_tools_app_files"])
        assert len(files) == 11, f"expected exactly 11 app files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/capture-tool/app.tsx",
            "src/gui-tools/capture-tool/controllers/CaptureController.ts",
            "src/gui-tools/capture-tool/controllers/RecordingController.ts",
            "src/gui-tools/capture-tool/controllers/ScreenshotController.ts",
            "src/gui-tools/capture-tool/controllers/TargetResolver.ts",
            "src/gui-tools/capture-tool/lib/icon-registry.ts",
            "src/gui-tools/capture-tool/style.css",
            "src/gui-tools/capture-tool/types.ts",
            "src/gui-tools/capture-tool/ui/CaptureWindow.tsx",
            "src/gui-tools/capture-tool/ui/RecordingView.tsx",
            "src/gui-tools/capture-tool/ui/ScreenshotView.tsx",
        ]
        assert sources == expected, (
            f"gui_tools_app_files sources must be exactly {expected}; got {sources}"
        )

    def test_app_sources_exist_in_repo(self) -> None:
        """Every source resolves to a real repo file (typo-proof)."""
        for entry in _vars()["gui_tools_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"app source missing from repo: {entry['source']}"

    def test_icme_app_files_exact_list(self) -> None:
        """The icon color mapping editor file set, exactly: entry point,
        stylesheet, dialogs, and every lib module the editor imports — including
        the Phase 5 event seam (event-contract.ts + event-bus.ts) plus the
        wallpaper.state consumer core (event-bus-core.ts) behind the live
        palette refresh. Deployed by the raw-copy task (NOT template: literal
        {{PLACEHOLDER}} sequences would be destroyed by Jinja2)."""
        files = list(_vars()["gui_tools_icme_app_files"])
        assert len(files) == 21, f"expected exactly 21 icme files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/icon-color-mapping-editor/app.tsx",
            "src/gui-tools/icon-color-mapping-editor/lib/diff.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/event-bus-core.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/event-bus.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/event-contract.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/inputs.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/itr.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/model.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/substitute.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/svg.ts",
            "src/gui-tools/icon-color-mapping-editor/lib/templates.ts",
            "src/gui-tools/icon-color-mapping-editor/style.css",
            "src/gui-tools/icon-color-mapping-editor/ui/DiffPane.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/EditorWindow.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/GroupTree.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/InputsPanel.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/Preview.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/ScopeSwitch.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/SelectionPanel.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/TemplatesTab.tsx",
            "src/gui-tools/icon-color-mapping-editor/ui/TokenPicker.tsx",
        ]
        assert sources == expected, (
            f"gui_tools_icme_app_files sources must be exactly {expected}; got {sources}"
        )
        for entry in files:
            dest = str(entry["dest"])
            assert dest.startswith("{{ gui_tools_spine_config_dir }}/ags-icme/"), (
                f"icme dest must derive from gui_tools_spine_config_dir/ags-icme: {dest}"
            )

    def test_icme_app_sources_exist_in_repo(self) -> None:
        """Every icme source resolves to a real repo file (typo-proof)."""
        for entry in _vars()["gui_tools_icme_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"icme app source missing from repo: {entry['source']}"

    def test_every_icme_dest_parent_is_an_ensured_dir(self) -> None:
        """Regression lock: `copy` does NOT create dest parents, so every icme
        file dest's parent dir must be listed in gui_tools_config_dirs."""
        data = _vars()
        ensured = {
            str(d).replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            for d in data["gui_tools_config_dirs"]
        }
        for entry in data["gui_tools_icme_app_files"]:
            dest = str(entry["dest"])
            parent = dest.rsplit("/", 1)[0].replace(
                "{{ gui_tools_spine_config_dir }}", "<spine>"
            )
            assert parent in ensured, (
                f"dest parent {parent!r} of {entry['name']} is not an ensured "
                f"dir (copy would fail); add it to gui_tools_config_dirs"
            )

    def test_every_dest_parent_is_an_ensured_dir(self) -> None:
        """Regression lock (bootstrap failure 2026-09-05): `template` does
        NOT create dest parents, so every file dest's parent dir must be
        listed in gui_tools_config_dirs — otherwise placement fails with
        'Destination directory does not exist'."""
        data = _vars()
        ensured = {
            str(d).replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            for d in data["gui_tools_config_dirs"]
        }
        for entry in data["gui_tools_app_files"]:
            dest = str(entry["dest"])
            parent = dest.rsplit("/", 1)[0].replace(
                "{{ gui_tools_spine_config_dir }}", "<spine>"
            )
            assert parent in ensured, (
                f"dest parent {parent!r} of {entry['name']} is not an ensured "
                f"dir (template would fail); add it to gui_tools_config_dirs"
            )

    def test_hypr_pano_app_files_exact_list(self) -> None:
        """The clipboard overlay file set, exactly: entry point, stylesheet,
        dialogs, and every lib module the overlay imports (including the
        Phase 5 event seam: clipboard-types, history, event-bus-core, event-bus)."""
        files = list(_vars()["gui_tools_hypr_pano_app_files"])
        assert len(files) == 10, f"expected exactly 10 hypr-pano files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/hypr-pano/app.tsx",
            "src/gui-tools/hypr-pano/lib/clipboard-types.ts",
            "src/gui-tools/hypr-pano/lib/event-bus-core.ts",
            "src/gui-tools/hypr-pano/lib/event-bus.ts",
            "src/gui-tools/hypr-pano/lib/history.ts",
            "src/gui-tools/hypr-pano/lib/icon-registry.ts",
            "src/gui-tools/hypr-pano/style.css",
            "src/gui-tools/hypr-pano/ui/ItemCard.tsx",
            "src/gui-tools/hypr-pano/ui/PanoWindow.tsx",
            "src/gui-tools/hypr-pano/ui/Preview.tsx",
        ]
        assert sources == expected, (
            f"gui_tools_hypr_pano_app_files sources must be exactly {expected}; got {sources}"
        )
        for entry in files:
            dest = str(entry["dest"])
            assert dest.startswith("{{ gui_tools_spine_config_dir }}/ags-hypr-pano/"), (
                f"hypr-pano dest must derive from gui_tools_spine_config_dir/ags-hypr-pano: {dest}"
            )

    def test_hypr_pano_app_sources_exist_in_repo(self) -> None:
        """Every hypr-pano source resolves to a real repo file (typo-proof)."""
        for entry in _vars()["gui_tools_hypr_pano_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"hypr-pano app source missing from repo: {entry['source']}"

    def test_every_hypr_pano_dest_parent_is_an_ensured_dir(self) -> None:
        """Regression lock: `template` does NOT create dest parents, so every
        hypr-pano dest's parent dir must be listed in gui_tools_config_dirs."""
        data = _vars()
        ensured = {
            str(d).replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            for d in data["gui_tools_config_dirs"]
        }
        for entry in data["gui_tools_hypr_pano_app_files"]:
            dest = str(entry["dest"])
            parent = dest.rsplit("/", 1)[0].replace(
                "{{ gui_tools_spine_config_dir }}", "<spine>"
            )
            assert parent in ensured, (
                f"dest parent {parent!r} of {entry['name']} is not an ensured "
                f"dir (template would fail); add it to gui_tools_config_dirs"
            )

    def test_hypr_pano_sources_contain_no_jinja_sequences(self) -> None:
        """The hypr-pano sources are placed via `template`, so they must not
        contain Jinja-sensitive `{{`/`{%` sequences (which Jinja2 would
        evaluate and destroy). Pins the choice of template over raw copy."""
        for entry in _vars()["gui_tools_hypr_pano_app_files"]:
            text = (_REPO_ROOT / str(entry["source"])).read_text(encoding="utf-8")
            assert "{{" not in text and "{%" not in text, (
                f"{entry['source']} contains a Jinja sequence; use raw copy"
            )

    def test_wallpaper_selector_app_files_exact_list(self) -> None:
        """The wallpaper selector file set, exactly: entry point, stylesheet,
        P5 window, and every lib module it imports (scan/thumbnails/apply/
        contrast plus the Phase 5 event seam: icon-registry, event-bus-core,
        event-bus)."""
        files = list(_vars()["gui_tools_wallpaper_selector_app_files"])
        assert len(files) == 11, f"expected exactly 11 selector files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/wallpaper-selector/app.tsx",
            "src/gui-tools/wallpaper-selector/lib/apply.ts",
            "src/gui-tools/wallpaper-selector/lib/contrast.ts",
            "src/gui-tools/wallpaper-selector/lib/event-bus-core.ts",
            "src/gui-tools/wallpaper-selector/lib/event-bus.ts",
            "src/gui-tools/wallpaper-selector/lib/icon-registry.ts",
            "src/gui-tools/wallpaper-selector/lib/model.ts",
            "src/gui-tools/wallpaper-selector/lib/scan.ts",
            "src/gui-tools/wallpaper-selector/lib/thumbnails.ts",
            "src/gui-tools/wallpaper-selector/style.css",
            "src/gui-tools/wallpaper-selector/ui/WallpaperSelectorWindow.tsx",
        ]
        assert sources == expected, (
            f"gui_tools_wallpaper_selector_app_files sources must be exactly {expected}; got {sources}"
        )
        for entry in files:
            dest = str(entry["dest"])
            assert dest.startswith("{{ gui_tools_spine_config_dir }}/ags-wallpaper-selector/"), (
                f"selector dest must derive from gui_tools_spine_config_dir/ags-wallpaper-selector: {dest}"
            )

    def test_wallpaper_selector_app_sources_exist_in_repo(self) -> None:
        """Every selector source resolves to a real repo file (typo-proof)."""
        for entry in _vars()["gui_tools_wallpaper_selector_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"selector app source missing from repo: {entry['source']}"

    def test_every_wallpaper_selector_dest_parent_is_an_ensured_dir(self) -> None:
        """Regression lock: `template` does NOT create dest parents, so every
        selector dest's parent dir must be listed in gui_tools_config_dirs."""
        data = _vars()
        ensured = {
            str(d).replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            for d in data["gui_tools_config_dirs"]
        }
        for entry in data["gui_tools_wallpaper_selector_app_files"]:
            dest = str(entry["dest"])
            parent = dest.rsplit("/", 1)[0].replace(
                "{{ gui_tools_spine_config_dir }}", "<spine>"
            )
            assert parent in ensured, (
                f"dest parent {parent!r} of {entry['name']} is not an ensured "
                f"dir (template would fail); add it to gui_tools_config_dirs"
            )

    def test_wallpaper_selector_sources_contain_no_jinja_sequences(self) -> None:
        """The selector sources are placed via `template`, so they must not
        contain Jinja-sensitive `{{`/`{%` sequences (which Jinja2 would
        evaluate and destroy). Pins the choice of template over raw copy."""
        for entry in _vars()["gui_tools_wallpaper_selector_app_files"]:
            text = (_REPO_ROOT / str(entry["source"])).read_text(encoding="utf-8")
            assert "{{" not in text and "{%" not in text, (
                f"{entry['source']} contains a Jinja sequence; use raw copy"
            )

    def test_ags_instances_include_wallpaper_selector(self) -> None:
        """The selector instance must be quit after placement (bundles TS at
        startup and holds it in memory — same lifecycle as the siblings)."""
        instances = [str(i["name"]) for i in _vars()["gui_tools_ags_instances"]]
        assert "wallpaper-selector" in instances, (
            f"gui_tools_ags_instances must include wallpaper-selector; got {instances}"
        )

    def test_notifications_app_files_exact_list(self) -> None:
        """The notifd overlay file set, exactly: entry point, stylesheet,
        and the stack window (the overlay renders daemon-provided image
        paths directly, so it owns no icon registry — the EMITTER resolves
        current/icons/ paths in the capture backend)."""
        files = list(_vars()["gui_tools_notifications_app_files"])
        assert len(files) == 4, f"expected exactly 4 notifications files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/notifications/Makefile",
            "src/gui-tools/notifications/app.tsx",
            "src/gui-tools/notifications/style.css",
            "src/gui-tools/notifications/ui/NotificationsWindow.tsx",
        ]
        assert sources == expected, (
            f"gui_tools_notifications_app_files sources must be exactly {expected}; got {sources}"
        )
        for entry in files:
            dest = str(entry["dest"])
            assert dest.startswith("{{ gui_tools_spine_config_dir }}/ags-notifications/"), (
                f"notifications dest must derive from gui_tools_spine_config_dir/ags-notifications: {dest}"
            )

    def test_notifications_app_sources_exist_in_repo(self) -> None:
        """Every notifications source resolves to a real repo file (typo-proof)."""
        for entry in _vars()["gui_tools_notifications_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"notifications app source missing from repo: {entry['source']}"

    def test_every_notifications_dest_parent_is_an_ensured_dir(self) -> None:
        """Regression lock: `template` does NOT create dest parents, so every
        notifications dest's parent dir must be listed in gui_tools_config_dirs."""
        data = _vars()
        ensured = {
            str(d).replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            for d in data["gui_tools_config_dirs"]
        }
        for entry in data["gui_tools_notifications_app_files"]:
            dest = str(entry["dest"])
            parent = dest.rsplit("/", 1)[0].replace(
                "{{ gui_tools_spine_config_dir }}", "<spine>"
            )
            assert parent in ensured, (
                f"dest parent {parent!r} of {entry['name']} is not an ensured "
                f"dir (template would fail); add it to gui_tools_config_dirs"
            )

    def test_notifications_sources_contain_no_jinja_sequences(self) -> None:
        """The notifications sources are placed via `template`, so they must
        not contain Jinja-sensitive `{{`/`{%` sequences (which Jinja2 would
        evaluate and destroy). Pins the choice of template over raw copy."""
        for entry in _vars()["gui_tools_notifications_app_files"]:
            text = (_REPO_ROOT / str(entry["source"])).read_text(encoding="utf-8")
            assert "{{" not in text and "{%" not in text, (
                f"{entry['source']} contains a Jinja sequence; use raw copy"
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
