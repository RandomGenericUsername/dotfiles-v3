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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "wlogout_config"
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


class TestWlogoutConfigRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "wlogout-config.yaml").is_file(), (
            "missing playbooks/wlogout-config.yaml"
        )


class TestWlogoutConfigTasks:
    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert"
        that = str(_module(first).get("that", ""))
        assert "install_dir is defined" in that

    def test_render_task_targets_final_style_css(self) -> None:
        task = _render_task()
        module = _module(task)
        assert str(module.get("dest")) == "{{ wlogout_config_spine_dir }}/style.css", (
            "render dest must be the FINAL style.css (not the .tpl)"
        )
        assert "style.css.tpl" in str(module.get("src", "")), (
            "render src must be the style.css.tpl template"
        )

    def test_render_task_defines_all_template_vars(self) -> None:
        template = (_REPO_ROOT / "dotfiles" / "config" / "wlogout" / "style.css.tpl").read_text()
        import re

        template_vars = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
        task = _render_task()
        vars_block = task.get("vars")
        assert isinstance(vars_block, dict), "render task must define a vars block"
        missing = template_vars - set(vars_block.keys())
        assert not missing, f"render task does not define template vars: {sorted(missing)}"

    def test_render_uses_tunable_font(self) -> None:
        """The font must come from the tunable shell vars, never hardcoded."""
        task = _render_task()
        vars_block = task.get("vars")
        assert isinstance(vars_block, dict)
        assert "{{ shell.font_family }}" == vars_block.get("SYSTEM_FONT_FAMILY"), (
            "SYSTEM_FONT_FAMILY must derive from shell.font_family (tunable)"
        )
        assert "{{ shell.font_size_px }}" == vars_block.get("FONT_SIZE_PX"), (
            "FONT_SIZE_PX must derive from shell.font_size_px (tunable)"
        )

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False)


class TestWlogoutConfigTemplate:
    def test_template_uses_palette_color_names(self) -> None:
        """The template must consume the palette's REAL @color_00..@color_15
        names — the nonexistent @color16/@color10/@color7 are gone."""
        text = (_REPO_ROOT / "dotfiles" / "config" / "wlogout" / "style.css.tpl").read_text()
        for bad in ("@color16", "@color10", "@color7;"):
            assert bad not in text, f"template still uses nonexistent color {bad}"
        for good in ("@color_15", "@color_12", "@color_07"):
            assert good in text, f"template must use real palette color {good}"


class TestWlogoutConfigPlaybook:
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
                str(_PLAYBOOKS_DIR / "wlogout-config.yaml"),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_renders_style_css(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install = root / "install"
            wlogout_dir = install / "config" / "wlogout"
            (install / "config" / "ags").mkdir(parents=True)
            (install / "generated" / "icons").mkdir(parents=True)
            (install / "wallpapers").mkdir(parents=True)
            (install / "config" / "ags" / "colors.css").write_text("@define-color color_15 #fff;\n")
            (install / "generated" / "icons" / "lock.svg").write_text("")
            (install / "wallpapers" / "default.png").write_bytes(b"\x89PNG")

            env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(_PLAYBOOKS_DIR / "wlogout-config.yaml"),
                    "-e",
                    f"install_dir={install}",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            rendered = wlogout_dir / "style.css"
            assert rendered.is_file(), f"style.css was never rendered ({rendered})"
            text = rendered.read_text()
            assert "{{" not in text and "{%" not in text, "unresolved Jinja: " + text
            assert "@import" in text, "rendered style.css must import colors.css"
            assert "@color_15" in text, "rendered style.css must use real palette colors"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
