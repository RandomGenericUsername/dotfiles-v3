from __future__ import annotations

from pathlib import Path

import yaml


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from this test file; "
        "AC 1-7 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "gloview_plugin"

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
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _sudoers_task() -> dict[str, object]:
    matches = [t for t in _load_tasks() if "passwordless hyprpm" in str(t.get("name", ""))]
    assert len(matches) == 1, "expected exactly one hyprpm sudoers task"
    return matches[0]


def _invokes_hyprpm(task: dict[str, object]) -> bool:
    """True when the task executes hyprpm (shell cmd or command argv)."""
    for value in task.values():
        if isinstance(value, dict) and "hyprpm" in str(value.get("cmd", value.get("argv", ""))):
            return True
    return False


class TestGloviewPrivilegeArchitecture:
    """The rewritten hyprpm escalates internally via sudo and DIES as root, so
    no hyprpm invocation may use become — only the sudoers authoring (which
    grants exactly hyprpm's helper surface under /var/cache/hyprpm) runs
    privileged."""

    def test_sudoers_task_is_first_and_privileged(self) -> None:
        tasks = _load_tasks()
        first_hyprpm = next(i for i, t in enumerate(tasks) if _invokes_hyprpm(t))
        task = _sudoers_task()
        assert tasks.index(task) < first_hyprpm, (
            "the sudoers rule must land before any hyprpm invocation"
        )
        assert task.get("become") is True
        body = task.get("ansible.builtin.copy", {})
        assert isinstance(body, dict)
        assert "sudoers.d" in str(body.get("dest", ""))
        assert "visudo" in str(body.get("validate", "")), (
            "the sudoers file must be visudo-validated"
        )
        assert str(body.get("mode", "")) == "0440"
        content = str(body.get("content", ""))
        for helper in ("/usr/bin/mkdir", "/usr/bin/install", "/usr/bin/rm", "/usr/bin/echo"):
            assert helper in content, f"sudoers must cover the hyprpm helper {helper}"
        assert "/var/cache/hyprpm" in content
        assert "not ansible_check_mode" in str(task.get("when", "")), (
            "the sudoers task mutates and must be --check-gated"
        )

    def test_no_become_on_hyprpm_invocations(self) -> None:
        for task in _load_tasks():
            if _invokes_hyprpm(task):
                assert not task.get("become", False), (
                    f"hyprpm dies as superuser — task {task.get('name')!r} must not use become"
                )

    def test_mutating_tasks_skip_without_synced_headers(self) -> None:
        """The header sync needs an interactive sudo, so every mutating task
        (and the assert) must skip when the synced headers are absent instead
        of dying on an invisible prompt."""
        tasks = _load_tasks()
        check = next(t for t in tasks if "headers are synced" in str(t.get("name", "")))
        assert _module_key(check) == "ansible.builtin.stat"
        gated = [
            "Add the GloView repository",
            "Synchronize hyprpm headers",
            "Enable GloView",
            "Verify GloView is enabled",
            "Assert GloView installed",
        ]
        for task in tasks:
            name = str(task.get("name", ""))
            if any(want in name for want in gated):
                assert "gloview_store_check.stat.exists" in str(task.get("when", "")), (
                    f"task {name!r} must skip without synced headers"
                )

    def test_skip_warns_with_manual_command(self) -> None:
        tasks = _load_tasks()
        warn = next(t for t in tasks if "interactive header sync" in str(t.get("name", "")))
        assert "hyprpm update" in str(warn.get("msg", warn)), (
            "the skip warning must name the manual command"
        )
