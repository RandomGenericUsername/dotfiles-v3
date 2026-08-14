from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_settings_role.py`` / ``test_config_copies_role.py``:
    anchored on ``pyproject.toml`` so the sibling project's ``ansible/`` tree
    in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-3 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "verify"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_MANIFEST_PATH = _REPO_ROOT / "dotfiles" / "provisioning" / "config-copies.yaml"

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
    "block",
    "rescue",
    "always",
    "delegate_to",
    "run_once",
    "no_log",
    "include_tasks",
    "import_tasks",
    "include_role",
    "meta",
}

# Trim lock (review finding 2026-08-12): detect hardcoded absolute paths even
# when they are quoted (`"/home/user/x"`) or glued after a Jinja expression
# (`}}/home/user/generated`). A fragment is hardcoded unless a seam var
# (install_dir / verify_xdg_config_home / ansible_facts.env) appears within 80
# chars before it.
_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9._~/-]+)")


def _hardcoded_absolute_path(text: str, seam_vars: tuple[str, ...]) -> str | None:
    """Return the first absolute-path fragment in ``text`` not derived from a
    seam var, or None if every `/` path is seam-derived (trim lock)."""
    for match in _ABSOLUTE_PATH_RE.finditer(text):
        window = text[max(0, match.start() - 80) : match.start()]
        if any(var in window for var in seam_vars):
            continue
        return match.group(0)
    return None


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


def _assert_tasks() -> list[dict[str, object]]:
    return _tasks_with_module("ansible.builtin.assert")


def _stat_tasks() -> list[dict[str, object]]:
    return _tasks_with_module("ansible.builtin.stat")


def _shell_tasks() -> list[dict[str, object]]:
    return _tasks_with_module("ansible.builtin.shell")


def _command_tasks() -> list[dict[str, object]]:
    return _tasks_with_module("ansible.builtin.command")


