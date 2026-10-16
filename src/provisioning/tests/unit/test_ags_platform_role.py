"""Tests for the ags_platform role (spine AD-17/AD-23).

The role installs the AGS platform as ONE versioned unit and creates the
shared-ancestor `node_modules/ags-platform` shortcut every AGS config resolves
the bare specifier through. These tests pin the STRUCTURE (the role, the
playbook, the vars' shapes, the presence guard, the check gating, the `.git`
removal, the pin record, the shortcut) and EXECUTE the playbook against a
pre-seeded unit so the pin + shortcut are proven by a real run — without a
network clone (the clone is presence-guarded; the fetch is proven separately by
the deploy-coverage gate's role assertion and the manual simulated install).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

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
}


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found walking up from the test file")


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "ags_platform"
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"


def _load_tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLES_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return data


def _module_key(task: dict[str, object]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, object]) -> dict[str, object]:
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return {}
    assert isinstance(module, dict)
    return module


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _named(name: str) -> dict[str, object]:
    task = next((t for t in _load_tasks() if t.get("name") == name), None)
    assert task is not None, f"missing task {name!r}"
    return task


class TestAgsPlatformRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "ags-platform.yaml").is_file(), (
            "missing playbooks/ags-platform.yaml"
        )


class TestAgsPlatformVars:
    def test_pins_one_version(self) -> None:
        data = _vars()
        version = str(data["ags_platform_version"])
        assert version.startswith("v"), "the pin must be a release tag (e.g. v0.1.0)"
        assert data["ags_platform_repo_url"].startswith("https://github.com/"), (
            "the unit is cloned over anonymous HTTPS"
        )

    def test_unit_is_under_the_versioned_install_root(self) -> None:
        data = _vars()
        assert "install_dir" in str(data["ags_platform_install_root"])
        assert "ags-platform" in str(data["ags_platform_install_root"])
        assert "ags_platform_version" in str(data["ags_platform_unit_dir"])
        assert "ags_platform_install_root" in str(data["ags_platform_unit_dir"])

    def test_shortcut_is_the_shared_ancestor(self) -> None:
        """The shortcut lives under <install>/config/node_modules so config/ags
        AND every config/ags-* resolve the bare specifier (AD-17)."""
        data = _vars()
        assert "install_dir" in str(data["ags_platform_spine_config_dir"])
        assert "config" in str(data["ags_platform_spine_config_dir"])
        assert "node_modules" in str(data["ags_platform_shortcut_dir"])
        assert str(data["ags_platform_shortcut"]).endswith("/ags-platform")

    def test_unit_marker_guards_the_clone(self) -> None:
        data = _vars()
        assert str(data["ags_platform_unit_marker"]).endswith("/index.ts")
        assert "ags_platform_unit_dir" in str(data["ags_platform_unit_marker"])


class TestAgsPlatformTasks:
    def test_tasks_parse_to_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        first = _load_tasks()[0]
        assert _module_key(first) == "ansible.builtin.assert"
        assert "install_dir" in str(_module(first).get("that", ""))

    def test_clone_is_shallow_pinned_presence_guarded_and_check_gated(self) -> None:
        clone = _named("Clone the pinned ags-platform unit (shallow, anonymous HTTPS)")
        assert _module_key(clone) == "ansible.builtin.git"
        module = _module(clone)
        assert module["version"] == "{{ ags_platform_version }}"
        assert module["depth"] == 1, "the clone must be shallow"
        assert module["dest"] == "{{ ags_platform_unit_dir }}"
        when = clone.get("when")
        assert isinstance(when, list)
        assert "not ansible_check_mode" in when, "the clone must be --check-gated"
        assert any("ags_platform_unit_check" in str(w) for w in when), (
            "the clone must be presence-guarded via the stat register"
        )

    def test_git_dir_is_removed(self) -> None:
        task = _named(
            "Remove the clone's .git (deploy the unit as a source tree, not a checkout)"
        )
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "absent"
        assert str(module["path"]).endswith("/.git")

    def test_pin_is_recorded(self) -> None:
        task = _named("Record the pinned framework version")
        assert _module_key(task) == "ansible.builtin.copy"
        module = _module(task)
        assert module["dest"] == "{{ ags_platform_pin_file }}"
        assert "ags_platform_version" in str(module["content"])

    def test_shortcut_is_forced_symlink_into_the_unit(self) -> None:
        task = _named("Point the shared-ancestor shortcut at the pinned unit")
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a rollback repoint converge"
        assert module["src"] == "{{ ags_platform_unit_dir }}"
        assert module["dest"] == "{{ ags_platform_shortcut }}"

    def test_no_become_anywhere(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"ags_platform must not use become (task {task.get('name')!r})"
            )


class TestAgsPlatformPlaybook:
    _PATH = _PLAYBOOKS_DIR / "ags-platform.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["ags_platform"]
        assert "become" not in play

    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [ansible_playbook, "--syntax-check", str(self._PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestAgsPlatformExecution:
    """Run the real playbook against a pre-seeded unit (no network): the clone
    is presence-guarded, so the run exercises the pin + shortcut path."""

    _PATH = _PLAYBOOKS_DIR / "ags-platform.yaml"

    def _run(self, install: Path, home: Path) -> subprocess.CompletedProcess[str]:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env["HOME"] = str(home)
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        return subprocess.run(
            [ansible_playbook, str(self._PATH), "-e", f"install_dir={install}"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

    def test_places_pin_and_shortcut_for_a_present_unit(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        # Pre-seed the pinned unit so the presence-guarded clone is skipped.
        unit = install / "ags-platform" / "v0.1.0"
        (unit / "ports").mkdir(parents=True)
        (unit / "index.ts").write_text("export {}\n")
        (unit / "package.json").write_text("{}")
        (unit / "ports" / "reactive.ts").write_text("")

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        pin = install / "ags-platform" / "pinned"
        assert pin.is_file(), "the pin must be recorded"
        assert pin.read_text().strip() == "v0.1.0"

        shortcut = install / "config" / "node_modules" / "ags-platform"
        assert shortcut.is_symlink(), "the shared-ancestor shortcut must be a symlink"
        assert shortcut.resolve() == unit.resolve(), (
            "the shortcut must point at the pinned unit"
        )
        assert not (unit / ".git").exists(), "the clone's .git must be removed"

        # Idempotent: a second run converges to the same state.
        second = self._run(install, home)
        assert second.returncode == 0, second.stdout + second.stderr
        assert shortcut.resolve() == unit.resolve()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
