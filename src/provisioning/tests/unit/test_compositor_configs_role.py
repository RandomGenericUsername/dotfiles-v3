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

    Mirrors ``test_assets_role.py`` / ``test_default_palette_role.py``: anchored
    on ``pyproject.toml`` so the sibling project's ``ansible/`` tree in a shared
    workspace is never matched.
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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "compositor_configs"

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
    modules)."""
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


def _copy_tasks() -> list[dict[str, object]]:
    return _tasks_with_module("ansible.builtin.copy")


def _skeleton_copy_task() -> dict[str, object]:
    """The single skeleton copy task: the copy carrying `force: false` (the
    AC 5 marker), looping over {{ compositor_configs_skeleton_copies }}."""
    matches = [
        task
        for task in _copy_tasks()
        if str(_module(task).get("force")) == "False"
        and "compositor_configs_skeleton_copies" in str(task.get("loop", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one skeleton copy task looping over "
        f"compositor_configs_skeleton_copies; found {len(matches)}"
    )
    return matches[0]


def _fragment_copy_task() -> dict[str, object]:
    """The single fragment copy task: the copy looping over
    {{ compositor_configs_fragment_copies }} (no force override — default
    force: true makes fragments the overwrite candidates)."""
    matches = [
        task
        for task in _copy_tasks()
        if "compositor_configs_fragment_copies" in str(task.get("loop", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one fragment copy task looping over "
        f"compositor_configs_fragment_copies; found {len(matches)}"
    )
    return matches[0]


class TestCompositorConfigsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestCompositorConfigsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Role contract: the FIRST task is an `ansible.builtin.assert` requiring
        the install_dir seam extra-var — the identical verbatim copy of the
        2.5/2.6/2.7 assert (no aliasing into a var)."""
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert (role contract)"
        )
        assert_ = _module(first)
        that = str(assert_.get("that", ""))
        assert "install_dir is defined" in that
        assert "install_dir | trim | length > 0" in that

    def test_three_skeleton_copy_dirs_with_force_false(self) -> None:
        """AC 2 + 5: the skeleton copy task loops over exactly the three
        compositor dirs (2.6 `assets_copies` pattern), each entry a `src`
        prefixed `{{ compositor_configs_repo_root }}/dotfiles/config/<dir>/`
        with trailing `/` (contents-into-dest), and the task sets
        `remote_src: true` + `force: false` — the marker that locks AC 5,
        without which a dev could silently fall back to copy's default
        force: true and clobber a user's edits."""
        task = _skeleton_copy_task()
        module = _module(task)
        assert module.get("remote_src") is True, (
            "skeleton copies must use remote_src: true (repo content is on the target)"
        )
        assert module.get("force") is False, (
            "skeleton copies must set force: false (AC 5 — never re-touch a placed skeleton)"
        )
        assert "compositor_configs_skeleton_copies" in str(task.get("loop", ""))

        data = _vars()
        copies = list(data["compositor_configs_skeleton_copies"])
        assert len(copies) == 3, (
            f"expected exactly 3 skeleton copies (hypr/hyprpaper/waybar); found {len(copies)}"
        )
        sources = sorted(str(c["source"]) for c in copies)
        expected = [
            "dotfiles/config/hypr/",
            "dotfiles/config/hyprpaper/",
            "dotfiles/config/waybar/",
        ]
        assert sources == expected, f"skeleton copy sources must be exactly {expected}"
        for copy_ in copies:
            assert str(copy_["source"]).endswith("/"), (
                "skeleton copy src must end with '/' for contents-into-dest semantics"
            )
            assert str(copy_["dest"]).startswith("{{ compositor_configs_xdg_config_home }}/"), (
                "skeleton copy dest must derive from compositor_configs_xdg_config_home"
            )

    def test_skeleton_copy_carries_no_creates(self) -> None:
        """AC 5/6 idempotency: `force: false` already guarantees no re-transfer
        when the file exists — a `creates:` would be redundant and confusing."""
        assert _creates_value(_skeleton_copy_task()) is None, (
            "skeleton copy task must not carry creates: "
            "(force: false already guarantees no re-transfer)"
        )

    def test_fragment_copy_pair_locks_the_rename(self) -> None:
        """AC 3 + 4: the fragment copy task loops over exactly the two fragment
        copies — colors.conf -> hypr/colors.conf and colors.gtk.css ->
        waybar/colors.css (the rename). The AC's literal `colors.css` source is
        a stale reference; locking source `colors.gtk.css` / dest basename
        `colors.css` is load-bearing."""
        task = _fragment_copy_task()
        assert "compositor_configs_fragment_copies" in str(task.get("loop", ""))
        data = _vars()
        fragments = list(data["compositor_configs_fragment_copies"])
        assert len(fragments) == 2, "fragment copy list must have exactly 2 entries"
        pairs = sorted(
            (str(f["source"]).rsplit("/", 1)[-1], str(f["dest"]).rsplit("/", 1)[-1])
            for f in fragments
        )
        assert pairs == [
            ("colors.conf", "colors.conf"),
            ("colors.gtk.css", "colors.css"),
        ], (
            "fragment copies must lock the colors.gtk.css -> colors.css rename "
            "(source colors.gtk.css, dest basename colors.css)"
        )

    def test_fragment_copies_carry_no_creates_and_are_check_gated(self) -> None:
        """AC 5/6 + dry-run-must-be-dry: the fragment copy task carries NO
        `creates:` (a gate would freeze a stale fragment and break the Phase 2
        overwrite contract) and is gated `when: not ansible_check_mode` (under
        --check the default_palette generate is skipped so the sources may be
        absent)."""
        task = _fragment_copy_task()
        assert _creates_value(task) is None, (
            f"fragment copy task {task.get('name')!r} must not carry creates: "
            "(AC 5 — fragments are the overwrite candidates)"
        )
        assert task.get("when") == "not ansible_check_mode", (
            "fragment copies must be gated when: not ansible_check_mode "
            "(sources may be absent under --check)"
        )

    def test_fragment_sources_stat_plus_assert_pair(self) -> None:
        """Fail-loud direct-run prerequisite: a `stat` loop over the fragment
        sources registers a var, and an `assert` checks the registered results
        — both gated `when: not ansible_check_mode` (under --check the
        default_palette generate is skipped so the files are absent on a fresh
        target; an assert alone cannot check file existence)."""
        stat_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if "compositor_configs_fragment_copies" in str(task.get("loop", ""))
        ]
        assert stat_tasks, "no fragment-source stat loop task found"
        for task in stat_tasks:
            assert task.get("register") == "compositor_configs_fragment_check"
            assert task.get("when") == "not ansible_check_mode", (
                "fragment-source stat must be gated when: not ansible_check_mode"
            )

        assert_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if "compositor_configs_fragment_check" in str(_module(task).get("that", ""))
        ]
        assert assert_tasks, (
            "no assert task checking compositor_configs_fragment_check found "
            "(an assert alone cannot check file existence — the stat is mandatory)"
        )
        for task in assert_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "fragment-source assert must be gated when: not ansible_check_mode"
            )

    def test_config_dirs_ensured_via_file_directory(self) -> None:
        """Direct-run self-containment: a `file` `state: directory` task re-ensures
        the three compositor config dirs (copy does NOT create dest parents for
        file sources; the filesystem role created them on the bootstrap chain)."""
        dir_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.file")
            if "compositor_configs_config_dirs" in str(task.get("loop", ""))
        ]
        assert dir_tasks, "no config-dir ensure task found"
        for task in dir_tasks:
            assert _module(task)["state"] == "directory"
            assert task.get("when") is None, (
                "dir ensure is check-safe natively — must NOT be --check-gated"
            )

    def test_invariant_documented_in_task_header(self) -> None:
        """AC 7: the task file header documents the load-bearing Phase 2
        invariant — skeletons never change; fragments are the overwrite target."""
        header = (_ROLES_DIR / "tasks" / "main.yml").read_text()
        assert "skeletons never change" in header, (
            "task header must document 'skeletons never change' (AC 7)"
        )
        assert "fragments are the Phase 2 overwrite target" in header, (
            "task header must document 'fragments are the Phase 2 overwrite target' (AC 7)"
        )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere —
        everything the role writes lives under the user's config dirs and
        install_dir."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path-bearing reference derives from the role vars
        (`{{ compositor_configs_repo_root }}`, `{{ install_dir | trim }}`,
        `{{ compositor_configs_xdg_config_home }}`) — no literal absolute path
        is baked into any task's module body."""
        safe_vars = (
            "compositor_configs_repo_root",
            "compositor_configs_xdg_config_home",
            "install_dir",
            "ansible_facts.env",
            "item.",
        )
        for task in _load_tasks():
            module_key = _module_key(task)
            assert module_key is not None
            raw = task.get(module_key)
            if isinstance(raw, str):
                raw = {module_key: raw}
            assert isinstance(raw, dict)
            for token in str(raw).split():
                if token.startswith("/") and not any(var in token for var in safe_vars):
                    raise AssertionError(
                        f"task {task.get('name')!r} hardcodes an absolute path: "
                        f"{token!r} (trim lock)"
                    )