def _sibling_vars(role: str) -> Any:
    data = yaml.safe_load((_ANSIBLE_DIR / "roles" / role / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


def _fact_gathering_assert_task() -> dict[str, object]:
    """The fail-loud fact-gathering guard: the FIRST task, an assert on
    ansible_facts.env.HOME with a gather_facts fail_msg."""
    tasks = _load_tasks()
    assert tasks, "tasks/main.yml must not be empty"
    first = tasks[0]
    assert _module_key(first) == "ansible.builtin.assert", (
        "the first task must be the fail-loud fact-gathering assert "
        "(role contract — vars derive from ansible_facts.env)"
    )
    return first


def _install_dir_assert_task() -> dict[str, object]:
    """The hardened install_dir seam assert: the SECOND task, with the five
    conditions from settings 2.11."""
    tasks = _load_tasks()
    assert len(tasks) >= 2, "tasks/main.yml must have at least two tasks"
    second = tasks[1]
    assert _module_key(second) == "ansible.builtin.assert", (
        "the second task must be the install_dir seam assert"
    )
    return second


def _system_binary_shell_task() -> dict[str, object]:
    matches = [
        task for task in _shell_tasks() if "verify_system_binaries" in str(task.get("loop", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one system-binary shell check; found {len(matches)}"
    )
    return matches[0]


def _cli_tool_shell_task() -> dict[str, object]:
    matches = [task for task in _shell_tasks() if "verify_cli_tools" in str(task.get("loop", ""))]
    assert len(matches) == 1, f"expected exactly one cli-tool shell check; found {len(matches)}"
    return matches[0]


def _shell_assert_task(register: str) -> dict[str, object]:
    matches = [task for task in _assert_tasks() if register in str(_module(task).get("that", ""))]
    assert len(matches) == 1, (
        f"expected exactly one shell-check assert consuming {register}; found {len(matches)}"
    )
    return matches[0]


def _stat_assert_pairs() -> list[tuple[dict[str, object], dict[str, object]]]:
    """Pair each stat loop with the assert consuming its register, in order."""
    registers = [str(task.get("register")) for task in _stat_tasks()]
    assert len(registers) == len(set(registers)), "stat registers must be unique"
    pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    for register in registers:
        assert_tasks = [
            task for task in _assert_tasks() if register in str(_module(task).get("that", ""))
        ]
        assert len(assert_tasks) == 1, (
            f"expected exactly one assert consuming {register}; found {len(assert_tasks)}"
        )
        stat = next(task for task in _stat_tasks() if task.get("register") == register)
        pairs.append((stat, assert_tasks[0]))
    return pairs


def _config_copy_stat_task() -> dict[str, object]:
    matches = [
        task for task in _stat_tasks() if "verify_config_copy_checks" == str(task.get("register"))
    ]
    assert len(matches) == 1, f"expected exactly one config-copy dest stat; found {len(matches)}"
    return matches[0]


def _config_copy_assert_task() -> dict[str, object]:
    matches = [
        task
        for task in _assert_tasks()
        if "verify_config_copy_checks" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, f"expected exactly one config-copy dest assert; found {len(matches)}"
    return matches[0]


def _itr_list_task() -> dict[str, object]:
    matches = [task for task in _command_tasks() if "itr list" in _module_text(task)]
    assert len(matches) == 1, f"expected exactly one itr list gate task; found {len(matches)}"
    return matches[0]


class TestVerifyRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestVerifyTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_fact_gathering_assert(self) -> None:
        """Role contract: the FIRST task is the fail-loud fact-gathering guard
        (mirror of config_copies) — resolves the 2.11 deferred flag: an
        aggregator that forgets gather_facts: true dies with a friendly
        message, not an opaque undefined-var traceback."""
        first = _fact_gathering_assert_task()
        module = _module(first)
        that = str(module.get("that", ""))
        assert "ansible_facts.env.HOME is defined" in that, (
            "the guard must assert ansible_facts.env.HOME is defined"
        )
        fail_msg = str(module.get("fail_msg", ""))
        assert "gather_facts" in fail_msg, (
            "the guard's fail_msg must name the gather_facts: true requirement"
        )

    def test_second_task_is_hardened_install_dir_assert(self) -> None:
        """Role contract: the SECOND task is the HARDENED five-condition
        install_dir seam assert from settings 2.11 (this role gates rendered
        files, so it inherits the hardened form that rejects None/relative/
        trailing-slash values before any stat evaluates)."""
        second = _install_dir_assert_task()
        module = _module(second)
        that = str(module.get("that", ""))
        for condition in (
            "install_dir is defined",
            "install_dir is not none",
            "install_dir is string",
            "install_dir | trim | length > 0",
            "regex_search('^/')",
        ):
            assert condition in that, f"hardened assert must include {condition!r}"
        assert second.get("when") is None, "the seam assert must be ungated"

    def test_system_binary_and_cli_tool_checks_use_shell_command_v(self) -> None:
        """Criterion 2 + 3: the binary/tool checks are `ansible.builtin.shell`
        running `command -v <item>` (a SHELL BUILTIN — free-form shell task),
        looping the vars, with changed_when: false / failed_when: false so a
        missing binary never fails the check task itself (the assert decides)."""
        for task in (_system_binary_shell_task(), _cli_tool_shell_task()):
            text = _module_text(task)
            assert "command -v" in text, (
                f"{task.get('name')!r} must run `command -v` (shell builtin → shell module)"
            )
            assert task.get("changed_when") is False
            assert task.get("failed_when") is False
            assert task.get("when") is None, (
                "shell checks are skipped under --check by ansible-core; the assert is "
                "the gated half"
            )

    def test_cli_tool_check_prepends_cli_bin_dir_to_path(self) -> None:
        """Criterion 3: the cli-tool check prepends {{ verify_cli_bin_dir }} to
        PATH so uv-installed tools resolve right after cli_tools installed
        them (mirror of default_palette) — without it the bootstrap chain would
        FALSE-FAIL when ~/.local/bin is not on the inherited PATH."""
        task = _cli_tool_shell_task()
        env = task.get("environment")
        assert isinstance(env, dict), "cli-tool check must set environment"
        assert "PATH" in env
        assert "verify_cli_bin_dir" in str(env["PATH"]), (
            "cli-tool check PATH must prepend verify_cli_bin_dir"
        )

    def test_shell_check_asserts_are_check_gated(self) -> None:
        """The assert halves of both shell checks must be gated
        `when: not ansible_check_mode` (a dry run must never fail on
        host-state preconditions)."""
        for register in ("verify_system_binary_checks", "verify_cli_tool_checks"):
            assert_task = _shell_assert_task(register)
            assert assert_task.get("when") == "not ansible_check_mode", (
                f"assert consuming {register} must be gated when: not ansible_check_mode"
            )

    def test_every_state_assert_is_check_gated(self) -> None:
        """Check-mode discipline: every ASSERT on state existence/isdir/rc is
        gated `when: not ansible_check_mode` so bootstrap.yaml --check stays
        clean on a partially-provisioned host (the real dotfiles-provision
        verify is the authoritative gate). Only the two leading seam asserts
        (fact + install_dir) are ungated."""
        for task in _load_tasks()[2:]:
            if _module_key(task) == "ansible.builtin.assert":
                assert task.get("when") == "not ansible_check_mode", (
                    f"state assert {task.get('name')!r} must be gated when: not "
                    "ansible_check_mode (bootstrap --check cleanliness)"
                )

    def test_settings_parse_gate_tasks_exist_and_are_check_gated(self) -> None:
        """AC 3: the three settings parse-gate command tasks (csg info / weg
        info / itr list) exist, are `ansible.builtin.command`, and are gated
        `when: not ansible_check_mode` (command tasks skip under --check)."""
        gate_names = {
            "Gate csg settings parse",
            "Gate weg settings parse",
            "Gate itr list against icons.yaml",
        }
        names = {str(task.get("name")) for task in _command_tasks()}
        assert gate_names.issubset(names), (
            f"expected the three parse-gate command tasks; found {names}"
        )
        for task in _command_tasks():
            assert task.get("when") == "not ansible_check_mode", (
                f"parse gate {task.get('name')!r} must be check-gated"
            )
        parse_asserts = [
            task
            for task in _assert_tasks()
            if "verify_csg_gate" in str(_module(task).get("that", ""))
            or "verify_weg_gate" in str(_module(task).get("that", ""))
            or "verify_itr_gate" in str(_module(task).get("that", ""))
        ]
        assert len(parse_asserts) == 1, (
            f"expected exactly one parse-gate assert; found {len(parse_asserts)}"
        )
        assert parse_asserts[0].get("when") == "not ansible_check_mode"

    def test_itr_list_task_pins_icons_yaml_not_defaults(self) -> None:
        """AC 3 / SPEC.md#51: the ITR gate is `itr list <install>/
        icon-mappings/icons.yaml --config <itr settings dest>` — NOT
        defaults.yaml (which lacks a `variants` field and is not listable)."""
        task = _itr_list_task()
        text = _module_text(task)
        assert "verify_itr_list_target" in text, (
            "itr gate must consume the verify_itr_list_target var (trim lock)"
        )
        assert "--config" in text
        assert "{{ verify_xdg_config_home }}/itr/settings.toml" in text, (
            "itr gate --config must reference the ITR settings dest"
        )
        env = task.get("environment")
        assert isinstance(env, dict) and "verify_cli_bin_dir" in str(env.get("PATH", "")), (
            "itr gate must prepend verify_cli_bin_dir to PATH"
        )
        target = str(_vars()["verify_itr_list_target"])
        assert "icon-mappings/icons.yaml" in target, (
            "verify_itr_list_target must pin icon-mappings/icons.yaml (SPEC.md#51)"
        )
        assert "defaults.yaml" not in target, (
            "verify_itr_list_target must NOT reference defaults.yaml (SPEC.md#51)"
        )

    def test_config_copies_dest_check_uses_follow_false_and_isdir(self) -> None:
        """Criterion 9 (runtime independence): the config-copy dest check is a
        `stat` with `follow: false` + an assert on `stat.isdir` — a symlink
        back into the repo reports islnk: true / isdir: false, so only REAL
        directories pass. Both tasks gated (mirror of config_copies)."""
        stat = _config_copy_stat_task()
        assert _module(stat).get("follow") is False, (
            "config-copy stat must pass follow: false (a symlink reports "
            "islnk: true / isdir: false)"
        )
        assert "{{ verify_config_copies_targets }}" in str(stat.get("loop", ""))
        assert stat.get("when") == "not ansible_check_mode"

        assert_task = _config_copy_assert_task()
        that = str(_module(assert_task).get("that", ""))
        assert "stat.isdir" in that, (
            "config-copy assert must check stat.isdir (real dirs, not symlinks)"
        )
        assert "verify_config_copies_targets | length" in that
        assert assert_task.get("when") == "not ansible_check_mode"

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere —
        everything the role checks lives under the user's config home and
        install_dir."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path-bearing reference derives from the role vars
        (`{{ verify_xdg_config_home }}`, `{{ install_dir | trim }}`,
        `ansible_facts.env`) — no literal absolute path is baked into any
        task's module body. Hardened scan catches quoted/glued literals."""
        seam_vars = (
            "verify_xdg_config_home",
            "verify_xdg_state_home",
            "verify_xdg_cache_home",
            "verify_xdg_dirs",
            "verify_install_spine_dirs",
            "verify_install_spine_files",
            "verify_settings_files",
            "verify_settings_spine_targets",
            "verify_itr_list_target",
            "install_dir",
            "ansible_facts.env",
        )
        for task in _load_tasks():
            hit = _hardcoded_absolute_path(str(task), seam_vars)
            assert hit is None, (
                f"task {task.get('name')!r} hardcodes an absolute path: {hit!r} (trim lock)"
            )


class TestVerifyVars:
    _REQUIRED_KEYS = {
        "verify_xdg_config_home",
        "verify_xdg_state_home",
        "verify_xdg_cache_home",
        "verify_xdg_dirs",
        "verify_install_spine_dirs",
        "verify_install_spine_files",
        "verify_system_binaries",
        "verify_cli_tools",
        "verify_cli_bin_dir",
        "verify_settings_files",
        "verify_settings_spine_targets",
        "verify_palette_files",
        "verify_compositor_config_dirs",
        "verify_compositor_skeleton_files",
        "verify_compositor_fragments",
        "verify_config_copies_targets",
        "verify_itr_list_target",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The check targets must resolve to the SAME location the filesystem
        role (2.5) created: honors $XDG_CONFIG_HOME with the spec default
        `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["verify_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_install_spine_dirs_parity_with_filesystem(self) -> None:
        """Parity lock: verify_install_spine_dirs mirrors filesystem_spine_dirs
        EXACTLY — if the spine changes, verify must change (a divergence would
        make verify check the wrong layout)."""
        data = _vars()
        spine = list(data["verify_install_spine_dirs"])
        filesystem_spine = list(_sibling_vars("filesystem")["filesystem_spine_dirs"])
        assert spine == filesystem_spine, (
            "verify_install_spine_dirs must be parity-EXACT with "
            "filesystem_spine_dirs (the test locks exact set equality)"
        )

    def test_settings_files_parity_with_settings_role(self) -> None:
        """Parity lock: verify_settings_files dests mirror the settings role's
        settings_files dests EXACTLY — verify must check the SAME rendered
        files settings renders."""
        data = _vars()
        verify_dests = [str(f["dest"]) for f in data["verify_settings_files"]]
        settings_dests = [str(f["dest"]) for f in _sibling_vars("settings")["settings_files"]]

        def relative_path(dest: str) -> str:
            """Strip the per-role home var prefix (settings_xdg_config_home vs
            verify_xdg_config_home resolve to the SAME location) and compare the
            relative dest path — the parity contract is the relative layout."""
            return dest.split("/", 1)[1]

        assert [relative_path(d) for d in verify_dests] == [
            relative_path(d) for d in settings_dests
        ], (
            "verify_settings_files dests must be parity-EXACT with the settings "
            "role's settings_files dests (same relative layout under the XDG "
            "config home)"
        )

    def test_settings_spine_targets_are_absolute_trim_derived(self) -> None:
        """Every spine target must derive from {{ install_dir | trim }} (trim
        lock) — never a relative path or a literal absolute path."""
        data = _vars()
        for target in data["verify_settings_spine_targets"]:
            value = str(target)
            assert value.startswith("{{ install_dir | trim }}/"), (
                f"settings spine target {value!r} must derive from {{{{ install_dir | trim }}}}"
            )

    def test_config_copies_targets_parity_with_manifest(self) -> None:
        """Parity lock: verify_config_copies_targets mirrors the config-copies
        manifest entries EXACTLY (criterion 9 — the real-dir check covers one
        per manifest entry)."""
        data = _vars()
        role_targets = [str(item) for item in data["verify_config_copies_targets"]]
        manifest_targets = [str(e["target"]) for e in _manifest_entries()]
        assert role_targets == manifest_targets, (
            "verify_config_copies_targets must be parity-EXACT with "
            "dotfiles/provisioning/config-copies.yaml entries"
        )

    def test_palette_files_match_chain_formats(self) -> None:
        """Criterion 6: the palette files check is exactly the three chain
        formats (conf/gtk.css/yaml) — NOT json/sh (no Phase 1 consumer)."""
        data = _vars()
        assert [str(f) for f in data["verify_palette_files"]] == [
            "colors.conf",
            "colors.yaml",
            "colors.gtk.css",
        ]
        palette_formats = _sibling_vars("default_palette")["default_palette_formats"]
        assert {str(f"colors.{fmt}") for fmt in palette_formats} == {
            str(f) for f in data["verify_palette_files"]
        }, "verify_palette_files must match default_palette_formats (conf/gtk.css/yaml) as a set"

    def test_cli_tools_are_csg_weg_itr(self) -> None:
        data = _vars()
        assert [str(c) for c in data["verify_cli_tools"]] == ["csg", "weg", "itr"]

    def test_system_binaries_are_compositors(self) -> None:
        data = _vars()
        assert [str(b) for b in data["verify_system_binaries"]] == [
            "hyprland",
            "hyprpaper",
            "waybar",
        ]

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        text = str(_vars())
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock on vars: every path derives from install_dir /
        verify_xdg_config_home / ansible_facts.env — no literal absolute path
        is baked into vars/main.yml."""
        seam_vars = (
            "verify_xdg_config_home",
            "verify_xdg_state_home",
            "verify_xdg_cache_home",
            "verify_xdg_dirs",
            "verify_install_spine_dirs",
            "verify_install_spine_files",
            "verify_settings_files",
            "verify_settings_spine_targets",
            "verify_itr_list_target",
            "install_dir",
            "ansible_facts.env",
        )
        hit = _hardcoded_absolute_path(str(_vars()), seam_vars)
        assert hit is None, f"vars/main.yml hardcodes an absolute path: {hit!r} (trim lock)"


class TestVerifyPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "verify.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["verify"]
        assert "become" not in play, "verify playbook must not use become"
        assert "become_user" not in play, "verify playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the verify playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "verify playbook must not use group_by"
        assert "groups" not in play, "verify playbook must not group hosts"

    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = _test_env(ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"))
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
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestVerifyRuntime:
    _PATH = _ANSIBLE_DIR / "playbooks" / "verify.yaml"

    def test_verify_passes_on_a_provisioned_machine(self) -> None:
        """Regression guard (2.10/2.11 discipline): structural tests alone
        cannot prove verify isn't vacuous. Build a minimal provisioned
        "machine" (spine, assets, palette, settings + spine targets, compositor
        configs, config-copy real dirs, stub binaries) and assert the real
        verify.yaml run passes; then DELETE one criterion element and assert
        the re-run FAILS loudly (negative lock: verify is not vacuous)."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()

            bin_dir = _write_stub_binaries(home)
            _build_provisioned_layout(home, xdg, install)

            env = _test_env(
                HOME=str(home),
                XDG_CONFIG_HOME=str(xdg),
                ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"),
                PATH=f"{bin_dir}:{os.environ.get('PATH', '')}",
            )

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        ansible_playbook,
                        str(self._PATH),
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
            assert "failed=0" in first.stdout, (
                "verify must report zero failed tasks on a provisioned machine; "
                "recap:\n" + first.stdout
            )

            (install / "generated" / "palettes" / "colors.conf").unlink()
            second = run()
            assert second.returncode != 0, (
                "verify must FAIL after a criterion element is removed "
                "(negative lock — the gate is not vacuous); recap:\n" + second.stdout
            )

    def test_verify_fails_when_not_provisioned(self) -> None:
        """Hardening: machine, not repo. Run verify.yaml against a bare temp
        HOME/XDG/install (no spine, no configs, no binaries) and assert the run
        FAILS — the gate cannot go green on an unprovisioned machine even when
        the repo checkout exists."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            install = Path(tmp) / "install"
            home.mkdir()
            xdg.mkdir()
            install.mkdir()

            env = _test_env(
                HOME=str(home),
                XDG_CONFIG_HOME=str(xdg),
                ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"),
            )
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(self._PATH),
                    "-e",
                    f"install_dir={install}",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode != 0, (
                "verify must FAIL on an unprovisioned machine (hardening: "
                "machine, not repo); recap:\n" + result.stdout
            )


def _test_env(**overrides: str) -> dict[str, str]:
    """A scrubbed env for playbook subprocesses (review finding 2026-08-12):
    drop ambient ANSIBLE_* vars — a developer's ANSIBLE_INVENTORY /
    ANSIBLE_ROLES_PATH / etc. would otherwise silently override ansible.cfg —
    then apply the explicit HOME/XDG_CONFIG_HOME/ANSIBLE_CONFIG."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
    env.update(overrides)
    return env


def _write_stub_binaries(home: Path) -> Path:
    """Stub hyprland/hyprpaper/waybar/csg/weg/itr as executable `#!/bin/sh`
    scripts in home/.local/bin that exit 0 — so `command -v` + the csg/weg/itr
    parse gates pass without installing real CLIs."""
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("hyprland", "hyprpaper", "waybar", "csg", "weg", "itr"):
        stub = bin_dir / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    return bin_dir


def _build_provisioned_layout(home: Path, xdg: Path, install: Path) -> None:
    """Create the minimal provisioned "machine" verify.yaml asserts against:
    install spine + weg-effects.yaml, the five asset outcomes, the three
    palette files, the three rendered settings.toml files pointing at the
    spine targets, compositor configs + skeletons + fragments, the XDG
    state/cache homes, and the four config-copy targets as REAL directories."""
    for rel in (
        "wallpapers",
        "icon-templates",
        "icon-mappings",
        "csg-templates",
        "generated",
        "generated/palettes",
        "generated/effects",
        "generated/icons",
        "generated/.weg-tmp",
    ):
        (install / rel).mkdir(parents=True, exist_ok=True)
    (install / "weg-effects.yaml").write_text("{}\n")

    (home / ".local" / "state").mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)

    (install / "wallpapers" / "default.png").write_bytes(b"\x89PNG")
    (install / "icon-mappings" / "icons.yaml").write_text("variants: []\n")
    for name in ("colors.conf", "colors.yaml", "colors.gtk.css"):
        (install / "generated" / "palettes" / name).write_text("")

    (xdg / "color-scheme-generator").mkdir(parents=True, exist_ok=True)
    (xdg / "weg").mkdir(parents=True, exist_ok=True)
    (xdg / "itr").mkdir(parents=True, exist_ok=True)
    (xdg / "color-scheme-generator" / "settings.toml").write_text(
        f'[output]\ndirectory = "{install}/generated/palettes"\n'
        'overwrite = false\ndefault_formats = ["conf", "gtk.css", "yaml"]\n'
    )
    (xdg / "weg" / "settings.toml").write_text(
        f'[output]\ndirectory = "{install}/generated/effects"\n'
        f'[processing]\ntemp_dir = "{install}/generated/.weg-tmp"\n'
        "[execution]\nstrict = false\n"
    )
    (xdg / "itr" / "settings.toml").write_text(
        f'[output]\noutput_dir = "{install}/generated/icons"\n'
        f'[templates]\ndir = "{install}/icon-templates"\n'
        f'[color_scheme]\npath = "{install}/generated/palettes/colors.yaml"\n'
    )

    for name in ("hypr", "hyprpaper", "waybar"):
        (xdg / name).mkdir(parents=True, exist_ok=True)
    (xdg / "hypr" / "hyprland.conf").write_text("")
    (xdg / "hyprpaper" / "hyprpaper.conf").write_text("")
    (xdg / "waybar" / "config").write_text("")
    (xdg / "waybar" / "style.css").write_text("")
    (xdg / "hypr" / "colors.conf").write_text("")
    (xdg / "waybar" / "colors.css").write_text("")

    for target in ("nvim", "starship", "wlogout", "zsh"):
        (xdg / target).mkdir(parents=True, exist_ok=True)
