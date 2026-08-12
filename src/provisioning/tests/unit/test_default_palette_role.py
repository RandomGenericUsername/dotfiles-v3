from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_assets_role.py``: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-12 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "default_palette"

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


def _module_key(task: dict[str, object]) -> str | None:
    """Return the module FQCN key for a task, or None for bare-key tasks."""
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, object]) -> dict[str, object]:
    """Return the module body as a dict for a task. String-valued modules
    (free-form `command`/`shell` tasks) yield an empty dict — use
    ``_module_text`` for those."""
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return {}
    assert isinstance(module, dict)
    return module


def _module_text(task: dict[str, object]) -> str:
    """Return the module body as text for free-form tasks (string-valued
    modules like `ansible.builtin.shell: command -v csg`)."""
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return module
    assert isinstance(module, dict)
    return " ".join(str(value) for value in module.values())


def _creates_value(task: dict[str, object]) -> object | None:
    """Return the ``creates`` value whether declared top-level, in args, or
    inside the module body."""
    direct = task.get("creates")
    if direct is not None:
        return direct
    for container in (task.get("args"), _module(task)):
        if isinstance(container, dict) and container.get("creates") is not None:
            return container.get("creates")
    return None


def _vars() -> Any:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _tasks_with_module(module: str) -> list[dict[str, object]]:
    return [task for task in _load_tasks() if _module_key(task) == module]


def _generate_task() -> dict[str, object]:
    matches = [
        task
        for task in _tasks_with_module("ansible.builtin.command")
        if "csg generate" in _module_text(task)
    ]
    assert len(matches) == 1, (
        f"expected exactly one `csg generate` command task; found {len(matches)}"
    )
    return matches[0]


class TestDefaultPaletteRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestDefaultPaletteTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Locks AC 8: the FIRST task is an `ansible.builtin.assert` requiring
        the install_dir seam extra-var — the identical verbatim copy of the
        2.5/2.6 assert (no aliasing into a var)."""
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert (AC 8)"
        )
        assert_ = _module(first)
        that = str(assert_.get("that", ""))
        assert "install_dir is defined" in that
        assert "install_dir | trim | length > 0" in that

    def test_palette_output_dir_ensured_via_file_directory(self) -> None:
        """AC 9 dir contract: a `file` `state: directory` task ensures
        `{{ default_palette_output_dir }}` == `{{ install_dir | trim
        }}/generated/palettes` — self-containment on a direct run + explicit
        ownership of the output dir (mirror of 2.6 AC 9 discipline)."""
        matches = [
            task
            for task in _tasks_with_module("ansible.builtin.file")
            if str(_module(task).get("path", "")) == "{{ default_palette_output_dir }}"
        ]
        assert matches, "no task ensuring {{ default_palette_output_dir }} found"
        for task in matches:
            assert _module(task)["state"] == "directory"

    def test_generate_task_targets_default_image_with_csg(self) -> None:
        """AC 2: the command task runs `csg generate` against
        `{{ default_palette_default_image }}` (single-quoted, shlex-safe)."""
        task = _generate_task()
        command = _module_text(task)
        assert command.startswith("csg generate")
        assert "'{{ default_palette_default_image }}'" in command

    def test_generate_task_format_flags_equal_default_palette_formats(self) -> None:
        """AC 2/5/9: the generate task's `-f` flags are DERIVED from
        `default_palette_formats` (load-bearing `join(' -f ')`), never
        hardcoded — so the var and the task cannot silently diverge. Render the
        free-form command's join expression against the var and assert each
        `-f <fmt>` appears with no extra format flags."""
        data = _vars()
        formats = [str(fmt) for fmt in data["default_palette_formats"]]
        assert formats, "default_palette_formats must not be empty"
        command = _module_text(_generate_task())
        join_expr = "{{ default_palette_formats | join(' -f ') }}"
        assert join_expr in command, (
            "generate task must derive its -f flags from default_palette_formats "
            "via join(' -f ') — never hardcoded (AC 2)"
        )
        rendered = command.replace(join_expr, " -f ".join(formats))
        rendered_flags = re.findall(r"-f\s+(\S+)", rendered)
        assert rendered_flags == formats, (
            "the rendered command's -f flags must equal default_palette_formats "
            "exactly, with no extra format flags"
        )

    def test_generate_task_env_contract(self) -> None:
        """AC 3/9/11 + container mode (product decision 2026-08-12): the
        generate task's `environment` sets
        COLORSCHEME__RUNTIME__MODE: "container",
        COLORSCHEME__CONTAINER__ENGINE: "{{ default_palette_container_engine }}"
        (resolved at runtime from override-or-detection, never a pinned var),
        COLORSCHEME__OUTPUT__OVERWRITE: "true" and
        COLORSCHEME__OUTPUT__DIRECTORY: "{{ default_palette_output_dir }}" and
        PATH starting with `{{ default_palette_bin_dir }}:`."""
        task = _generate_task()
        env = task.get("environment")
        assert isinstance(env, dict), "generate task must set environment"
        assert env.get("COLORSCHEME__RUNTIME__MODE") == "container", (
            "generate task must run csg in CONTAINER mode (product decision "
            "2026-08-12) — local mode would require host-side backends"
        )
        detected = "{{ default_palette_container_engine }}"
        assert env.get("COLORSCHEME__CONTAINER__ENGINE") == detected, (
            "generate task must pass the RESOLVED engine (override-or-detection, "
            "podman preferred, then docker) — never a hardcoded engine"
        )
        assert env.get("COLORSCHEME__OUTPUT__DIRECTORY") == "{{ default_palette_output_dir }}"
        assert env.get("COLORSCHEME__OUTPUT__OVERWRITE") == "true"
        assert str(env.get("PATH", "")).startswith("{{ default_palette_bin_dir }}:"), (
            "generate task must prepend default_palette_bin_dir to PATH (AC 11)"
        )

    def test_generate_task_carries_no_creates_and_is_check_gated(self) -> None:
        """AC 7 + dry-run-must-be-dry: the generate task carries NO `creates:`
        (FR-18 regenerate — a gate would freeze the palette forever) and is
        gated `when: not ansible_check_mode` (the command module would
        otherwise WRITE under --check)."""
        task = _generate_task()
        assert _creates_value(task) is None, (
            f"generate task {task.get('name')!r} must NOT carry creates: "
            "(AC 7 — FR-18 regenerate semantics)"
        )
        assert task.get("when") == "not ansible_check_mode", (
            "generate task must be gated when: not ansible_check_mode (dry-run must be dry)"
        )

    def test_csg_presence_fail_loud_guard(self) -> None:
        """AC 11 direct-run prerequisite: a `shell` `command -v csg` task
        (with `environment.PATH` prepending `{{ default_palette_bin_dir }}:`)
        registers a var, and an `assert` checks rc == 0 — the assert gated
        `when: not ansible_check_mode` (the read-only shell check may run under
        --check)."""
        shell_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.shell")
            if "command -v csg" in _module_text(task)
        ]
        assert shell_tasks, "no `command -v csg` presence check found"
        for task in shell_tasks:
            assert task.get("register"), "csg check must register its result"
            assert task.get("failed_when") is False, "csg check must not fail the play"
            env = task.get("environment")
            assert isinstance(env, dict), "csg check must set environment"
            assert str(env.get("PATH", "")).startswith("{{ default_palette_bin_dir }}:"), (
                "csg check must prepend default_palette_bin_dir to PATH (AC 11)"
            )

        assert_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if "default_palette_csg_check.rc == 0" in str(_module(task).get("that", ""))
        ]
        assert assert_tasks, "no assert locking default_palette_csg_check.rc == 0 found"
        for task in assert_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "csg assert must be gated when: not ansible_check_mode"
            )

    def test_default_png_asserted_via_stat_plus_assert(self) -> None:
        """AC 6: a `stat` on `{{ default_palette_default_image }}` registers a
        var, and an `assert` checks that registered var's `stat.exists` — both
        gated `when: not ansible_check_mode` (under --check the assets
        unarchive is skipped so the file is absent on a fresh target)."""
        stat_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if str(_module(task).get("path", "")) == "{{ default_palette_default_image }}"
        ]
        assert stat_tasks, "no stat task on {{ default_palette_default_image }} found"
        for task in stat_tasks:
            assert task.get("register"), "stat task must register its result"
            assert task.get("when") == "not ansible_check_mode", (
                "stat task must be gated when: not ansible_check_mode"
            )

        assert_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if str(_module(task).get("that", "")) == "default_palette_default_png.stat.exists"
        ]
        assert assert_tasks, (
            "no assert task checking default_palette_default_png.stat.exists "
            "found (an assert alone cannot check file existence — the stat is mandatory)"
        )
        for task in assert_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "default.png assert must be gated when: not ansible_check_mode"
            )

    def test_container_engine_detected_with_fail_loud_assert(self) -> None:
        """Container engine is a DOCUMENTED DEPENDENCY: a read-only probe
        detects podman then docker (register + changed_when/failed_when false),
        a set_fact resolves the engine from override-or-probe (trimmed), and a
        gated assert fails loud when neither is present — mirror of the
        cli_tools role detection."""
        probes = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.shell"
            and "command -v podman" in _module_text(task)
            and "command -v docker" in _module_text(task)
        ]
        assert probes, "expected a podman/docker detection probe"
        for task in probes:
            assert task.get("register") == "default_palette_engine_check"
            assert task.get("failed_when") is False
            assert task.get("changed_when") is False

        set_facts = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.set_fact"
            and "default_palette_container_engine" in str(task.get("ansible.builtin.set_fact", {}))
        ]
        assert set_facts, "expected a set_fact resolving default_palette_container_engine"

        asserts = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.assert"
            and "default_palette_container_engine" in str(_module(task).get("that", ""))
        ]
        assert asserts, "expected an assert on the resolved engine"
        for task in asserts:
            assert task.get("when") == "not ansible_check_mode", (
                "engine assert must be gated when: not ansible_check_mode"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context (AC 10): NO become/become_user anywhere
        — everything the role writes lives under the user's install_dir."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path-bearing reference derives from the trim-locked
        role vars (`{{ install_dir | trim }}`) — no literal absolute path is
        baked into any task's module body."""
        for task in _load_tasks():
            module_key = _module_key(task)
            assert module_key is not None
            raw = task.get(module_key)
            if isinstance(raw, dict):
                text = " ".join(str(value) for value in raw.values())
            else:
                text = str(raw)
            stripped = re.sub(r"\{\{.*?\}\}", "", text)
            tokens = [token for token in stripped.split() if token.startswith("/")]
            assert not tokens, (
                f"task {task.get('name')!r} hardcodes an absolute path: {tokens} (trim lock)"
            )


