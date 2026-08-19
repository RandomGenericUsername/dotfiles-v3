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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "display_manager"
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


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


class TestDisplayManagerRoleTree:
    _REQUIRED_FILES = (
        "tasks/main.yml",
        "vars/main.yml",
        "templates/config.toml.j2",
        "templates/hypr-session.j2",
        "templates/hyprland-greeter.conf.j2",
    )

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "display-manager.yaml").is_file(), (
            "missing playbooks/display-manager.yaml"
        )


class TestDisplayManagerTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_installs_greetd_packages(self) -> None:
        """The role is self-contained: it installs greetd + the selected
        greeter (not a silent dependency on the packages role)."""
        tasks = _load_tasks()
        pkg = next((t for t in tasks if _module_key(t) == "ansible.builtin.package"), None)
        assert pkg is not None, "missing greetd package install task"
        module = pkg.get("ansible.builtin.package")
        assert isinstance(module, dict)
        assert module["name"] == "{{ display_manager_packages }}"

    def test_regreet_hyprland_host_config_rendered_only_for_regreet(self) -> None:
        """The regreet Hyprland host config (exec-once = regreet; hyprctl
        dispatch exit) is rendered ONLY when the greeter is regreet."""
        tasks = _load_tasks()
        host = next(
            (
                t
                for t in tasks
                if "Render the regreet Hyprland host config" in str(t.get("name", ""))
            ),
            None,
        )
        assert host is not None, "missing regreet Hyprland host config render task"
        assert "display_manager_greeter_type == 'regreet'" in str(host.get("when", "")), (
            "regreet host config render must gate on greeter_type == regreet"
        )

    def test_tuigreet_session_launcher_gated(self) -> None:
        """hypr-session (dbus-run-session -> Hyprland) is the tuigreet fallback
        path; gated on greeter_type == tuigreet."""
        tasks = _load_tasks()
        session = next(
            (t for t in tasks if "Render greetd session launcher" in str(t.get("name", ""))),
            None,
        )
        assert session is not None, "missing hypr-session render task"
        assert "display_manager_greeter_type == 'tuigreet'" in str(session.get("when", "")), (
            "hypr-session must gate on greeter_type == tuigreet"
        )

    def test_enables_greetd_service(self) -> None:
        tasks = _load_tasks()
        sysd = [t for t in tasks if _module_key(t) == "ansible.builtin.systemd"]
        enable = next((t for t in sysd if str(t.get("name", "")).startswith("Enable greetd")), None)
        assert enable is not None, "missing 'Enable greetd service' task"
        module = enable.get("ansible.builtin.systemd")
        assert isinstance(module, dict)
        assert module["name"] == "greetd"
        assert module["enabled"] is True

    def test_disables_x11_display_managers(self) -> None:
        """greetd (X11-free) must replace the X11 greeters that grab the GPU and
        freeze Hyprland — the role disables lightdm and sddm."""
        tasks = _load_tasks()
        sysd = [t for t in tasks if _module_key(t) == "ansible.builtin.systemd"]
        disable = next(
            (t for t in sysd if "Disable the superseded X11" in str(t.get("name", ""))), None
        )
        assert disable is not None, "missing 'Disable the superseded X11 display manager' task"
        assert "{{ display_manager_disable_services }}" in str(disable.get("loop", ""))

    def test_greetd_user_created(self) -> None:
        tasks = _load_tasks()
        user_task = next((t for t in tasks if _module_key(t) == "ansible.builtin.user"), None)
        assert user_task is not None, "missing greetd user creation task"
        module = user_task.get("ansible.builtin.user")
        assert isinstance(module, dict)
        assert module["name"] == "{{ display_manager_greeter_user }}"


class TestDisplayManagerTemplates:
    def test_hyprland_greeter_hosts_regreet(self) -> None:
        """The Hyprland host config used for regreet must run regreet at
        startup then exit Hyprland when the session launches."""
        body = (_ROLES_DIR / "templates" / "hyprland-greeter.conf.j2").read_text()
        assert "regreet" in body
        assert "hyprctl dispatch exit" in body

    def test_config_toml_branches_by_greeter(self) -> None:
        """config.toml must launch regreet (via Hyprland host) OR tuigreet
        (--cmd hypr-session) depending on display_manager_greeter_type."""
        body = (_ROLES_DIR / "templates" / "config.toml.j2").read_text()
        assert "display_manager_greeter_type" in body
        assert "start-hyprland" in body, "regreet path must use start-hyprland with the host config"
        assert "tuigreet" in body, "fallback path must use tuigreet"
        assert "/usr/local/bin/hypr-session" in body

    def test_hypr_session_wrapper_runs_dbus_wayland(self) -> None:
        """The session wrapper must launch Hyprland inside dbus-run-session —
        no X11, matching a clean Wayland login (the freeze fix)."""
        body = (_ROLES_DIR / "templates" / "hypr-session.j2").read_text()
        assert "dbus-run-session" in body
        assert "Hyprland" in body


class TestDisplayManagerVars:
    _REQUIRED_KEYS = {
        "display_manager_greeter_type",
        "display_manager_packages",
        "display_manager_packages_regreet",
        "display_manager_packages_tuigreet",
        "display_manager_greeter_user",
        "display_manager_greeter_shell",
        "display_manager_disable_services",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_regreet_defaults_on_arch(self) -> None:
        data = _vars()
        assert "Archlinux" in str(data["display_manager_greeter_type"]), (
            "greeter_type must default to regreet on Arch"
        )
        assert "regreet" in str(data["display_manager_greeter_type"])

    def test_package_sets_per_greeter(self) -> None:
        data = _vars()
        assert "greetd-regreet" in data["display_manager_packages_regreet"]
        assert "greetd-tuigreet" in data["display_manager_packages_tuigreet"]
        assert "greetd" in data["display_manager_packages_regreet"]
        assert "greetd" in data["display_manager_packages_tuigreet"]

    def test_disables_lightdm_and_sddm(self) -> None:
        data = _vars()
        assert "lightdm" in data["display_manager_disable_services"]
        assert "sddm" in data["display_manager_disable_services"]


class TestDisplayManagerPlaybook:
    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [ansible_playbook, "--syntax-check", str(_PLAYBOOKS_DIR / "display-manager.yaml")],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
