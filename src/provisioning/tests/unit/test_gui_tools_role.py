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

    def test_no_become_anywhere(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere."""
        for task in _tasks():
            assert "become" not in task and "become_user" not in task, (
                f"task must not use become: {task.get('name')}"
            )


class TestGuiToolsVars:
    _REQUIRED_KEYS = {
        "gui_tools_repo_root",
        "gui_tools_spine_config_dir",
        "gui_tools_config_dirs",
        "gui_tools_app_files",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_app_files_exact_list(self) -> None:
        """The capture app file set, exactly: entry point, stylesheet,
        types, dialog + kept scaffolding (views + controllers)."""
        files = list(_vars()["gui_tools_app_files"])
        assert len(files) == 10, f"expected exactly 10 app files; found {len(files)}"
        sources = sorted(str(f["source"]) for f in files)
        expected = [
            "src/gui-tools/capture-tool/app.tsx",
            "src/gui-tools/capture-tool/controllers/CaptureController.ts",
            "src/gui-tools/capture-tool/controllers/RecordingController.ts",
            "src/gui-tools/capture-tool/controllers/ScreenshotController.ts",
            "src/gui-tools/capture-tool/controllers/TargetResolver.ts",
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