class TestDefaultPaletteVars:
    _REQUIRED_KEYS = {
        "default_palette_bin_dir",
        "default_palette_default_image",
        "default_palette_output_dir",
        "default_palette_formats",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_bin_dir_defaults_under_home(self) -> None:
        data = _vars()
        assert str(data["default_palette_bin_dir"]) == "{{ ansible_facts.env.HOME }}/.local/bin"

    def test_container_engine_not_pinned_in_vars(self) -> None:
        """podman/docker are DOCUMENTED DEPENDENCIES: the engine is resolved at
        runtime (override-or-detection, podman preferred, then docker, then fail
        loud) — the RESOLVED engine is never a vars value, and the override
        escape hatch defaults to empty (auto-detect)."""
        data = _vars()
        assert "default_palette_container_engine" not in data, (
            "the resolved engine must come from set_fact (override-or-detection), "
            "never pinned in vars"
        )
        assert data.get("default_palette_container_engine_override") == "", (
            "the override escape hatch must default to empty (auto-detect)"
        )

    def test_default_image_and_output_dir_are_trim_locked(self) -> None:
        """2.5 review lock: path-bearing vars consume the same trimmed
        `{{ install_dir | trim }}` value the fail-loud assert validates."""
        data = _vars()
        assert (
            str(data["default_palette_default_image"])
            == "{{ install_dir | trim }}/wallpapers/default.png"
        )
        assert (
            str(data["default_palette_output_dir"]) == "{{ install_dir | trim }}/generated/palettes"
        )

    def test_formats_are_the_contract_set(self) -> None:
        """Contract-driven format set (NOT the packaged json/sh defaults): conf
        → Hyprland colors.conf, css → Waybar colors.css, yaml → ITR spine chain
        colors.yaml."""
        data = _vars()
        assert [str(fmt) for fmt in data["default_palette_formats"]] == [
            "conf",
            "css",
            "yaml",
        ]

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        data = _vars()
        text = str(data)
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text


class TestDefaultPalettePlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "default-palette.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["default_palette"]
        assert "become" not in play, "default-palette playbook must not use become"
        assert "become_user" not in play, "default-palette playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the default-palette playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "default-palette playbook must not use group_by"
        assert "groups" not in play, "default-palette playbook must not group hosts"

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
                str(self._PATH),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
