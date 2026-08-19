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
        "templates/sddm.conf.j2",
        "templates/config.toml.j2",
        "templates/regreet.toml.j2",
        "templates/regreet.css.j2",
        "templates/hypr-session.j2",
    )

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "display-manager.yaml").is_file(), (
            "missing playbooks/display-manager.yaml"
        )


class TestSddmPixieTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_installs_sddm_packages(self) -> None:
        """The role installs sddm + Qt6 deps for the SDDM+Pixie path."""
        tasks = _load_tasks()
        pkg = next((t for t in tasks if _module_key(t) == "ansible.builtin.package"), None)
        assert pkg is not None, "missing package install task"
        module = pkg.get("ansible.builtin.package")
        assert isinstance(module, dict)
        assert module["name"] == "{{ display_manager_sddm_packages }}"

    def test_fetches_pixie_theme(self) -> None:
        """The Pixie theme (Qt6) is fetched via git into the sddm themes dir."""
        tasks = _load_tasks()
        git = next((t for t in tasks if _module_key(t) == "ansible.builtin.git"), None)
        assert git is not None, "missing Pixie theme fetch (git) task"
        module = git.get("ansible.builtin.git")
        assert isinstance(module, dict)
        assert module["dest"] == "{{ display_manager_pixie_themedir }}"

    def test_renders_sddm_config(self) -> None:
        """The role renders /etc/sddm.conf.d with the Pixie theme + Wayland
        greeter."""
        tasks = _load_tasks()
        tmpl = next((t for t in tasks if "Render SDDM config" in str(t.get("name", ""))), None)
        assert tmpl is not None, "missing SDDM config render task"
        body = tmpl.get("ansible.builtin.template")
        assert isinstance(body, dict)
        assert body["dest"] == "{{ display_manager_sddm_conf }}"

    def test_sddm_tasks_gated_on_type(self) -> None:
        """The SDDM+Pixie install/config tasks must gate on
        display_manager_type == 'sddm-pixie'."""
        tasks = _load_tasks()
        sddm_tasks = [
            t
            for t in tasks
            if "SDDM" in str(t.get("name", ""))
            or "Pixie" in str(t.get("name", ""))
            or "sddm config" in str(t.get("name", "")).lower()
        ]
        assert sddm_tasks, "expected SDDM+Pixie tasks"
        for t in sddm_tasks:
            assert "display_manager_type == 'sddm-pixie'" in str(t.get("when", "")), (
                f"SDDM task {t.get('name')!r} must gate on display_manager_type == sddm-pixie"
            )

    def test_enables_sddm_used_to_derive_service(self) -> None:
        data = _vars()
        assert "sddm" in str(data["display_manager_enable_service"]), (
            "default enable_service must be sddm"
        )


class TestSddmConfigTemplate:
    def test_uses_pixie_theme_and_wayland_greeter(self) -> None:
        """The sddm.conf must enable the Pixie theme and a Wayland greeter (the
        no-X11-GPU-grab freeze fix)."""
        body = (_ROLES_DIR / "templates" / "sddm.conf.j2").read_text()
        assert "Current=pixie" in body
        assert "DisplayServer={{ display_manager_sddm_display_server }}" in body
        assert "wayland" in body.lower() or "QT_QPA_PLATFORM=wayland" in body


class TestSddmVars:
    def test_packages_include_sddm_and_qt6(self) -> None:
        data = _vars()
        pkgs = data["display_manager_sddm_packages"]
        assert "sddm" in pkgs
        assert "qt6-declarative" in pkgs
        assert "qt6-svg" in pkgs

    def test_pixie_repo_and_theme_dir(self) -> None:
        data = _vars()
        assert "github.com/xCaptaiN09/pixie-sddm" in str(data["display_manager_pixie_repo"])
        assert "pixie" in str(data["display_manager_pixie_themedir"])

    def test_default_type_is_sddm_pixie(self) -> None:
        data = _vars()
        assert data["display_manager_type"] == "sddm-pixie"

    def test_disables_greetd_and_lightdm(self) -> None:
        data = _vars()
        assert "greetd" in data["display_manager_disable_services"]
        assert "lightdm" in data["display_manager_disable_services"]


class TestGreetdFallbackRetained:
    def test_greetd_regreet_config_still_rendered(self) -> None:
        """The greetd+regreet templates remain so a user can fall back by
        setting display_manager_type == 'greetd-regreet'."""
        assert (_ROLES_DIR / "templates" / "config.toml.j2").is_file()
        for t in _load_tasks():
            if "greetd" in str(t.get("name", "")).lower():
                assert "display_manager_type == 'greetd-regreet'" in str(t.get("when", "")), (
                    f"greetd task {t.get('name')!r} must gate on greetd-regreet type"
                )

    def test_hypr_session_wrapper_retained(self) -> None:
        assert (_ROLES_DIR / "templates" / "hypr-session.j2").is_file()


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
