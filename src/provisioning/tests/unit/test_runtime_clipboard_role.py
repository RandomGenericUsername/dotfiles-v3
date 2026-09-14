"""D1 role tests — the clipboard watcher's --user unit (runtime_clipboard role).

Structural YAML tests (no live systemd/user manager): the unit template is
rendered with StrictUndefined and asserted per-section, tasks are pinned for
privilege/check-mode/probe semantics, and the handler notifies only on an
actual template change (the 6dd697f convergence fix).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found walking up from the test file")


_ANSIBLE_DIR = _find_ansible_dir()
_ROLE_DIR = _ANSIBLE_DIR / "roles" / "runtime_clipboard"

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
    "vars",
    "loop",
    "tags",
    "environment",
    "ignore_errors",
    "notify",
    "check_mode",
}

_RENDER_VARS = {
    "runtime_clipboard_bin_dir": "/home/tester/.local/bin",
    "runtime_clipboard_unit_name": "dotfiles-runtime-clipboard.service",
    "runtime_clipboard_daemon_unit_name": "dotfiles-runtime-daemon.service",
    "runtime_clipboard_restart_sec": 5,
    "runtime_clipboard_start_limit_interval_sec": 60,
    "runtime_clipboard_start_limit_burst": 3,
}


def _load_tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLE_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return [dict(entry) for entry in data]


def _load_handlers() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLE_DIR / "handlers" / "main.yml").read_text())
    assert isinstance(data, list)
    return [dict(entry) for entry in data]


def _module_key(task: dict[str, object]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS:
            return key
    return None


def _render_unit(**overrides: object) -> str:
    template = (_ROLE_DIR / "templates" / "dotfiles-runtime-clipboard.service.j2").read_text()
    env = Environment(
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env.from_string(template).render(**{**_RENDER_VARS, **overrides})


def _section(rendered: str, name: str) -> str:
    lines = rendered.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == f"[{name}]")
    except StopIteration:
        raise AssertionError(f"section [{name}] missing from rendered unit") from None

    def _is_header(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("[") and stripped.endswith("]")

    end = next((i for i in range(start + 1, len(lines)) if _is_header(lines[i])), len(lines))
    return "\n".join(lines[start + 1 : end])


class TestRoleTree:
    def test_role_tree_exists(self) -> None:
        assert (_ROLE_DIR / "tasks" / "main.yml").is_file()
        assert (_ROLE_DIR / "templates" / "dotfiles-runtime-clipboard.service.j2").is_file()
        assert (_ROLE_DIR / "vars" / "main.yml").is_file()
        assert (_ROLE_DIR / "handlers" / "main.yml").is_file()

    def test_tasks_parse_to_named_list(self) -> None:
        for task in _load_tasks():
            assert isinstance(task.get("name"), str) and task["name"]

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert "become" not in task and "become_user" not in task, task["name"]


class TestUnitContent:
    def test_type_simple_and_foreground_clipboard(self) -> None:
        rendered = _render_unit()
        service = _section(rendered, "Service")
        assert "Type=simple" in service
        assert 'ExecStart="/home/tester/.local/bin/dotfiles-runtime" clipboard' in rendered

    def test_start_limits_in_unit_section_not_service(self) -> None:
        unit = _section(_render_unit(), "Unit")
        service = _section(_render_unit(), "Service")
        assert "StartLimitIntervalSec=60" in unit
        assert "StartLimitBurst=3" in unit
        assert "StartLimit" not in service

    def test_restart_always(self) -> None:
        service = _section(_render_unit(), "Service")
        assert "Restart=always" in service
        assert "Restart=on-failure" not in service
        assert "RestartSec=5" in service

    def test_orders_after_hub_and_session(self) -> None:
        unit = _section(_render_unit(), "Unit")
        assert "Requires=dbus.socket" in unit
        assert "After=dbus.socket graphical-session.target" in unit
        assert "After=dotfiles-runtime-daemon.service" in unit
        assert "Wants=dotfiles-runtime-daemon.service" in unit

    def test_install_wanted_by_session(self) -> None:
        assert "WantedBy=graphical-session.target" in _section(_render_unit(), "Install")

    def test_exec_start_line_not_merged_with_following_comment(self) -> None:
        rendered = _render_unit()
        exec_lines = [line for line in rendered.splitlines() if line.startswith("ExecStart=")]
        assert len(exec_lines) == 1, exec_lines
        assert exec_lines[0] == (
            'ExecStart="/home/tester/.local/bin/dotfiles-runtime" clipboard'
        )
        assert "#" not in exec_lines[0]

    def test_renders_with_undefined_vars_rejected(self) -> None:
        template = (
            _ROLE_DIR / "templates" / "dotfiles-runtime-clipboard.service.j2"
        ).read_text()
        assert "{{" in template
        _render_unit()  # StrictUndefined raises on any missing var


class TestTasks:
    def test_manager_probe_never_fails(self) -> None:
        probe = next(t for t in _load_tasks() if "Probe" in str(t["name"]))
        assert _module_key(probe) == "ansible.builtin.shell"
        assert probe.get("failed_when") is False
        assert probe.get("changed_when") is False

    def test_binary_precondition_fails_loud(self) -> None:
        tasks = _load_tasks()
        assert any(
            _module_key(t) == "ansible.builtin.assert" and "dotfiles-runtime" in str(t)
            for t in tasks
        )

    def test_systemd_enable_gated_on_live_manager(self) -> None:
        enable = next(t for t in _load_tasks() if _module_key(t) == "ansible.builtin.systemd")
        params = enable["ansible.builtin.systemd"]
        assert isinstance(params, dict)
        assert params.get("scope") == "user"
        assert params.get("enabled") is True
        assert params.get("state") == "started"
        assert params.get("daemon_reload") is True
        when = str(enable.get("when", ""))
        assert "ansible_check_mode" in when
        assert "default(1)" in when

    def test_managerless_fallback_is_wants_symlink(self) -> None:
        link = next(
            t
            for t in _load_tasks()
            if _module_key(t) == "ansible.builtin.file"
            and isinstance(t.get("ansible.builtin.file"), dict)
            and t["ansible.builtin.file"].get("state") == "link"
            and "graphical-session.target.wants" in str(t)
        )
        params = link["ansible.builtin.file"]
        assert isinstance(params, dict)
        assert params.get("force") is True
        assert "default(1)" in str(link.get("when", ""))

    def test_runtime_executable_freshness_detection_is_read_only(self) -> None:
        """uv force-install rewrites the binary but never re-execs the job, so
        the role must detect a newer executable to restart the watcher."""
        task = next(
            t
            for t in _load_tasks()
            if "newer than the running watcher" in str(t["name"])
            and _module_key(t) == "ansible.builtin.shell"
        )
        assert task.get("changed_when") is False
        assert task.get("failed_when") is False
        when = str(task.get("when", ""))
        assert "ansible_check_mode" in when
        assert "runtime_clipboard_manager_probe" in when
        cmd = task["ansible.builtin.shell"]
        assert isinstance(cmd, dict)
        assert "ActiveEnterTimestamp" in cmd["cmd"]
        assert "stat -c %Y" in cmd["cmd"]

    def test_newer_executable_notifies_watcher_restart(self) -> None:
        """A newer installed binary must fire the restart handler (live only)."""
        task = next(
            t
            for t in _load_tasks()
            if str(t["name"]) == "Restart the watcher to load the newer runtime executable"
        )
        assert _module_key(task) == "ansible.builtin.debug"
        assert task.get("changed_when") is True
        assert task.get("notify") == "Restart dotfiles clipboard watcher"
        when = str(task.get("when", ""))
        assert "runtime_clipboard_executable_freshness" in when
        assert "newer" in when
        assert "ansible_check_mode" in when
        assert "runtime_clipboard_manager_probe" in when

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
                str(_ANSIBLE_DIR / "playbooks" / "runtime-clipboard.yaml"),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestHandlers:
    def test_unit_template_notifies_restart(self) -> None:
        template_task = next(
            t for t in _load_tasks() if _module_key(t) == "ansible.builtin.template"
        )
        assert template_task.get("notify") == "Restart dotfiles clipboard watcher"

    def test_handler_guarded_on_manager_and_not_check_mode(self) -> None:
        handler = _load_handlers()[0]
        when = handler.get("when")
        assert isinstance(when, list)
        joined = " ".join(str(condition) for condition in when)
        assert "ansible_check_mode" in joined
        assert "default(1)" in joined


class TestBootstrapWiring:
    def test_bootstrap_imports_playbook_after_daemon(self) -> None:
        bootstrap = (_ANSIBLE_DIR / "playbooks" / "bootstrap.yaml").read_text()
        assert "- import_playbook: runtime-clipboard.yaml" in bootstrap
        assert bootstrap.index("runtime-daemon.yaml") < bootstrap.index(
            "runtime-clipboard.yaml"
        )
