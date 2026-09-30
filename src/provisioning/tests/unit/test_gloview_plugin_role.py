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


def _load_vars() -> dict[str, object]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _module_key(task: dict[str, object]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _task_text() -> str:
    return (_ROLES_DIR / "tasks" / "main.yml").read_text()


class TestGloviewAurContract:
    """GloView ships as /usr/lib/gloview.so via the gloview-git AUR package —
    no hyprpm anywhere in this flow (it requires a live Hyprland IPC session
    even for add/update, which a TTY provision can never provide). The role
    only asserts the artifact is present: fully headless-checkable."""

    def test_vars_point_at_aur_artifact(self) -> None:
        assert _load_vars()["gloview_plugin_so_path"] == "/usr/lib/gloview.so"

    def test_no_hyprpm_invocation(self) -> None:
        """No task may execute the hyprpm binary (the legacy cleanup task
        only removes its sudoers file — a path string, not an invocation)."""
        for task in _load_tasks():
            for key, value in task.items():
                if key.startswith("ansible.builtin.command") or key.startswith(
                    "ansible.builtin.shell"
                ):
                    assert "hyprpm" not in str(value), (
                        f"task {task.get('name')!r} must not invoke hyprpm"
                    )

    def test_stats_then_asserts_artifact(self) -> None:
        tasks = _load_tasks()
        stat = next(t for t in tasks if "artifact" in str(t.get("name", "")))
        assert _module_key(stat) == "ansible.builtin.stat"
        assert "gloview_plugin_so_path" in str(stat.get("ansible.builtin.stat", ""))
        names = [str(t.get("name", "")) for t in tasks]
        assert any("Assert GloView installed" in n for n in names)

    def test_no_become_except_legacy_cleanup(self) -> None:
        """Only the legacy hyprpm-sudoers removal runs privileged; the
        stat/assert pair is read-only user context."""
        for task in _load_tasks():
            name = str(task.get("name", ""))
            if "legacy" in name and "sudoers" in name:
                assert task.get("become") is True
            else:
                assert not task.get("become", False), (
                    f"task {name!r} must not use become"
                )

    def test_legacy_sudoers_cleanup_is_check_gated(self) -> None:
        tasks = _load_tasks()
        cleanup = next(t for t in tasks if "legacy" in str(t.get("name", "")))
        assert _module_key(cleanup) == "ansible.builtin.file"
        assert "not ansible_check_mode" in str(cleanup.get("when", "")), (
            "the sudoers removal mutates and must be --check-gated"
        )


class TestGloviewPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "gloview-plugin.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        """The playbook must gather facts: the role derives the login user
        (ansible_facts['user_id']) from discovered facts for the legacy
        sudoers path, so direct runs abort on undefined facts with
        gather_facts: false (live 2026-09-29)."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["gloview_plugin"]
