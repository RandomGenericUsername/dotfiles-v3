from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_cli_tools_role.py``: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-7 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "filesystem"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_MANIFEST_PATH = _REPO_ROOT / "dotfiles" / "provisioning" / "filesystem.yaml"

_XDG_BASE_NAMES = {"config", "state", "cache"}


def _rebase_filesystem_manifest(manifest_names: set[str]) -> set[str]:
    """Rebase the pre-config-in-spine flat manifest names onto the layout the
    filesystem role now creates (config-in-spine 2026-08-16). The manifest
    (Story 2.1) still carries the pre-refactor flat list: ``csg-templates``
    (dir) relocates to ``config/color-scheme-generator/templates`` with its
    parent, the ``weg-effects.yaml`` file node keeps its manifest name (the
    role's file-node partition still names it) while its parent ``config/weg``
    joins the spine, and the newly managed tool/compositor config subdirs under
    ``config/`` are added. This keeps the parity lock EXACT against the
    manifest without touching the (still-old) manifest."""
    names = set(manifest_names)
    names.discard("csg-templates")
    names.update(
        {
            "config",
            "config/color-scheme-generator",
            "config/color-scheme-generator/templates",
            "config/weg",
            "config/hypr",
            "config/hyprpaper",
            "config/waybar",
            "config/nvim",
            "config/starship",
            "config/wlogout",
            "config/zsh",
            "config/itr",
        }
    )
    return names


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


def _file_tasks() -> list[dict[str, object]]:
    """The `ansible.builtin.file` tasks that create the layout."""
    return [task for task in _load_tasks() if _module_key(task) == "ansible.builtin.file"]


def _module(task: dict[str, object]) -> dict[str, object]:
    module = task.get(_module_key(task) or "", {})
    assert isinstance(module, dict)
    return module


def _vars() -> Any:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


_XDG_HOME_VARS = {
    "{{ filesystem_xdg_config_home }}",
    "{{ filesystem_xdg_state_home }}",
    "{{ filesystem_xdg_cache_home }}",
}


def _is_xdg_base_dirs_task(task: dict[str, object]) -> bool:
    """True when the task's literal loop is EXACTLY the three XDG home vars —
    an extra loop item would silently create a dir absent from the manifest,
    so equality (not subset) is required."""
    loop = task.get("loop")
    return isinstance(loop, list) and {str(item) for item in loop} == _XDG_HOME_VARS


class TestFilesystemRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestFilesystemTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Locks AC6: the FIRST task is an `ansible.builtin.assert` requiring
        the install_dir seam extra-var, so an undefined spine root aborts with
        a friendly message before any dir task evaluates."""
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert (AC 6)"
        )
        assert_ = _module(first)
        that = str(assert_.get("that", ""))
        assert "install_dir is defined" in that
        assert "install_dir | trim | length > 0" in that

    def test_exactly_one_file_task_per_group(self) -> None:
        """AC 2/3/4 shape: one `ansible.builtin.file` task per node group
        (XDG base dirs, compositor dirs, spine dirs), each looping its var."""
        file_tasks = _file_tasks()
        assert len(file_tasks) == 3, (
            "expected exactly three ansible.builtin.file tasks "
            "(XDG base dirs, compositor dirs, spine dirs); "
            f"found {len(file_tasks)}"
        )

    def test_xdg_base_dirs_created_via_file_directory(self) -> None:
        """AC 2: one task loops the three XDG home vars with the file module,
        `state: directory` (idempotent create-if-missing)."""
        matches = [task for task in _file_tasks() if _is_xdg_base_dirs_task(task)]
        assert matches, "no task creating the XDG base dirs found"
        for task in matches:
            module = _module(task)
            assert module["state"] == "directory"
            assert module["path"] == "{{ item }}"

    def test_compositor_dirs_created_via_file_directory(self) -> None:
        """AC 3: one task loops `{{ filesystem_compositor_dirs }}` with the
        file module, `state: directory`."""
        matches = [
            task for task in _file_tasks() if task.get("loop") == "{{ filesystem_compositor_dirs }}"
        ]
        assert matches, "no task creating the compositor dirs found"
        for task in matches:
            module = _module(task)
            assert module["state"] == "directory"
            assert module["path"] == "{{ item }}"

    def test_spine_dirs_created_under_install_dir(self) -> None:
        """AC 4: one task loops `{{ filesystem_spine_dirs }}` with path
        `{{ install_dir }}/{{ item }}` and `state: directory` — the same path
        that auto-creates the <install_dir> root and the weg-effects.yaml
        parent."""
        matches = [
            task for task in _file_tasks() if task.get("loop") == "{{ filesystem_spine_dirs }}"
        ]
        assert matches, "no task creating the install spine dirs found"
        for task in matches:
            module = _module(task)
            assert module["state"] == "directory"
            assert module["path"] == "{{ install_dir | trim }}/{{ item }}"

    def test_no_task_creates_weg_effects_yaml(self) -> None:
        """AC 4 parent-only guarantee: the role never `state: touch`es
        weg-effects.yaml and no task path targets it — the file is the assets
        role's job (2.6) via `weg dump-effects`."""
        for task in _load_tasks():
            module = _module(task)
            assert module.get("state") != "touch", (
                f"task {task.get('name')!r} must never state: touch (parent-only)"
            )
            path = str(module.get("path", ""))
            assert not path.endswith("weg-effects.yaml"), (
                f"task {task.get('name')!r} must not target weg-effects.yaml "
                "(parent-only; the assets role emits the file)"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: everything lives under the user's
        home + user-owned install_dir — NO become (running as root would
        create ~-paths under /root/... and silently diverge)."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task


class TestFilesystemVars:
    _REQUIRED_KEYS = {
        "filesystem_xdg_config_home",
        "filesystem_xdg_state_home",
        "filesystem_xdg_cache_home",
        "filesystem_compositor_dirs",
        "filesystem_spine_dirs",
        "filesystem_file_nodes",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_parity_with_manifest(self) -> None:
        """AC 7 parity lock (resolves the Story 2.1 deferred item): the role's
        node map partitions the manifest's flat name list exactly — the XDG
        base dirs (config/state/cache) + install-spine dirs + file nodes
        union to the manifest entries, with disjoint base and file partitions.
        config-in-spine (2026-08-16): the manifest still carries the
        pre-refactor flat list, so the expected union is the manifest REBASED
        through the config-in-spine relocations (_rebase_filesystem_manifest).
        The manifest ``config`` name is DUAL-USE — the XDG base dir AND the
        config-in-spine root — so the non-XDG partition keeps the spine
        ``config`` root."""
        data = _vars()
        spine = set(str(item) for item in data["filesystem_spine_dirs"])
        files = set(str(item) for item in data["filesystem_file_nodes"])
        manifest_names = {item["name"] for item in _manifest_entries()}

        expected = _rebase_filesystem_manifest(manifest_names)

        assert spine | files | _XDG_BASE_NAMES == expected, (
            "spine dirs ∪ file nodes ∪ {config,state,cache} must equal the "
            "manifest entries rebased to the config-in-spine layout "
            "(single source of truth)"
        )
        assert spine | files == (expected - _XDG_BASE_NAMES) | {"config"}, (
            "the non-XDG manifest names must partition into spine dirs + file "
            "nodes, with the spine's config/ root standing in for the dual-use "
            "'config' name"
        )
        assert spine.isdisjoint(files), (
            "spine dirs and file nodes must be disjoint partitions — a file node "
            "leaked into the spine dir list (or vice versa) would still satisfy "
            "the set-equality checks above"
        )
        assert files == {"weg-effects.yaml"}, (
            "the file-node partition must be exactly weg-effects.yaml"
        )

    def test_spine_dirs_keep_generated_parent_and_leaves(self) -> None:
        """Parity guard: `generated` AND its nested leaves stay in the spine
        list (the file module auto-creates parents; optimizing to leaves-only
        would break the exact set-equality parity test)."""
        data = _vars()
        spine = set(str(item) for item in data["filesystem_spine_dirs"])
        assert "generated" in spine
        nested = {
            "generated/palettes",
            "generated/effects",
            "generated/icons",
            "generated/.weg-tmp",
        }
        assert nested.issubset(spine)

    def test_compositor_dirs_exactly_three_under_xdg_config_home(self) -> None:
        """AC 3: the compositor dirs are exactly hypr/hyprpaper/waybar under
        the XDG config home — nothing more."""
        data = _vars()
        compositor = [str(item) for item in data["filesystem_compositor_dirs"]]
        assert compositor == [
            "{{ filesystem_xdg_config_home }}/hypr",
            "{{ filesystem_xdg_config_home }}/hyprpaper",
            "{{ filesystem_xdg_config_home }}/waybar",
        ]

    def test_xdg_homes_honor_env_with_default(self) -> None:
        """AC 2 + F4 lock: each XDG home reads its $XDG_*_HOME env var with a
        default fallback — never a hardcoded `~/.config` literal."""
        data = _vars()
        for key in (
            "filesystem_xdg_config_home",
            "filesystem_xdg_state_home",
            "filesystem_xdg_cache_home",
        ):
            value = str(data[key])
            assert "ansible_facts.env.XDG_" in value, f"{key} must honor $XDG_*_HOME"
            assert "| default(" in value, f"{key} must carry a default fallback"
            assert "ansible_facts.env.HOME" in value, f"{key} default must derive from HOME"

    def test_xdg_homes_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated
        top-level ansible_env fact (INJECT_FACTS_AS_VARS injection that
        hard-breaks on ansible-core >= 2.24)."""
        data = _vars()
        for key in (
            "filesystem_xdg_config_home",
            "filesystem_xdg_state_home",
            "filesystem_xdg_cache_home",
        ):
            value = str(data[key])
            assert "ansible_facts.env." in value, f"{key} must use ansible_facts.env"
            assert "{{ ansible_env." not in value, (
                f"{key} must not use the deprecated ansible_env fact"
            )

    def test_file_nodes_exactly_weg_effects_yaml(self) -> None:
        data = _vars()
        assert [str(item) for item in data["filesystem_file_nodes"]] == ["weg-effects.yaml"]


class TestFilesystemPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "filesystem.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["filesystem"]
        assert "become" not in play, "filesystem playbook must not use become"

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
                "os_family=arch",
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
