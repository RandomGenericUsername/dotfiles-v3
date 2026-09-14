from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "kitty_config"
_TEMPLATE = _ROLES_DIR / "templates" / "kitty.conf.j2"
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


def _render_task() -> dict[str, object]:
    matches = [t for t in _load_tasks() if _module_key(t) == "ansible.builtin.template"]
    assert len(matches) == 1, f"expected exactly one render task; found {len(matches)}"
    return matches[0]


def _local_conf_task() -> dict[str, object]:
    matches = [t for t in _load_tasks() if _module_key(t) == "ansible.builtin.copy"]
    assert len(matches) == 1, f"expected exactly one copy task; found {len(matches)}"
    return matches[0]


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


class TestKittyConfigRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml", "templates/kitty.conf.j2")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "kitty-config.yaml").is_file(), (
            "missing playbooks/kitty-config.yaml"
        )


class TestKittyConfigTasks:
    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert"
        )
        that = str(_module(first).get("that", ""))
        assert "install_dir is defined" in that

    def test_render_task_targets_final_kitty_conf(self) -> None:
        task = _render_task()
        module = _module(task)
        assert str(module.get("dest")) == "{{ kitty_config_spine_dir }}/kitty.conf", (
            "render dest must be {{ kitty_config_spine_dir }}/kitty.conf (final, not .j2)"
        )
        assert str(module.get("src")) == "kitty.conf.j2", (
            "render src must be the role-internal kitty.conf.j2 template"
        )

    def test_local_conf_copy_is_create_only(self) -> None:
        """local.conf must be created ONLY IF ABSENT (force: false) so a user's
        hand-written overrides survive re-provisioning."""
        task = _local_conf_task()
        module = _module(task)
        assert str(module.get("dest")) == "{{ kitty_config_spine_dir }}/local.conf"
        assert module.get("force") is False, (
            "the local.conf copy must set force: false (never clobber user edits)"
        )

    def test_render_has_full_check_mode_support(self) -> None:
        task = _render_task()
        assert task.get("when") is None, "render must not be --check-gated (template is check-safe)"

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"kitty_config must not use become (task {task.get('name')!r})"
            )

    def test_install_dir_is_never_defaulted(self) -> None:
        """F4 lock: the role must not invent a default install_dir — a missing
        seam fails loud on the first assert."""
        text = (_ROLES_DIR / "tasks" / "main.yml").read_text()
        assert "install_dir | default(" not in text


class TestKittyConfigVars:
    _REQUIRED_KEYS = {
        "kitty_config_spine_dir",
        "kitty_config_xdg_state_home",
        "kitty_config_state_current_dir",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_spine_dir_is_trim_locked(self) -> None:
        data = _vars()
        assert str(data["kitty_config_spine_dir"]) == "{{ install_dir | trim }}/config/kitty"

    def test_xdg_state_home_mirrors_zsh_derivation(self) -> None:
        """F4 lock: the state home derives EXACTLY like
        zsh_config_xdg_state_home — honors $XDG_STATE_HOME with the spec default
        ~/.local/state via ansible_facts.env (never the deprecated ansible_env)."""
        data = _vars()
        value = str(data["kitty_config_xdg_state_home"])
        assert value == (
            "{{ ansible_facts.env.XDG_STATE_HOME | default(ansible_facts.env.HOME "
            "| default(ansible_facts.user_dir) + '/.local/state', true) }}"
        ), "kitty_config_xdg_state_home must carry the exact shared derivation string"
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_state_current_dir_derived_from_state_home(self) -> None:
        data = _vars()
        value = str(data["kitty_config_state_current_dir"])
        assert value == "{{ kitty_config_xdg_state_home | trim }}/dotfiles/current", (
            "kitty_config_state_current_dir must derive from kitty_config_xdg_state_home "
            "(trim lock — one XDG read per role)"
        )
        assert "ansible_facts.env.XDG_STATE_HOME" not in value

    def test_no_install_dir_default_in_vars(self) -> None:
        text = (_ROLES_DIR / "vars" / "main.yml").read_text()
        assert "install_dir | default(" not in text


class TestKittyConfigTemplate:
    def test_template_contains_the_exact_managed_config(self) -> None:
        text = _TEMPLATE.read_text()
        assert "include {{ kitty_config_state_current_dir }}/colors.kitty" in text, (
            "the template must include the runtime palette at the absolute state path"
        )
        assert "include local.conf" in text, "the template must include the user local.conf"
        assert "auto_reload_config -1" in text, (
            "auto_reload_config must be -1 (kitty 0.48 types it as a float in "
            "seconds; a negative value disables it; the runtime reloader "
            "signals SIGUSR1)"
        )


class TestKittyConfigPlaybook:
    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                ansible_playbook,
                "--syntax-check",
                str(_PLAYBOOKS_DIR / "kitty-config.yaml"),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_renders_kitty_conf_with_absolute_include(self) -> None:
        """End-to-end render against a temp spine: the rendered kitty.conf
        includes the ABSOLUTE runtime palette path derived from the explicit
            XDG_STATE_HOME, carries auto_reload_config -1, and creates local.conf;
        re-running never clobbers a user-edited local.conf."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            install = root / "install"
            state = root / "state"
            home.mkdir()
            kitty_dir = install / "config" / "kitty"
            palette_dir = state / "dotfiles" / "current"
            palette_dir.mkdir(parents=True)
            (palette_dir / "colors.kitty").write_text("background #000000\n")

            env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
            env.update(
                {
                    "HOME": str(home),
                    "XDG_STATE_HOME": str(state),
                    "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
                }
            )
            env.pop("XDG_CONFIG_HOME", None)

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        ansible_playbook,
                        str(_PLAYBOOKS_DIR / "kitty-config.yaml"),
                        "-e",
                        f"install_dir={install}",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=120,
                )

            first = run()
            assert first.returncode == 0, first.stdout + first.stderr
            rendered = kitty_dir / "kitty.conf"
            assert rendered.is_file(), f"kitty.conf was never rendered ({rendered})"
            text = rendered.read_text()
            assert "{{" not in text and "{%" not in text, (
                "rendered kitty.conf must have no unresolved Jinja: " + text
            )
            expected_include = f"include {state}/dotfiles/current/colors.kitty"
            assert expected_include in text, (
                "rendered kitty.conf must include the absolute runtime palette path; "
                f"got: {text}"
            )
            assert "include local.conf" in text
            assert "auto_reload_config -1" in text
            local_conf = kitty_dir / "local.conf"
            assert local_conf.is_file(), "local.conf must be created on first provision"

            kitty_bin = shutil.which("kitty")
            if kitty_bin is not None:
                parsed = subprocess.run(
                    [
                        kitty_bin,
                        "+runpy",
                        f"from kitty.config import load_config; load_config({str(rendered)!r})",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=60,
                )
                combined = parsed.stdout + parsed.stderr
                assert parsed.returncode == 0, (
                    "kitty rejected the rendered kitty.conf: " + combined
                )
                assert "could not convert" not in combined, combined
                assert "Ignoring invalid config line" not in combined, combined

            local_conf.write_text("# user override\n")
            second = run()
            assert second.returncode == 0, second.stdout + second.stderr
            assert local_conf.read_text() == "# user override\n", (
                "re-provisioning must never clobber a user-edited local.conf"
            )
            assert "changed=0" in second.stdout, (
                "re-provisioning must be a no-op when nothing changed; recap:\n"
                + second.stdout
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
