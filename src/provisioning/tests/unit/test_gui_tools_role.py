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
        types, the classic layout, the capture-owned icon registry (the per-app
        registry pattern) deployed beside the app sources so the instance resolves
        palette-aware icons with fallback to the shared bar manifest, and the
        PURE domain layer the layout now imports (refactor-capture-tool-hexagonal
        A3 task 3.6 — the layout has no runtime meaning without it).

        The pre-hexagonal views + controllers were removed by
        refactor-capture-tool-hexagonal (A1 task 1.4): they were unimplemented
        scaffolding, and their placement entries went with them.

        The shared builder kit in ui/shared/ joined them in the same change
        (A7 task 7.4). Both layouts import it -- registering it is what stops a
        second layout from growing its own divergent row builders -- but
        placement is per-file, so an unregistered file silently never deploys.

        The ports/ and adapters/ layers joined them next (A5 tasks 5.1-5.8):
        the layout imports ports/ and the composition root injects
        adapters/, so a missing member of either layer is a panel that cannot
        bundle at runtime. This exact list is the only thing standing between
        A5 and a role that passes against a tree whose adapters are absent.

        The request->argv translator joined them in the same change (A6 tasks
        6.1-6.3): domain/capture-request.ts (the value objects) and
        domain/cli-args.ts (the SINGLE module that writes an argv literal for
        `capture-tool screenshot|start`). Both are loaded through the bundle,
        and cli-args.ts carries the two tokens the backend's argparse rejects
        (--size 75 not 75%, --audio mic not microphone) -- so an unregistered
        member of this pair is a capture that silently never happens, not a
        build error someone would notice.

        ui/classic/ replaced the single ui/CaptureWindow.tsx in the same
        change (A8 tasks 8.1-8.6): ClassicWindow.tsx (the shell) plus the
        three top-level views it renders. ClassicWindow reaches all three
        pages only through its own imports, so an unregistered page is a
        capture panel that cannot bundle -- the same failure the ports and
        adapters entries guard against.

        The monitor lifecycle joined them in fix-capture-monitor-lifecycle,
        with the same argument and one more: app.tsx now IMPORTS these
        directly rather than calling get_monitors() itself, so an undeployed
        member does not fail a build check -- it fails at bundle time, on the
        host, with a capture panel that never opens. Six files:
          domain/monitor-registry.ts   the pure plan/order decisions
          ports/monitor-topology.ts    read the monitors, be told when they change
          ports/monitor-focus.ts       which monitor the user is on
          adapters/gdk-monitor-topology.ts   the hotplug subscription
          adapters/hyprland-monitor-focus.ts  the focus source GTK4 lacks
          adapters/monitor-window-set.ts      one window per monitor, always"""
        files = list(_vars()["gui_tools_app_files"])
        assert len(files) == 30, f"expected exactly 30 app files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/capture-tool/adapters/exec-backend-probe.ts",
            "src/gui-tools/capture-tool/adapters/exec-capture-launcher.ts",
            "src/gui-tools/capture-tool/adapters/gdk-monitor-topology.ts",
            "src/gui-tools/capture-tool/adapters/glib-settings-store.ts",
            "src/gui-tools/capture-tool/adapters/glib-ui-state-store.ts",
            "src/gui-tools/capture-tool/adapters/hyprland-monitor-focus.ts",
            "src/gui-tools/capture-tool/adapters/monitor-window-set.ts",
            "src/gui-tools/capture-tool/app.tsx",
            "src/gui-tools/capture-tool/domain/capture-request.ts",
            "src/gui-tools/capture-tool/domain/cli-args.ts",
            "src/gui-tools/capture-tool/domain/monitor-registry.ts",
            "src/gui-tools/capture-tool/domain/settings.ts",
            "src/gui-tools/capture-tool/domain/ui-state.ts",
            "src/gui-tools/capture-tool/lib/icon-registry.ts",
            "src/gui-tools/capture-tool/ports/backend-probe.ts",
            "src/gui-tools/capture-tool/ports/capture-launcher.ts",
            "src/gui-tools/capture-tool/ports/capture-ports.ts",
            "src/gui-tools/capture-tool/ports/monitor-focus.ts",
            "src/gui-tools/capture-tool/ports/monitor-topology.ts",
            "src/gui-tools/capture-tool/ports/settings-store.ts",
            "src/gui-tools/capture-tool/ports/ui-state-store.ts",
            "src/gui-tools/capture-tool/style.css",
            "src/gui-tools/capture-tool/types.ts",
            "src/gui-tools/capture-tool/ui/classic/ClassicWindow.tsx",
            "src/gui-tools/capture-tool/ui/classic/RecordingPage.tsx",
            "src/gui-tools/capture-tool/ui/classic/ScreenshotPage.tsx",
            "src/gui-tools/capture-tool/ui/classic/SettingsPage.tsx",
            "src/gui-tools/capture-tool/ui/shared/groups.ts",
            "src/gui-tools/capture-tool/ui/shared/icons.ts",
            "src/gui-tools/capture-tool/ui/shared/rows.ts",
        ]
        assert sources == expected, (
            f"gui_tools_app_files sources must be exactly {expected}; got {sources}"
        )

    def test_app_sources_exist_in_repo(self) -> None:
        """Every source resolves to a real repo file (typo-proof)."""
        for entry in _vars()["gui_tools_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"app source missing from repo: {entry['source']}"

    def test_retired_capture_sources_are_removed_from_the_spine(self) -> None:
        """Per-file placement only WRITES, so a source dropped from
        gui_tools_app_files leaves its placed copy on disk forever. The capture
        app's hexagonal refactor retired four pre-refactor sources; without an
        explicit removal task they persist in derived state, where they are the
        exact "parallel, never-exercised architecture" the refactor deleted,
        invisible to every gate (the gates read the repo, not the spine)."""
        obsolete = _vars()["gui_tools_capture_obsolete"]
        assert len(obsolete) == 4, f"expected 4 retired paths; found {len(obsolete)}"

        removal_tasks = [
            t
            for t in _tasks()
            if t.get("ansible.builtin.file", {}).get("state") == "absent"
            and "gui_tools_capture_obsolete" in str(t.get("loop", ""))
        ]
        assert len(removal_tasks) == 1, (
            "expected exactly one task looping gui_tools_capture_obsolete with "
            f"state: absent; found {len(removal_tasks)}"
        )
        task = removal_tasks[0]
        assert task.get("when") == "not ansible_check_mode", (
            "the removal must be check-gated: under --check it reports what "
            "would go without deleting it"
        )

    def test_retired_capture_sources_are_not_also_placed(self) -> None:
        """A path cannot be both placed and removed in the same run. This is the
        ordering that would silently no-op one of the two tasks."""
        placed = {str(e["dest"]) for e in _vars()["gui_tools_app_files"]}
        obsolete = set(_vars()["gui_tools_capture_obsolete"])
        overlap = placed & obsolete
        assert not overlap, f"paths both placed and removed: {sorted(overlap)}"

    def test_retired_capture_paths_are_the_real_pre_refactor_ones(self) -> None:
        """Pins WHICH paths are retired, so a future layout move that retires a
        different set cannot pass by editing the list silently. Each entry must
        name a spine path under ags-capture/ that is no longer a placed dest."""
        placed = {str(e["dest"]) for e in _vars()["gui_tools_app_files"]}
        expected_suffixes = {
            "ui/CaptureWindow.tsx",
            "ui/RecordingView.tsx",
            "ui/ScreenshotView.tsx",
            "controllers",
        }
        suffixes = {
            str(p).split("ags-capture/", 1)[1] for p in _vars()["gui_tools_capture_obsolete"]
        }
        assert suffixes == expected_suffixes, (
            f"gui_tools_capture_obsolete must be exactly {sorted(expected_suffixes)}; "
            f"got {sorted(suffixes)}"
        )
        for path in _vars()["gui_tools_capture_obsolete"]:
            assert str(path) not in placed, f"still placed, do not remove: {path}"

    def test_icme_app_files_exact_list(self) -> None:
        """The icon color mapping editor file set, exactly: entry point,
        stylesheet, dialogs, and every lib module the editor imports — including
        the Phase 5 event seam (event-contract.ts + event-bus.ts) plus the
        wallpaper.state consumer core (event-bus-core.ts) behind the live
        palette refresh. Deployed by the raw-copy task (NOT template: literal
        {{PLACEHOLDER}} sequences would be destroyed by Jinja2)."""
        files = list(_vars()["gui_tools_icme_app_files"])
        assert len(files) == 22, f"expected exactly 22 icme files; found {len(files)}"
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
            "src/gui-tools/icon-color-mapping-editor/lib/theme.ts",
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

    def test_wallpaper_selector_app_files_exact_list(self) -> None:
        """The wallpaper selector file set, exactly: entry point, stylesheet,
        P5 window, and every lib module it imports (scan/thumbnails/apply/
        contrast plus the Phase 5 event seam: icon-registry, event-bus-core,
        event-bus)."""
        files = list(_vars()["gui_tools_wallpaper_selector_app_files"])
        assert len(files) == 12, f"expected exactly 12 selector files; found {len(files)}"
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
            "src/gui-tools/wallpaper-selector/lib/theme.ts",
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
    """btop-theme-studio is provisioned as its OWN AGS instance, launch-on-demand
    only — never in the bar's app.tsx, never autostarted (capability
    `btop-theme-studio`, tasks 1.1-1.3)."""

    _EXPECTED_SOURCES = [
        "src/gui-tools/btop-theme-studio/app.tsx",
        "src/gui-tools/btop-theme-studio/lib/btop-conf.ts",
        "src/gui-tools/btop-theme-studio/lib/key-map.ts",
        "src/gui-tools/btop-theme-studio/lib/key-widgets.generated.ts",
        "src/gui-tools/btop-theme-studio/lib/preview.ts",
        "src/gui-tools/btop-theme-studio/lib/schematic.ts",
        "src/gui-tools/btop-theme-studio/lib/targets.ts",
        "src/gui-tools/btop-theme-studio/lib/theme-keys.ts",
        "src/gui-tools/btop-theme-studio/lib/theme-model.ts",
        "src/gui-tools/btop-theme-studio/live/btop_live.py",
        "src/gui-tools/btop-theme-studio/style.css",
        "src/gui-tools/btop-theme-studio/ui/StudioWindow.tsx",
    ]

    def test_btop_studio_app_files_exact_list(self) -> None:
        files = list(_vars()["gui_tools_btop_studio_app_files"])
        sources = sorted(str(f["source"]) for f in files)
        assert sources == self._EXPECTED_SOURCES, (
            f"gui_tools_btop_studio_app_files sources must be exactly "
            f"{self._EXPECTED_SOURCES}; got {sources}"
        )
        for entry in files:
            dest = str(entry["dest"])
            assert dest.startswith("{{ gui_tools_spine_config_dir }}/ags-btop-studio/"), (
                f"studio dest must derive from gui_tools_spine_config_dir/ags-btop-studio: {dest}"
            )

    def test_btop_studio_sources_exist_in_repo(self) -> None:
        for entry in _vars()["gui_tools_btop_studio_app_files"]:
            path = _REPO_ROOT / str(entry["source"])
            assert path.is_file(), f"studio app source missing from repo: {entry['source']}"

    def test_every_btop_studio_dest_parent_is_an_ensured_dir(self) -> None:
        data = _vars()
        ensured = {
            str(d).replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            for d in data["gui_tools_config_dirs"]
        }
        for entry in data["gui_tools_btop_studio_app_files"]:
            dest = str(entry["dest"])
            parent = dest.rsplit("/", 1)[0].replace("{{ gui_tools_spine_config_dir }}", "<spine>")
            assert parent in ensured, (
                f"dest parent {parent!r} of {entry['name']} is not an ensured dir; "
                "add it to gui_tools_config_dirs"
            )

    def test_btop_studio_placed_via_raw_copy(self) -> None:
        """JSX style objects contain `{{` sequences, so the studio takes the
        raw-copy path (like icme), not template placement."""
        tasks = [
            task
            for task in _tasks()
            if task.keys() & {"ansible.builtin.copy"}
            and "gui_tools_btop_studio_app_files" in str(task.get("loop", ""))
        ]
        assert len(tasks) == 1, "expected exactly one raw-copy task for the studio"
        assert _module(tasks[0]).get("force") is True

    def test_ags_instances_include_btop_studio(self) -> None:
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
        autostart = (_REPO_ROOT / "dotfiles/config/hypr/autostart.lua").read_text(encoding="utf-8")
        assert "btop-theme-studio" not in autostart and "ags-btop-studio" not in autostart, (
            "the studio must not be autostarted (launch-on-demand only)"
        )
        keybinds = (_REPO_ROOT / "dotfiles/config/hypr/keybindings.lua").read_text(encoding="utf-8")
        assert "btop-theme-studio" in keybinds, (
            "the studio must have a provisioned keybind launcher"
        )
