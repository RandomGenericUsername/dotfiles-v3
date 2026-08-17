from __future__ import annotations

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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "zsh_tools"
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
    assert isinstance(module, dict)
    return module


def _module_text(task: dict[str, object]) -> str:
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return module
    assert isinstance(module, dict)
    return " ".join(str(value) for value in module.values())


def _tasks_with_module(module: str) -> list[dict[str, object]]:
    return [task for task in _load_tasks() if _module_key(task) == module]


def _git_clone_tasks() -> list[dict[str, object]]:
    return [
        t
        for t in _tasks_with_module("ansible.builtin.git")
        if "clone" in str(t.get("name", "")).lower()
    ]


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


class TestZshToolsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "zsh-tools.yaml").is_file(), "missing playbooks/zsh-tools.yaml"


class TestZshToolsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_home_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud HOME assert (vars derive ansible_facts.env.HOME)"
        )
        that = str(_module(first).get("that", ""))
        assert "ansible_facts.env.HOME" in that

    def test_clones_exactly_the_three_shell_tools(self) -> None:
        """The role provisions exactly oh-my-zsh, pyenv, nvm (git clone,
        presence-guarded with creates:) — dedicated, explicit."""
        clones = _git_clone_tasks()
        assert len(clones) == 3, (
            f"expected exactly three git-clone tasks (oh-my-zsh/pyenv/nvm); found {len(clones)}"
        )
        names = {str(t.get("name")) for t in clones}
        assert names == {"Clone oh-my-zsh", "Clone pyenv", "Clone nvm"}, (
            f"expected the three named clones; got {names}"
        )
        for task in clones:
            module = _module(task)
            assert "{{ shell." in str(module.get("dest", "")), (
                f"clone {task.get('name')!r} dest must derive from shell.* dirs"
            )
            assert module.get("repo") is not None, f"clone {task.get('name')!r} must set repo"

    def test_clones_are_check_gated_and_presence_guarded(self) -> None:
        """Each clone is presence-guarded (a stat checks the target dir) and
        --check-gated (dry-run must not clone). The git module does not accept
        creates:, so the stat guard is the idempotency mechanism."""
        stat_task = next(
            (t for t in _load_tasks() if "Check shell tool dirs exist" == str(t.get("name"))),
            None,
        )
        assert stat_task is not None, "missing 'Check shell tool dirs exist' stat task"
        assert "{{ shell.oh_my_zsh_dir }}" in str(stat_task.get("loop", ""))
        assert "{{ shell.pyenv_dir }}" in str(stat_task.get("loop", ""))
        assert "{{ shell.nvm_dir }}" in str(stat_task.get("loop", ""))

        clones = _git_clone_tasks()
        assert len(clones) == 3
        for task in clones:
            when = task.get("when")
            assert isinstance(when, list), (
                f"clone {task.get('name')!r} must be check-gated + presence-guarded (list when)"
            )
            assert "not ansible_check_mode" in when, (
                f"clone {task.get('name')!r} must be --check-gated"
            )
            assert any("zsh_tools_dir_checks" in str(w) for w in when), (
                f"clone {task.get('name')!r} must be presence-guarded via zsh_tools_dir_checks"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"zsh_tools must not use become (task {task.get('name')!r})"
            )


class TestZshToolsPlaybook:
    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                ansible_playbook,
                "--syntax-check",
                str(_PLAYBOOKS_DIR / "zsh-tools.yaml"),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
