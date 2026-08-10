from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_packages_role.py``: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-5 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "cli_tools"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_MANIFEST_PATH = _REPO_ROOT / "dotfiles" / "provisioning" / "cli-tools.yaml"

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


def _creates_value(task: dict[str, object]) -> object | None:
    """Return the ``creates`` value whether declared top-level or in args."""
    direct = task.get("creates")
    if direct is not None:
        return direct
    args = task.get("args")
    if isinstance(args, dict):
        return args.get("creates")
    return None


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


def _install_tasks() -> list[dict[str, object]]:
    """The tasks that run `uv tool install` for each manifest entry."""
    return [
        task
        for task in _load_tasks()
        if "uv tool install" in str(task.get(_module_key(task) or "", ""))
    ]


class TestCliToolsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestCliToolsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_one_install_task_covers_all_manifest_entries(self) -> None:
        install_tasks = _install_tasks()
        assert len(install_tasks) == 1, (
            "exactly one `uv tool install` task expected (looping over "
            f"cli_tools), found {len(install_tasks)}"
        )
        task = install_tasks[0]
        assert _module_key(task) == "ansible.builtin.command"
        assert task.get("loop") == "{{ cli_tools }}"

    def test_install_task_creates_guard_is_dry_run_and_idempotent(self) -> None:
        """Locks AC5: `creates: {{ cli_tools_bin_dir }}/{{ item.name }}` is the
        ONLY mechanism on the install task — check-mode-safe by construction
        (filesystem check, not a registered rc)."""
        install_tasks = _install_tasks()
        assert install_tasks, "no uv tool install task found"
        for task in install_tasks:
            creates = _creates_value(task)
            assert creates == "{{ cli_tools_bin_dir }}/{{ item.name }}", (
                f"install task {task.get('name')!r} must carry "
                "creates: '{{ cli_tools_bin_dir }}/{{ item.name }}'"
            )

    def test_install_task_not_gated_on_presence_check_rc(self) -> None:
        """Locks the Story 2.3 check-mode lesson: under --check a skipped
        `command -v` registers rc=0, so gating the install on a presence-check
        rc would report `skipped` instead of would-change."""
        install_tasks = _install_tasks()
        assert install_tasks, "no uv tool install task found"
        for task in install_tasks:
            when = str(task.get("when", ""))
            assert "uv_check" not in when and "command -v" not in when, (
                f"install task {task.get('name')!r} must not gate on a presence-check rc"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: `uv tool install` targets the
        intended user, never root (running as root would install into
        /root/.local/bin and AC 3 would be silently false)."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_repo_paths_hardcoded(self) -> None:
        """Every source is `{{ cli_tools_repo_root }}/...`, never an absolute
        repo path baked into the task."""
        install_tasks = _install_tasks()
        assert install_tasks, "no uv tool install task found"
        for task in install_tasks:
            command = str(task.get("ansible.builtin.command", ""))
            assert command.startswith("uv tool install {{ cli_tools_repo_root }}/"), (
                f"install task {task.get('name')!r} must use "
                "'{{ cli_tools_repo_root }}/{{ item.source }}'"
            )
            assert "{{ item.source }}" in command


class TestCliToolsVars:
    def test_vars_parse_with_required_keys(self) -> None:
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert isinstance(data, dict), "vars/main.yml must parse to a dict"
        assert {"cli_tools_repo_root", "cli_tools_bin_dir", "cli_tools"}.issubset(set(data))

    def test_cli_tools_parity_with_manifest(self) -> None:
        """Parity lock: the role var exactly mirrors the manifest by
        (name, source) so they can never silently diverge (AC 2)."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        role_entries = [dict(item) for item in data["cli_tools"]]
        manifest_entries = _manifest_entries()
        assert len(role_entries) == len(manifest_entries)
        assert {tuple(e.items()) for e in role_entries} == {
            tuple(e.items()) for e in manifest_entries
        }

    def test_cli_tools_bin_dir_defaults_under_home(self) -> None:
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert "{{ ansible_env.HOME }}/.local/bin" in str(data["cli_tools_bin_dir"])


class TestCliToolsPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "cli-tools.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["cli_tools"]
        assert "become" not in play, "cli-tools playbook must not use become"

    def test_syntax_check_exits_zero(self) -> None:
        env = dict(os.environ)
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                "ansible-playbook",
                "--syntax-check",
                str(self._PATH),
                "-e",
                "os_family=arch",
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
