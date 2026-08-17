from __future__ import annotations

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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "icons"
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


def _module_text(task: dict[str, object]) -> str:
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return module
    assert isinstance(module, dict)
    return " ".join(str(value) for value in module.values())


def _tasks_with_module(module: str) -> list[dict[str, object]]:
    return [task for task in _load_tasks() if _module_key(task) == module]


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


class TestIconsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "icons.yaml").is_file(), "missing playbooks/icons.yaml"


class TestIconsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert (role contract)"
        )
        that = str(_module(first).get("that", ""))
        assert "install_dir is defined" in that
        assert "install_dir | trim | length > 0" in that

    def test_render_task_invokes_itr_render_with_mappings_and_settings(self) -> None:
        """The role must actually INVOKE `itr render` against the deployed
        icons.yaml with the rendered itr settings — this is the wiring the
        chain previously lacked (CAP-5: ITR writes rendered SVGs)."""
        render = [
            task
            for task in _tasks_with_module("ansible.builtin.command")
            if "itr" in _module_text(task) and "render" in _module_text(task)
        ]
        assert len(render) == 1, (
            f"expected exactly one `itr render` command task; found {len(render)}"
        )
        argv = _module(render[0]).get("argv")
        assert isinstance(argv, list), "render task must use argv form (no shell splitting)"
        assert argv[0] == "itr"
        assert argv[1] == "render"
        assert "{{ icons_mappings_file }}" in [str(a) for a in argv]
        assert "--config" in [str(a) for a in argv]
        assert "{{ icons_itr_settings }}" in [str(a) for a in argv]

    def test_render_task_is_check_gated(self) -> None:
        """`itr render` is a command task — under --check ansible-core skips it,
        so it must be check-gated (dry-run must be dry)."""
        render = [
            task
            for task in _tasks_with_module("ansible.builtin.command")
            if "itr" in _module_text(task) and "render" in _module_text(task)
        ]
        assert len(render) == 1
        assert render[0].get("when") == "not ansible_check_mode"

    def test_render_task_prepends_bin_dir_to_path(self) -> None:
        render = [
            task
            for task in _tasks_with_module("ansible.builtin.command")
            if "itr" in _module_text(task) and "render" in _module_text(task)
        ][0]
        env = render.get("environment")
        assert isinstance(env, dict), "render task must set environment"
        assert "{{ icons_itr_bin_dir }}" in str(env.get("PATH", ""))

    def test_input_guards_exist_and_are_check_gated(self) -> None:
        """The four inputs (icons.yaml, templates dir, colors.yaml, settings)
        must be stat+assert guarded before the render (direct-run
        prerequisite), gated `when: not ansible_check_mode` (assert alone
        cannot check existence)."""
        stat_tasks = _tasks_with_module("ansible.builtin.stat")
        assert len(stat_tasks) >= 1, "expected at least one input stat task"
        for task in stat_tasks:
            assert task.get("when") == "not ansible_check_mode"
        assert_ = _tasks_with_module("ansible.builtin.assert")
        assert any("icons_input_check" in str(_module(t).get("that", "")) for t in assert_), (
            "expected an assert over icons_input_check"
        )

    def test_no_become_anywhere_in_role(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"icons role must not use become (task {task.get('name')!r})"
            )


class TestIconsVars:
    _REQUIRED_KEYS = {
        "icons_itr_bin_dir",
        "icons_mappings_file",
        "icons_itr_settings",
        "icons_inputs",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_paths_are_trim_locked(self) -> None:
        """All install-spine paths derive from {{ install_dir | trim }} — a
        literal absolute path would break the spine seam contract."""
        data = _vars()
        assert (
            str(data["icons_mappings_file"]) == "{{ install_dir | trim }}/icon-mappings/icons.yaml"
        )
        assert (
            str(data["icons_itr_settings"]) == "{{ install_dir | trim }}/config/itr/settings.toml"
        )
        assert "{{ icons_mappings_file }}" in [str(i) for i in data["icons_inputs"]]
        assert "{{ icons_itr_settings }}" in [str(i) for i in data["icons_inputs"]]
        for item in data["icons_inputs"]:
            assert "{{ install_dir | trim }}" in str(item) or "{{ icons_" in str(item), (
                "icons_inputs entry must derive from install_dir or a trim-locked icon var"
            )

    def test_bin_dir_defaults_under_home(self) -> None:
        data = _vars()
        assert str(data["icons_itr_bin_dir"]) == "{{ ansible_facts.env.HOME }}/.local/bin"


class TestIconsPlaybook:
    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                ansible_playbook,
                "--syntax-check",
                str(_PLAYBOOKS_DIR / "icons.yaml"),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_executes_and_renders_icons(self) -> None:
        """The real chain wiring: run icons.yaml against a temp spine that
        pre-populates the four inputs, assert itr render produces a rendered
        SVG into generated/icons. Requires itr on PATH."""
        itr = shutil.which("itr")
        if itr is None:
            pytest.skip("itr not installed; skipping execution test")
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install = root / "install"
            mappings = install / "icon-mappings"
            templates = (
                install / "icon-templates" / "status-bar" / "battery" / "battery-0" / "default"
            )
            palettes = install / "generated" / "palettes"
            settings_dir = install / "config" / "itr"
            icons = install / "generated" / "icons"
            for d in (mappings, templates, palettes, settings_dir, icons):
                d.mkdir(parents=True)

            (mappings / "icons.yaml").write_text(
                "battery:\n  color_mappings:\n    COLOR_ACCENT: color12\n"
                "  variants:\n"
                "    - name: battery-0\n"
                "      template: status-bar/battery/battery-0/default/icon.svg\n"
                "      output: battery-0.svg\n"
            )
            (templates / "icon.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                '<rect width="10" height="10" fill="{{ COLOR_ACCENT }}"/></svg>'
            )
            (palettes / "colors.yaml").write_text(
                "colors:\n  color12: '#ff0000'\nbackground:\n  hex: '#000000'\n"
                "foreground:\n  hex: '#ffffff'\ncursor:\n  hex: '#ffffff'\n"
            )
            (settings_dir / "settings.toml").write_text(
                f'[output]\noutput_dir = "{icons}"\nverbosity = 1\n\n'
                f'[templates]\ndir = "{install / "icon-templates"}"\n\n'
                f'[color_scheme]\npath = "{palettes / "colors.yaml"}"\n'
            )

            env = {
                k: v for k, v in __import__("os").environ.items() if not k.startswith("ANSIBLE_")
            }
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(_PLAYBOOKS_DIR / "icons.yaml"),
                    "-e",
                    f"install_dir={install}",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert (icons / "battery-0.svg").is_file(), (
                "icons.yaml must render battery-0.svg into generated/icons; "
                "stdout:\n" + result.stdout
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
