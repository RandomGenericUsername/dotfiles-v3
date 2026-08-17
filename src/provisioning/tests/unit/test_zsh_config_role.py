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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "zsh_config"
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]


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


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


class TestZshConfigRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "zsh-config.yaml").is_file(), "missing playbooks/zsh-config.yaml"


class TestZshConfigTasks:
    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert"
        )
        that = str(_module(first).get("that", ""))
        assert "install_dir is defined" in that

    def test_render_task_targets_rendered_zshrc(self) -> None:
        """The render task must produce a FINAL .zshrc (no .j2 suffix) in the
        spine — this is the wiring the chain previously lacked."""
        task = _render_task()
        module = _module(task)
        assert str(module.get("dest")) == "{{ zsh_config_spine_dir }}/.zshrc", (
            "render dest must be {{ zsh_config_spine_dir }}/.zshrc (final, not .j2)"
        )
        assert ".zshrc.j2" in str(module.get("src", "")), (
            "render src must be the .zshrc.j2 template"
        )

    def test_render_task_defines_all_template_vars(self) -> None:
        """Every variable the .zshrc.j2 template consumes must be passed to the
        template module (a missing var would render as empty/broken output)."""
        template = (_REPO_ROOT / "dotfiles" / "config" / "zsh" / ".zshrc.j2").read_text()
        import re

        template_vars = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
        task = _render_task()
        vars_block = task.get("vars")
        assert isinstance(vars_block, dict), "render task must define a vars block"
        provided = set(vars_block.keys())
        missing = template_vars - provided
        assert not missing, f"render task does not define template vars: {sorted(missing)}"

    def test_render_has_full_check_mode_support(self) -> None:
        """The template module is check-safe natively — must NOT be --check-gated."""
        task = _render_task()
        assert task.get("when") is None, "render must not be --check-gated (template is check-safe)"

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"zsh_config must not use become (task {task.get('name')!r})"
            )


class TestZshConfigVars:
    _REQUIRED_KEYS = {"zsh_config_spine_dir", "zsh_config_template_root", "zsh_config_plugin_paths"}

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_spine_dir_is_trim_locked(self) -> None:
        data = _vars()
        assert str(data["zsh_config_spine_dir"]) == "{{ install_dir | trim }}/config/zsh"

    def test_plugin_paths_cover_both_distros(self) -> None:
        """The role must resolve plugin file paths for BOTH Arch and
        Debian-family (NFR-3 distro isolation: package names in group_vars,
        file paths in this role)."""
        data = _vars()
        arch = data.get("_zsh_config_arch")
        debian = data.get("_zsh_config_debian")
        assert isinstance(arch, dict) and isinstance(debian, dict), (
            "both _zsh_config_arch and _zsh_config_debian must be defined"
        )
        assert arch.keys() == debian.keys(), "both distros must resolve the same plugin set"
        for key in (
            "syntax_highlighting",
            "autosuggestions",
            "history_substring_search",
            "fzf_key_bindings",
            "fzf_completion",
        ):
            assert key in arch and key in debian, f"missing plugin path key {key}"
            assert str(arch[key]).startswith("/") and str(debian[key]).startswith("/")
        # Arch and Debian paths must actually differ (the whole point).
        assert arch != debian, "Arch and Debian plugin paths must differ"


class TestZshConfigPlaybook:
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
                str(_PLAYBOOKS_DIR / "zsh-config.yaml"),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_renders_zshrc_with_all_vars(self) -> None:
        """End-to-end render: run zsh-config.yaml against a temp spine, assert
        the rendered .zshrc resolves every template var (no raw {{...}} left)."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            install = root / "install"
            home.mkdir()
            zsh_dir = install / "config" / "zsh"
            (install / "config" / "starship").mkdir(parents=True)
            (install / "generated" / "palettes").mkdir(parents=True)
            (install / "config" / "starship" / "starship.toml").write_text("")
            (install / "generated" / "palettes" / "colors.sequences").write_text("")
            for d in (home / ".oh-my-zsh", home / ".pyenv"):
                d.mkdir(parents=True)

            env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
            env.update(
                {
                    "HOME": str(home),
                    "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
                }
            )
            env.pop("XDG_CONFIG_HOME", None)
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(_PLAYBOOKS_DIR / "zsh-config.yaml"),
                    "-e",
                    f"install_dir={install}",
                    "-e",
                    f"shell_oh_my_zsh_dir={home / '.oh-my-zsh'}",
                    "-e",
                    f"shell_pyenv_dir={home / '.pyenv'}",
                    "-e",
                    f"shell_nvm_dir={home / '.nvm'}",
                    "-e",
                    "shell_font_family=monospace",
                    "-e",
                    "shell_font_size_px=12",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            rendered = zsh_dir / ".zshrc"
            assert rendered.is_file(), f".zshrc was never rendered ({rendered})"
            text = rendered.read_text()
            assert "{{" not in text and "{%" not in text, (
                "rendered .zshrc must have no unresolved Jinja: " + text
            )
            assert "starship init zsh" in text, "rendered .zshrc must init starship"
            assert "colors.sequences" in text, "rendered .zshrc must load the color scheme"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
