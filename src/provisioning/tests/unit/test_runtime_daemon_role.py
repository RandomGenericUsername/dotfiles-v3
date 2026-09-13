"""P5-1-1 role tests — the reactive daemon's --user unit (runtime_daemon role).

Structural YAML tests (no live systemd/user manager): the unit template is
rendered with StrictUndefined and asserted per-section (the Gate-2 StartLimit
placement bug class), tasks are pinned for privilege/check-mode/probe
semantics, and vars carry the approved supervision tuning.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import StrictUndefined
from jinja2 import Template as JinjaTemplate


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "P5-1-1 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLE_DIR = _ANSIBLE_DIR / "roles" / "runtime_daemon"

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
    "runtime_daemon_bin_dir": "/home/tester/.local/bin",
    "runtime_daemon_unit_name": "dotfiles-runtime-daemon.service",
    "runtime_daemon_restart_sec": 5,
    "runtime_daemon_start_limit_interval_sec": 60,
    "runtime_daemon_start_limit_burst": 3,
    "runtime_daemon_timeout_start_sec": 90,
}


def _load_tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLE_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return [dict(entry) for entry in data]


def _module_key(task: dict[str, object]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS:
            return key
    return None


def _render_unit() -> str:
    template = (_ROLE_DIR / "templates" / "dotfiles-runtime-daemon.service.j2").read_text()
    return JinjaTemplate(template, undefined=StrictUndefined).render(**_RENDER_VARS)


def _section(rendered: str, name: str) -> str:
    """Return the raw body of one INI section (exact `[Name]` line match —
    a naive `"["` split is fooled by section names inside comments)."""
    lines = rendered.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == f"[{name}]")
    except StopIteration:
        raise AssertionError(f"section [{name}] missing from rendered unit") from None

    def _is_header(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("[") and stripped.endswith("]")

    end = next(
        (i for i in range(start + 1, len(lines)) if _is_header(lines[i])),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end])


class TestRoleTree:
    def test_role_tree_exists(self) -> None:
        assert (_ROLE_DIR / "tasks" / "main.yml").is_file()
        assert (_ROLE_DIR / "templates" / "dotfiles-runtime-daemon.service.j2").is_file()
        assert (_ROLE_DIR / "vars" / "main.yml").is_file()

    def test_tasks_parse_to_named_list(self) -> None:
        for task in _load_tasks():
            assert isinstance(task.get("name"), str) and task["name"]

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped role: running as root would provision /root's session."""
        for task in _load_tasks():
            assert "become" not in task and "become_user" not in task, task["name"]


class TestUnitContent:
    def test_type_dbus_and_bus_name_in_service(self) -> None:
        service = _section(_render_unit(), "Service")
        assert "Type=dbus" in service
        assert "BusName=org.dotfiles.Events" in service

    def test_start_limits_in_unit_section_not_service(self) -> None:
        """Gate-2 regression: StartLimit* in [Service] is silently ignored."""
        unit = _section(_render_unit(), "Unit")
        service = _section(_render_unit(), "Service")
        assert "StartLimitIntervalSec=60" in unit
        assert "StartLimitBurst=3" in unit
        assert "StartLimit" not in service

    def test_restart_policy_in_service(self) -> None:
        """Name loss is a clean stop: Restart=always, never on-failure."""
        service = _section(_render_unit(), "Service")
        assert "Restart=always" in service
        assert "Restart=on-failure" not in service
        assert "RestartSec=5" in service
        assert "TimeoutStartSec=90" in service

    def test_exec_start_is_foreground_daemon_run(self) -> None:
        rendered = _render_unit()
        assert 'ExecStart="/home/tester/.local/bin/dotfiles-runtime" daemon run' in rendered
        assert "daemon start" not in rendered
        assert "daemon stop" not in rendered

    def test_session_binding(self) -> None:
        unit = _section(_render_unit(), "Unit")
        assert "Requires=dbus.socket" in unit
        assert "After=dbus.socket graphical-session.target" in unit
        install = _section(_render_unit(), "Install")
        assert "WantedBy=graphical-session.target" in install

    def test_renders_with_undefined_vars_rejected(self) -> None:
        """Every template variable resolves — no silent empty rendering."""
        template = (_ROLE_DIR / "templates" / "dotfiles-runtime-daemon.service.j2").read_text()
        assert "{{" in template  # actually templated, not a static file
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
        ), "a stat+assert must fail loud when the binary is absent"

    def test_systemd_enable_gated_on_live_manager(self) -> None:
        enable = next(t for t in _load_tasks() if _module_key(t) == "ansible.builtin.systemd")
        params = enable["ansible.builtin.systemd"]
        assert isinstance(params, dict)
        assert params.get("scope") == "user"
        assert params.get("enabled") is True
        assert params.get("daemon_reload") is True
        when = str(enable.get("when", ""))
        assert "ansible_check_mode" in when
        assert "default(1)" in when  # Gate-2: skipped-probe robustness

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
        assert params.get("state") == "link"
        assert params.get("force") is True  # Gate-2: re-provisioning converges
        assert "default(1)" in str(link.get("when", ""))

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
                str(_ANSIBLE_DIR / "playbooks" / "runtime-daemon.yaml"),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestVars:
    def test_supervision_tuning_matches_gate1(self) -> None:
        """Gate-1 rec 5: RestartSec 5, start-limit 60/3, TimeoutStartSec 90."""
        data = yaml.safe_load((_ROLE_DIR / "vars" / "main.yml").read_text())
        assert isinstance(data, dict)
        assert data["runtime_daemon_restart_sec"] == 5
        assert data["runtime_daemon_start_limit_interval_sec"] == 60
        assert data["runtime_daemon_start_limit_burst"] == 3
        assert data["runtime_daemon_timeout_start_sec"] == 90
        assert data["runtime_daemon_unit_name"] == "dotfiles-runtime-daemon.service"

    def test_no_dead_repo_root_var(self) -> None:
        """Gate-2: unreferenced derivations rot — the role must not define
        vars nothing consumes."""
        data = yaml.safe_load((_ROLE_DIR / "vars" / "main.yml").read_text())
        assert isinstance(data, dict)
        template = (_ROLE_DIR / "templates" / "dotfiles-runtime-daemon.service.j2").read_text()
        tasks_text = (_ROLE_DIR / "tasks" / "main.yml").read_text()
        for key in data:
            assert key in template or key in tasks_text, f"dead var: {key}"