class TestCompositorConfigsVars:
    _REQUIRED_KEYS = {
        "compositor_configs_repo_root",
        "compositor_configs_xdg_config_home",
        "compositor_configs_config_dirs",
        "compositor_configs_skeleton_copies",
        "compositor_configs_fragment_copies",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_repo_root_mirrors_assets_repo_root(self) -> None:
        data = _vars()
        assert str(data["compositor_configs_repo_root"]) == "{{ playbook_dir }}/../../../.."

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The copy destinations must resolve to the SAME location the filesystem
        role (2.5) created: honors $XDG_CONFIG_HOME with the spec default
        `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["compositor_configs_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_fragment_sources_are_trim_locked(self) -> None:
        """Trim lock: install-dir derived values consume the same validated
        `{{ install_dir | trim }}` value the fail-loud assert enforces."""
        data = _vars()
        for frag in data["compositor_configs_fragment_copies"]:
            assert str(frag["source"]).startswith("{{ install_dir | trim }}/"), (
                "fragment sources must consume {{ install_dir | trim }} (trim lock)"
            )

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        data = _vars()
        text = str(data)
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text


class TestCompositorConfigsPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "compositor-configs.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["compositor_configs"]
        assert "become" not in play, "compositor-configs playbook must not use become"
        assert "become_user" not in play, "compositor-configs playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the compositor-configs playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "compositor-configs playbook must not use group_by"
        assert "groups" not in play, "compositor-configs playbook must not group hosts"

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
