"""btop_config role tests (provision-btop-config, tasks 1.1-1.4).

Structural assertions run everywhere. The render test needs
``ansible-playbook`` on PATH and skips cleanly without it (same discipline as
the sibling kitty_config role test).
"""

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

# The theme file btop's setTheme must match by FILENAME. It is the cache
# artifact name (colors.btop-minimal.theme), NOT a csg-prefixed alias: an
# unmatched color_theme is not an error, it is a SILENT fallback to
# Default_theme (btop_theme.cpp:451-471).
_SELECTED_THEME = "colors.btop-minimal.theme"


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found walking up from the test file")


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "btop_config"
_TEMPLATE = _ROLES_DIR / "templates" / "btop.conf.j2"
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


def _file_tasks() -> list[dict[str, object]]:
    return [t for t in _load_tasks() if _module_key(t) == "ansible.builtin.file"]


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


class TestBtopConfigRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml", "templates/btop.conf.j2")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "btop-config.yaml").is_file(), (
            "missing playbooks/btop-config.yaml"
        )


class TestBtopConfigTasks:
    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert"
        )
        assert "install_dir is defined" in str(_module(first).get("that", ""))

    def test_both_spine_dirs_are_ensured(self) -> None:
        """D4: the seeder never mkdirs into the spine (skip_on_missing_parent),
        so the role must create config/btop AND config/btop/themes itself."""
        file_tasks = _file_tasks()
        paths = [
            str(_module(t).get("path"))
            for t in file_tasks
            if _module(t).get("state") == "directory"
        ]
        assert "{{ btop_config_spine_dir }}" in paths, (
            "config/btop must be ensured as a directory"
        )
        assert "{{ btop_config_spine_themes_dir }}" in paths, (
            "config/btop/themes must be ensured as a directory — without it the "
            "runtime's consumer pointers are skipped with a warning and the "
            "first swap drops all three themes"
        )

    def test_render_task_targets_final_btop_conf(self) -> None:
        task = _render_task()
        module = _module(task)
        assert str(module.get("dest")) == "{{ btop_config_spine_dir }}/btop.conf", (
            "render dest must be {{ btop_config_spine_dir }}/btop.conf (final, not .j2)"
        )
        assert str(module.get("src")) == "btop.conf.j2"

    def test_render_has_full_check_mode_support(self) -> None:
        assert _render_task().get("when") is None, (
            "render must not be --check-gated (template is check-safe)"
        )

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"btop_config must not use become (task {task.get('name')!r})"
            )

    def test_install_dir_is_never_defaulted(self) -> None:
        text = (_ROLES_DIR / "tasks" / "main.yml").read_text()
        assert "install_dir | default(" not in text


class TestBtopConfigVars:
    _REQUIRED_KEYS = {
        "btop_config_spine_dir",
        "btop_config_spine_themes_dir",
        "btop_config_xdg_config_home",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        assert self._REQUIRED_KEYS.issubset(set(_vars()))

    def test_spine_dir_is_trim_locked(self) -> None:
        assert str(_vars()["btop_config_spine_dir"]) == "{{ install_dir | trim }}/config/btop"

    def test_themes_dir_derives_from_spine_dir(self) -> None:
        """Trim lock: derived from btop_config_spine_dir — one seam read."""
        assert str(_vars()["btop_config_spine_themes_dir"]) == (
            "{{ btop_config_spine_dir }}/themes"
        )

    def test_xdg_config_home_mirrors_the_shared_derivation(self) -> None:
        """F4 lock: ansible_facts.env, never the deprecated top-level
        ansible_env fact; the exact shared derivation string (compare
        verify_xdg_config_home)."""
        value = str(_vars()["btop_config_xdg_config_home"])
        assert value == (
            "{{ ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME "
            "| default(ansible_facts.user_dir) + '/.config', true) }}"
        )
        assert "{{ ansible_env." not in value

    def test_no_install_dir_default_in_vars(self) -> None:
        assert "install_dir | default(" not in (_ROLES_DIR / "vars" / "main.yml").read_text()


class TestBtopConfigTemplate:
    def test_selects_the_generated_theme_by_filename(self) -> None:
        text = _TEMPLATE.read_text()
        assert f'color_theme = "{_SELECTED_THEME}"' in text, (
            "color_theme must name the theme FILE that the runtime places in "
            f"the spine's themes/ dir ({_SELECTED_THEME}) — btop matches "
            "color_theme against the themes it discovered in its own theme dir "
            "at startup, and an unmatched value silently falls back to "
            "Default_theme"
        )

    def test_save_config_on_exit_is_false(self) -> None:
        """Mandatory, not cosmetic: btop defaults it true and truncates +
        rewrites btop.conf on exit, which through the ~/.config/btop spine
        symlink would land the user's UI changes in version control."""
        assert "save_config_on_exit = false" in _TEMPLATE.read_text()

    def test_no_absolute_theme_path(self) -> None:
        """An absolute path outside btop's scanned theme dirs never loads —
        it resolves to nothing and falls back to Default_theme silently."""
        for line in _TEMPLATE.read_text().splitlines():
            if line.startswith("color_theme"):
                assert not line.split("=", 1)[1].strip().startswith(('"/', '"~', '"$')), (
                    f"color_theme must be a bare filename, not an absolute path: {line!r}"
                )

    def test_documents_the_save_config_on_exit_rationale(self) -> None:
        text = _TEMPLATE.read_text()
        assert "btop_config.cpp" in text and "btop_theme.cpp" in text, (
            "the template must carry the source citations that make "
            "save_config_on_exit = false a defended setting, not a stray flag"
        )

    def test_no_other_settings_are_set(self) -> None:
        """D6: every other btop setting stays at btop's own default, which
        operationally means ABSENT from the rendered file (btop applies its
        own defaults for keys it does not find)."""
        active = [
            line.split("=", 1)[0].strip()
            for line in _TEMPLATE.read_text().splitlines()
            if line and not line.startswith("#") and "=" in line
        ]
        assert sorted(active) == ["color_theme", "save_config_on_exit"]


class TestBtopConfigPlaybook:
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
                str(_PLAYBOOKS_DIR / "btop-config.yaml"),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_render_produces_the_expected_config_and_dirs(self) -> None:
        """End-to-end against a temp spine: both dirs exist, btop.conf carries
        the two pinned settings with no unresolved Jinja, and re-running is a
        no-op."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install = root / "install"
            (root / "home").mkdir()

            env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
            env.update(
                {
                    "HOME": str(root / "home"),
                    "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
                }
            )
            env.pop("XDG_CONFIG_HOME", None)

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        ansible_playbook,
                        str(_PLAYBOOKS_DIR / "btop-config.yaml"),
                        "-e",
                        f"install_dir={install}",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=180,
                )

            first = run()
            assert first.returncode == 0, first.stdout + first.stderr

            btop_dir = install / "config" / "btop"
            themes = btop_dir / "themes"
            assert themes.is_dir(), f"{themes} was never created (D4)"
            rendered = btop_dir / "btop.conf"
            assert rendered.is_file(), f"btop.conf was never rendered ({rendered})"
            text = rendered.read_text()
            assert "{{" not in text and "{%" not in text, (
                "rendered btop.conf must have no unresolved Jinja: " + text
            )
            assert f'color_theme = "{_SELECTED_THEME}"' in text
            assert "save_config_on_exit = false" in text

            second = run()
            assert second.returncode == 0, second.stdout + second.stderr
            assert "changed=0" in second.stdout, (
                "re-provisioning must be a no-op when nothing changed; recap:\n"
                + second.stdout
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
