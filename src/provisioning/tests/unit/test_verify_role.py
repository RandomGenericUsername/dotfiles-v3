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
    modules). For argv-form `command` tasks, join the argv list with spaces so
    `command -v` / `itr list ...` style assertions read naturally."""
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return module
    assert isinstance(module, dict)
    if "argv" in module:
        return " ".join(str(part) for part in module["argv"])
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


def _managed_link_stat_task() -> dict[str, object]:
    """The layer-1 stat: `stat` with `follow: false` over
    {{ verify_managed_link_dirs }}, registering verify_managed_link_checks."""
    matches = [
        task for task in _stat_tasks() if "verify_managed_link_checks" == str(task.get("register"))
    ]
    assert len(matches) == 1, f"expected exactly one managed-link stat; found {len(matches)}"
    return matches[0]


def _managed_link_islnk_assert_task() -> dict[str, object]:
    """The layer-1 assert: consumes verify_managed_link_checks checking
    stat.islnk for every managed dir."""
    matches = [
        task
        for task in _assert_tasks()
        if "verify_managed_link_checks" in str(_module(task).get("that", ""))
        and "stat.islnk" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one islnk assert over verify_managed_link_checks; found {len(matches)}"
    )
    return matches[0]


def _managed_link_target_assert_task() -> dict[str, object]:
    """The layer-2 assert: consumes verify_managed_link_checks asserting no
    broken/wrong lnk_target (every link resolves into the spine)."""
    matches = [
        task
        for task in _assert_tasks()
        if "verify_managed_link_checks" in str(_module(task).get("that", ""))
        and "stat.lnk_target" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one lnk_target assert over verify_managed_link_checks; "
        f"found {len(matches)}"
    )
    return matches[0]


def _managed_link_resolve_stat_task() -> dict[str, object]:
    """The layer-3 stat: `stat` with `follow: true` over
    {{ verify_managed_link_dirs }}, registering verify_managed_link_resolve_checks."""
    matches = [
        task
        for task in _stat_tasks()
        if "verify_managed_link_resolve_checks" == str(task.get("register"))
    ]
    assert len(matches) == 1, (
        f"expected exactly one managed-link resolve stat; found {len(matches)}"
    )
    return matches[0]


def _managed_link_resolve_assert_task() -> dict[str, object]:
    """The layer-3 assert: consumes verify_managed_link_resolve_checks asserting
    stat.isdir for every managed dir (the link resolves to a real dir)."""
    matches = [
        task
        for task in _assert_tasks()
        if "verify_managed_link_resolve_checks" in str(_module(task).get("that", ""))
        and "stat.isdir" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one managed-link resolve assert; found {len(matches)}"
    )
    return matches[0]


def _config_copy_follow_stat_task() -> dict[str, object]:
    """The layer-3 stat: `stat` with `follow: true` over
    {{ verify_config_copies_targets }}, registering verify_config_copy_checks."""
    matches = [
        task for task in _stat_tasks() if "verify_config_copy_checks" == str(task.get("register"))
    ]
    assert len(matches) == 1, f"expected exactly one config-copy follow stat; found {len(matches)}"
    return matches[0]


def _config_copy_follow_assert_task() -> dict[str, object]:
    """The layer-3 assert: consumes verify_config_copy_checks checking
    stat.isdir for every config-copy target."""
    matches = [
        task
        for task in _assert_tasks()
        if "verify_config_copy_checks" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one config-copy resolve assert; found {len(matches)}"
    )
    return matches[0]


def _config_content_stat_task() -> dict[str, object]:
    """The layer-4 stat: `stat` with `follow: true` over
    {{ verify_config_copy_content }}, registering
    verify_config_copy_content_checks."""
    matches = [
        task
        for task in _stat_tasks()
        if "verify_config_copy_content_checks" == str(task.get("register"))
    ]
    assert len(matches) == 1, f"expected exactly one config-content stat; found {len(matches)}"
    return matches[0]


def _config_content_assert_task() -> dict[str, object]:
    """The layer-4 assert: consumes verify_config_copy_content_checks checking
    stat.isreg through the symlink."""
    matches = [
        task
        for task in _assert_tasks()
        if "verify_config_copy_content_checks" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, f"expected exactly one config-content assert; found {len(matches)}"
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
            "regex_search('/$') is none",
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
        verify is the authoritative gate). The leading CONFIG seam asserts
        (fact, install_dir, list-not-empty, name-safety) are ungated — they
        check variables/configuration, not host state, and must fail under
        --check too."""
        ungated_seam_asserts = {
            "Assert fact-gathering provided HOME",
            "Assert install_dir seam is provided",
            "Assert verify list vars are not empty",
            "Assert binary and tool names are safe identifiers",
        }
        for task in _load_tasks():
            if task.get("name") in ungated_seam_asserts:
                continue
            if _module_key(task) == "ansible.builtin.assert":
                assert task.get("when") == "not ansible_check_mode", (
                    f"state assert {task.get('name')!r} must be gated when: not "
                    "ansible_check_mode (bootstrap --check cleanliness)"
                )

    def test_criterion_6_accepts_generated_or_current(self) -> None:
        """Criterion 6 (Story 1.12 AC 4): the palette gate stats BOTH candidate
        locations per file — generated/palettes/<file> (pre-runtime) AND
        {{ verify_state_current_dir }}/<file> (post-runtime) — and one
        check-gated assert accepts the OR per file. The current-dir stat sets
        `follow: true` EXPLICITLY: the installed ansible-core's stat module
        defaults follow to FALSE (verified against the argument spec — the
        story's Dev Notes assumed otherwise), so only an explicit follow
        resolves a healthy runtime symlink chain
        (current/colors.conf -> cache/palettes/<ph>/colors.conf) to isreg,
        while a DANGLING runtime symlink correctly fails (filesystem is
        authority, NFR-3)."""
        gen = next(
            (t for t in _stat_tasks() if t.get("register") == "verify_palette_checks"),
            None,
        )
        cur = next(
            (t for t in _stat_tasks() if t.get("register") == "verify_palette_current_checks"),
            None,
        )
        assert gen is not None, "missing the generated/palettes stat loop (criterion 6)"
        assert cur is not None, (
            "missing the runtime current-dir stat loop (criterion 6 OR-leg, Story 1.12)"
        )
        assert "generated/palettes" in str(_module(gen).get("path", ""))
        assert "{{ verify_palette_files }}" in str(gen.get("loop", ""))
        assert "{{ verify_state_current_dir }}" in str(_module(cur).get("path", "")), (
            "the OR-leg must stat {{ verify_state_current_dir }}/<file>"
        )
        assert "{{ verify_palette_files }}" in str(cur.get("loop", ""))
        assert _module(cur).get("follow") is True, (
            "the current-dir stat must pass follow: true EXPLICITLY (the stat "
            "module defaults follow to False in the installed ansible-core — a "
            "healthy runtime symlink chain must resolve to isreg; a dangling "
            "link must fail)"
        )

        assert_task = next(
            (
                t
                for t in _assert_tasks()
                if "verify_palette_checks" in str(_module(t).get("that", ""))
                and "verify_palette_current_checks" in str(_module(t).get("that", ""))
            ),
            None,
        )
        assert assert_task is not None, (
            "expected ONE assert consuming BOTH criterion-6 registers (the per-file OR)"
        )
        that = str(_module(assert_task).get("that", ""))
        assert "zip" in that, (
            "the assert must pair the two per-file result lists (zip) so the OR "
            "is evaluated per file, not across the whole set"
        )
        assert "map(attribute='stat.isreg', default=false)" in that, (
            "the assert must map stat.isreg with a default (absent on missing "
            "paths — a bare selectattr would break the pairing)"
        )
        assert assert_task.get("when") == "not ansible_check_mode", (
            "the criterion-6 assert must be check-gated (state assert discipline)"
        )
        fail_msg = str(_module(assert_task).get("fail_msg", ""))
        assert "generated/palettes" in fail_msg and "verify_state_current_dir" in fail_msg, (
            "fail_msg must enumerate BOTH accepted locations"
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

    def test_weg_gate_points_effects_at_the_spine_catalog(self) -> None:
        """The WEG parse gate must read the effects catalog the assets role
        emitted at <install>/config/weg/effects.yaml (config-in-spine
        2026-08-16; spec chaining-spine.md: env
        WALLPAPER_EFFECTS_CONFIG_FILE_PATH), NOT the XDG
        ~/.config/weg/effects.yaml fallback the installer never writes."""
        task = next(
            (t for t in _command_tasks() if str(t.get("name")) == "Gate weg settings parse"),
            None,
        )
        assert task is not None, "missing 'Gate weg settings parse' task"
        env = task.get("environment")
        assert isinstance(env, dict), "weg gate must set environment"
        assert env.get("WALLPAPER_EFFECTS_CONFIG_FILE_PATH") == ("{{ verify_weg_effects_path }}"), (
            "weg gate must wire WALLPAPER_EFFECTS_CONFIG_FILE_PATH to the spine catalog"
        )
        assert str(_vars().get("verify_weg_effects_path")) == (
            "{{ install_dir | trim }}/config/weg/effects.yaml"
        ), "verify_weg_effects_path must be the trim-locked spine config/weg/effects.yaml"

    def test_settings_spine_extraction_is_dynamic_and_check_gated(self) -> None:
        """Criterion 5 part 2 (review finding 2026-08-13): the spine-target
        gate READS each rendered settings.toml and stats the paths it actually
        references (parse ≠ works) — it must not be a static list. The
        extraction task is an `ansible.builtin.command` (argv form — no shell
        splitting), check-gated, and consumes verify_settings_files +
        verify_settings_spine_keys."""
        extraction = next(
            (
                task
                for task in _command_tasks()
                if "Extract spine paths referenced by rendered settings" == str(task.get("name"))
            ),
            None,
        )
        assert extraction is not None, (
            "expected an extraction command task reading the rendered settings"
        )
        assert extraction.get("when") == "not ansible_check_mode", (
            "the extraction command must be check-gated (command tasks skip under --check)"
        )
        argv = str(_module(extraction).get("argv", ""))
        assert "verify_settings_files" in str(extraction.get("loop", ""))
        assert "verify_settings_spine_keys" in argv
        assert "tomllib" in argv, (
            "the extraction must parse TOML (tomllib) to read the rendered paths"
        )
        assert "ansible_python_interpreter" in argv, (
            "the extraction must run with the ansible python (tomllib is "
            "stdlib >= 3.12, the project floor)"
        )
        stat = next(
            (
                task
                for task in _stat_tasks()
                if "verify_settings_referenced_targets" in str(task.get("loop", ""))
            ),
            None,
        )
        assert stat is not None, "expected a stat loop over the extracted referenced targets"
        assert stat.get("when") == "not ansible_check_mode"
        assert_task = next(
            (
                task
                for task in _assert_tasks()
                if "verify_settings_target_checks" in str(_module(task).get("that", ""))
            ),
            None,
        )
        assert assert_task is not None, "expected an assert consuming verify_settings_target_checks"
        that = str(_module(assert_task).get("that", ""))
        assert "verify_settings_extracted.results | selectattr('rc', 'equalto', 0)" in that, (
            "the assert must fail loudly when an extraction command failed "
            "(missing/unparseable settings file, renamed key)"
        )
        assert "verify_settings_referenced_targets | length > 0" in that, (
            "the assert must be non-vacuous (empty extraction must fail)"
        )
        assert assert_task.get("when") == "not ansible_check_mode"

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

    def test_shell_tools_clone_check_exists_and_is_check_gated(self) -> None:
        """Criterion 11 (zsh_tools): verify asserts the shell-tool clones
        (~/.oh-my-zsh, ~/.pyenv, ~/.nvm) exist as dirs. The stat task must loop
        over the shell.* dirs (the same source of truth zsh_tools uses) and the
        assert must be check-gated like every other state assert."""
        stat_task = None
        for task in _stat_tasks():
            if "verify_shell_tool_dirs" in str(task.get("register", "")):
                stat_task = task
                break
        assert stat_task is not None, "expected a verify_shell_tool_dirs stat task"
        loop = stat_task.get("loop", [])
        text = str(loop)
        assert "shell.oh_my_zsh_dir" in text
        assert "shell.pyenv_dir" in text
        assert "shell.nvm_dir" in text

        assert_tasks = [
            task
            for task in _assert_tasks()
            if "verify_shell_tool_dirs" in str(_module(task).get("that", ""))
        ]
        assert len(assert_tasks) == 1, (
            f"expected exactly one shell-tools assert; found {len(assert_tasks)}"
        )
        that = str(_module(assert_tasks[0]).get("that", ""))
        assert ".stat.exists" in that and ".stat.isdir" in that, (
            "shell-tools assert must check exists AND isdir"
        )
        assert assert_tasks[0].get("when") == "not ansible_check_mode"

    def test_managed_config_dirs_are_symlinks_into_the_spine(self) -> None:
        """Criterion 9 (config-in-spine 2026-08-16): the managed config dirs
        are SYMLINKS into the spine (~/.config/<name> -> <install>/config/<name>),
        so the real-dir check is REPLACED by the 5-layer symlink check
        (docs/02-config-in-spine-pattern.md):
          layer 1 — a `stat` with `follow: false` over verify_managed_link_dirs
                    asserts `stat.islnk` for every managed dir (it IS a link);
          layer 2 — an assert on `stat.lnk_target` proves no link is broken and
                    every target resolves in the spine (exact-target is locked by
                    config_links; here the no-broken-link assert guards the
                    unprovisioned case);
          layer 3 — a `stat` with `follow: true` over verify_config_copies_targets
                    asserts `stat.isdir` (the link resolves to a real dir);
          layer 4 — a `stat` over verify_config_copy_content asserts
                    `stat.isreg` THROUGH the link (content reachable);
          layer 5 — the parse gates (csg/weg/itr info --config) read the
                    settings THROUGH the link — covered by
                    test_settings_parse_gate_tasks_exist_and_are_check_gated.
        All tasks gated `when: not ansible_check_mode`."""
        stat = _managed_link_stat_task()
        assert _module(stat).get("follow") is False, (
            "layer-1 stat must pass follow: false (a real dir reports "
            "islnk: false — only symlinks pass the islnk count)"
        )
        assert "{{ verify_managed_link_dirs }}" in str(stat.get("loop", ""))
        assert stat.get("when") == "not ansible_check_mode"

        islnk_assert = _managed_link_islnk_assert_task()
        that = str(_module(islnk_assert).get("that", ""))
        assert "stat.islnk" in that
        assert "verify_managed_link_dirs | length" in that
        assert islnk_assert.get("when") == "not ansible_check_mode"

        target_assert = _managed_link_target_assert_task()
        that = str(_module(target_assert).get("that", ""))
        assert "stat.lnk_target" in that
        assert target_assert.get("when") == "not ansible_check_mode"

        resolve_stat = _managed_link_resolve_stat_task()
        assert _module(resolve_stat).get("follow") is True, (
            "layer-3 stat must pass follow: true (resolve the link target)"
        )
        assert "{{ verify_managed_link_dirs }}" in str(resolve_stat.get("loop", ""))
        assert resolve_stat.get("when") == "not ansible_check_mode"

        resolve_assert = _managed_link_resolve_assert_task()
        that = str(_module(resolve_assert).get("that", ""))
        assert "stat.isdir" in that
        assert "verify_managed_link_dirs | length" in that
        assert resolve_assert.get("when") == "not ansible_check_mode"

        follow_stat = _config_copy_follow_stat_task()
        assert _module(follow_stat).get("follow") is True, (
            "layer-3 stat must pass follow: true (resolve through the link)"
        )
        assert "{{ verify_config_copies_targets }}" in str(follow_stat.get("loop", ""))
        assert follow_stat.get("when") == "not ansible_check_mode"

        follow_assert = _config_copy_follow_assert_task()
        that = str(_module(follow_assert).get("that", ""))
        assert "stat.isdir" in that
        assert "verify_config_copies_targets | length" in that
        assert follow_assert.get("when") == "not ansible_check_mode"

        content_stat = _config_content_stat_task()
        assert _module(content_stat).get("follow") is True, (
            "layer-4 stat must pass follow: true (content read through the link)"
        )
        assert "{{ verify_config_copy_content }}" in str(content_stat.get("loop", ""))
        assert content_stat.get("when") == "not ansible_check_mode"

        content_assert = _config_content_assert_task()
        that = str(_module(content_assert).get("that", ""))
        assert "stat.isreg" in that
        assert "verify_config_copy_content | length" in that
        assert content_assert.get("when") == "not ansible_check_mode"

    def test_managed_link_dirs_parity_with_config_links(self) -> None:
        """Parity lock: verify_managed_link_dirs mirrors the config_links
        role's managed dir set EXACTLY — the symlink check must cover every
        dir the config-links role creates (a new managed dir not in verify
        would silently skip its symlink assertion)."""
        data = _vars()
        verify_links = list(data["verify_managed_link_dirs"])
        config_links = list(_sibling_vars("config_links")["config_links_managed_dirs"])
        assert verify_links == config_links, (
            "verify_managed_link_dirs must be parity-EXACT with "
            "config_links_managed_dirs (every managed link is asserted)"
        )

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
            "verify_state_current_dir",
            "verify_xdg_cache_home",
            "verify_xdg_dirs",
            "verify_install_spine_dirs",
            "verify_install_spine_files",
            "verify_settings_files",
            "verify_settings_spine_keys",
            "verify_itr_list_target",
            "verify_config_copy_content",
            "verify_managed_link_dirs",
            "<install>",
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
        "verify_weg_effects_path",
        "verify_asset_dirs",
        "verify_asset_files",
        "verify_system_binaries",
        "verify_cli_tools",
        "verify_cli_bin_dir",
        "verify_settings_files",
        "verify_settings_spine_keys",
        "verify_palette_files",
        "verify_state_current_dir",
        "verify_compositor_config_dirs",
        "verify_compositor_skeleton_files",
        "verify_compositor_fragments",
        "verify_config_copies_targets",
        "verify_config_copy_content",
        "verify_managed_link_dirs",
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
        files settings renders. config-in-spine (2026-08-16): both roles
        render into <install>/config/<tool>/settings.toml, but verify spells
        the seam as {{ install_dir | trim }}/config/... while settings reaches
        the same place via {{ settings_spine_config_dir }} (which IS
        install_dir/config). The parity contract is therefore the full relative
        layout after the Jinja var expression AND the leading config/ root —
        NOT just the tool-dir tail (review finding 2026-08-13: a root change
        like /etc/... would slip through a tail-only comparison)."""
        data = _vars()
        verify_dests = [str(f["dest"]) for f in data["verify_settings_files"]]
        settings_dests = [str(f["dest"]) for f in _sibling_vars("settings")["settings_files"]]

        def relative_path(dest: str) -> str:
            """Strip the `{{ <role>_<var> }}` seam expression and the leading
            `config/` root (verify reaches it as install_dir/config/<tool>,
            settings as settings_spine_config_dir/<tool>) and compare the full
            remainder — a divergence in the sub-layout (tool dir or filename)
            fails the parity."""
            assert "}}" in dest, f"dest {dest!r} must be Jinja-var-prefixed"
            rest = dest.split("}}", 1)[1].lstrip("/")
            if rest.startswith("config/"):
                rest = rest[len("config/") :]
            return rest

        assert [relative_path(d) for d in verify_dests] == [
            relative_path(d) for d in settings_dests
        ], (
            "verify_settings_files dests must be parity-EXACT with the settings "
            "role's settings_files dests (same full relative layout under "
            "<install>/config/)"
        )

    def test_settings_spine_keys_parity_with_settings_templates(self) -> None:
        """Parity lock (review finding 2026-08-13): each dotted key in
        verify_settings_spine_keys must appear as a path-bearing assignment in
        the matching settings template — if the settings role (2.11) renames a
        spine key, the verify gate must change in lockstep (the extraction
        task would otherwise silently read the wrong key). The dotted key is
        the TOML section + key name (e.g. [output] directory → output.directory)."""
        data = _vars()
        keys = data["verify_settings_spine_keys"]
        assert set(keys) == {"csg", "weg", "itr"}
        for name, dotted_keys in keys.items():
            template = (
                _ANSIBLE_DIR / "roles" / "settings" / "templates" / f"{name}-settings.toml.j2"
            )
            assert template.is_file(), f"missing settings template {template}"
            dotted = {str(k) for k in dotted_keys}

            section = ""
            assigned: set[str] = set()
            for line in template.read_text().splitlines():
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    continue
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if "install_dir" in line:
                        assigned.add(f"{section}.{key}")

            assert dotted <= assigned, (
                f"verify_settings_spine_keys[{name}] {dotted - assigned} not found "
                f"as path-bearing assignments in {template.name}; found {assigned}"
            )

    def test_settings_spine_keys_values_are_dotted_toml_paths(self) -> None:
        """The extraction keys must be dotted TOML key paths (section.key), not
        raw paths — the extraction task walks them into the parsed settings
        dict."""
        data = _vars()
        for name, dotted_keys in data["verify_settings_spine_keys"].items():
            for dotted in dotted_keys:
                value = str(dotted)
                assert "." in value and not value.startswith("{{"), (
                    f"verify_settings_spine_keys[{name}] entry {value!r} must be a "
                    "dotted TOML key path, not a rendered path"
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
        """Criterion 6 (Story 1.12 relaxed to generated OR current): the
        palette files check is exactly the three chain formats
        (conf/gtk.css/yaml) — NOT json/sh (no Phase 1 consumer). The list is
        shared by BOTH criterion-6 candidate locations (generated/palettes/
        and the runtime current dir)."""
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

    def test_state_current_dir_derived_from_verify_xdg_state_home(self) -> None:
        """Story 1.12 AC 4: verify_state_current_dir is <state>/dotfiles/
        current (AD-5) DERIVED from the existing verify_xdg_state_home var —
        no duplicate XDG resolution may be introduced."""
        data = _vars()
        value = str(data["verify_state_current_dir"])
        assert value == "{{ verify_xdg_state_home | trim }}/dotfiles/current", (
            "verify_state_current_dir must derive from verify_xdg_state_home "
            "(trim lock) — never a second ansible_facts.env.XDG_STATE_HOME read"
        )
        assert "ansible_facts.env.XDG_STATE_HOME" not in value

    def test_cli_tools_are_csg_weg_itr(self) -> None:
        data = _vars()
        assert [str(c) for c in data["verify_cli_tools"]] == ["csg", "weg", "itr"]

    def test_system_binaries_are_compositors(self) -> None:
        data = _vars()
        assert [str(b) for b in data["verify_system_binaries"]] == [
            "hyprland",
            "hyprpaper",
            "ags",
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
            "verify_state_current_dir",
            "verify_xdg_cache_home",
            "verify_xdg_dirs",
            "verify_install_spine_dirs",
            "verify_install_spine_files",
            "verify_settings_files",
            "verify_settings_spine_keys",
            "verify_itr_list_target",
            "verify_config_copy_content",
            "verify_managed_link_dirs",
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
        "machine" (spine incl. config/ subtree, assets, palette, settings +
        spine targets in the spine, compositor configs, config copies, the
        ~/.config symlinks into the spine, stub binaries) and assert the real
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

    def test_verify_fails_when_parse_gate_binary_fails(self) -> None:
        """Negative lock for the settings parse gates (review finding
        2026-08-13): a stub CLI that exits NON-ZERO must make verify FAIL —
        the parse gates are real gates, not stubbed-green. Previously the
        stubs exited 0 unconditionally, so a broken gate (or wrong --config
        path) would go green; this proves the weg/itr/csg rc asserts bite."""
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

            # Make the WEG stub fail (itr/csg stay green — only the WEG gate
            # is tripped, proving that specific rc assert is a real gate).
            (bin_dir / "weg").write_text("#!/bin/sh\nexit 1\n")

            env = _test_env(
                HOME=str(home),
                XDG_CONFIG_HOME=str(xdg),
                ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"),
                PATH=f"{bin_dir}:{os.environ.get('PATH', '')}",
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
                "verify must FAIL when a parse-gate CLI exits non-zero (the "
                "rc asserts are real gates, not stubbed green); recap:\n" + result.stdout
            )
            assert (
                "verify_weg_gate" in result.stdout
                or "one of the rendered settings" in result.stdout
            ), "the failure must be the settings parse-gate assert"

    def test_verify_fails_when_settings_reference_missing_dir(self) -> None:
        """Negative lock for the dynamic spine-target gate (review finding
        2026-08-13): a rendered settings.toml whose spine path points at a
        MISSING directory must FAIL verify — even though the file parses and
        every static target exists. This is the parse ≠ works proof: the gate
        reads the rendered files, it cannot go green on a wrong render."""
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

            # Mis-render the CSG settings to point at a directory that does
            # NOT exist (still valid TOML — the file parses fine). The file
            # lives in the SPINE (config-in-spine); the ~/.config symlink
            # exposes it to the tools.
            (install / "config" / "color-scheme-generator" / "settings.toml").write_text(
                f'[output]\ndirectory = "{install}/generated/missing-dir"\n'
                'overwrite = false\ndefault_formats = ["conf", "gtk.css", "yaml"]\n'
            )

            env = _test_env(
                HOME=str(home),
                XDG_CONFIG_HOME=str(xdg),
                ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"),
                PATH=f"{bin_dir}:{os.environ.get('PATH', '')}",
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
                "verify must FAIL when a rendered settings file references a "
                "MISSING spine path (parse ≠ works — the gate reads the "
                "rendered files, not a static list); recap:\n" + result.stdout
            )

    def test_verify_criterion_6_accepts_runtime_current_palette(self) -> None:
        """Story 1.12 AC 4: on a post-runtime machine where the palette was
        consumed into $XDG_STATE_HOME/dotfiles/current/ (a runtime symlink
        chain into the cache), criterion 6 must PASS via the current/ leg even
        with generated/palettes/colors.conf gone — and must FAIL again when
        NEITHER location holds the file (negative lock: the gate is not
        vacuous). The current/ file is created as a SYMLINK chain through the
        state cache so the explicit follow: true resolution is exercised."""
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

            state_root = home / ".local" / "state" / "dotfiles"
            cache_palette = state_root / "cache" / "palettes" / "abc123"
            cache_palette.mkdir(parents=True)
            (cache_palette / "colors.conf").write_text("$background = 0x000000\n")
            state_current = state_root / "current"
            state_current.mkdir(parents=True)
            (state_current / "colors.conf").symlink_to(cache_palette / "colors.conf")
            (install / "generated" / "palettes" / "colors.conf").unlink()

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

            post_runtime = run()
            assert post_runtime.returncode == 0, (
                "verify must PASS on a post-runtime machine where the palette "
                "was consumed into state_root/current (criterion 6 generated OR "
                "current, Story 1.12); recap:\n" + post_runtime.stdout
            )

            (state_current / "colors.conf").unlink()
            no_palette = run()
            assert no_palette.returncode != 0, (
                "verify must FAIL when a palette file exists in NEITHER "
                "generated/palettes/ nor state_root/current/ (negative lock — "
                "the OR-relaxation is not vacuous); recap:\n" + no_palette.stdout
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
    """A scrubbed env for playbook subprocesses (review findings 2026-08-12 and
    2026-08-13): drop ambient ANSIBLE_* vars (a developer's ANSIBLE_INVENTORY /
    ANSIBLE_ROLES_PATH / etc. would otherwise silently override ansible.cfg)
    AND ambient XDG_STATE_HOME/XDG_CACHE_HOME/XDG_BIN_HOME/UV_TOOL_BIN_DIR (a
    developer's real XDG state/cache/bin dirs would make verify_xdg_* resolve
    against the HOST instead of the temp machine, and the CLI-tool PATH prepend
    would target the wrong bin dir) — then apply the explicit overrides."""
    drop_prefixes = ("ANSIBLE_", "XDG_", "UV_TOOL_")
    env = {k: v for k, v in os.environ.items() if not k.startswith(drop_prefixes)}
    env.update(overrides)
    return env


def _write_stub_binaries(home: Path) -> Path:
    """Stub hyprland/hyprpaper/ags/csg/weg/itr as executable `#!/bin/sh`
    scripts in home/.local/bin that exit 0 — so `command -v` + the csg/weg/itr
    parse gates pass without installing real CLIs. Also stub `systemctl` so the
    NetworkManager-active gate (criterion-2 sibling) passes on the synthetic
    machine: report `NetworkManager` as active."""
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("hyprland", "hyprpaper", "ags", "csg", "weg", "itr"):
        stub = bin_dir / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    sysctl = bin_dir / "systemctl"
    sysctl.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "is-active" ] && [ "$2" = "NetworkManager" ]; then\n'
        '  echo active; exit 0\n'
        "fi\n"
        "exit 1\n"
    )
    sysctl.chmod(0o755)
    return bin_dir


def _build_provisioned_layout(home: Path, xdg: Path, install: Path) -> None:
    """Create the minimal provisioned "machine" verify.yaml asserts against
    (config-in-spine 2026-08-16): the full install-spine subtree (including
    config/ and its managed tool subdirs), the five asset outcomes, the three
    palette files, the three rendered settings.toml files in the SPINE, the
    compositor skeletons + fragments in the spine, the config copies in the
    spine, the XDG state/cache homes, and the ~/.config/<name> -> spine
    symlinks the config-links role creates. The spine is the home; every
    ~/.config managed dir is a symlink into it."""
    spine_dirs = (
        "wallpapers",
        "icon-templates",
        "icon-mappings",
        "config",
        "config/color-scheme-generator",
        "config/color-scheme-generator/templates",
        "config/hypr",
        "config/hyprpaper",
        "config/ags",
        "config/nvim",
        "config/starship",
        "config/wlogout",
        "config/zsh",
        "config/weg",
        "config/itr",
        "generated",
        "generated/palettes",
        "generated/effects",
        "generated/icons",
        "generated/.weg-tmp",
    )
    for rel in spine_dirs:
        (install / rel).mkdir(parents=True, exist_ok=True)
    (install / "config" / "weg" / "effects.yaml").write_text("{}\n")

    (home / ".local" / "state").mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)

    (install / "wallpapers" / "default.png").write_bytes(b"\x89PNG")
    (install / "icon-mappings" / "icons.yaml").write_text("variants: []\n")
    for name in ("colors.conf", "colors.yaml", "colors.gtk.css"):
        (install / "generated" / "palettes" / name).write_text("")

    (install / "config" / "color-scheme-generator" / "settings.toml").write_text(
        f'[output]\ndirectory = "{install}/generated/palettes"\n'
        'overwrite = false\ndefault_formats = ["conf", "gtk.css", "yaml"]\n'
    )
    (install / "config" / "weg" / "settings.toml").write_text(
        f'[output]\ndirectory = "{install}/generated/effects"\n'
        f'[processing]\ntemp_dir = "{install}/generated/.weg-tmp"\n'
        "[execution]\nstrict = false\n"
    )
    (install / "config" / "itr" / "settings.toml").write_text(
        f'[output]\noutput_dir = "{install}/generated/icons"\n'
        f'[templates]\ndir = "{install}/icon-templates"\n'
        f'[color_scheme]\npath = "{install}/generated/palettes/colors.yaml"\n'
    )

    for lua in (
        "hyprland.lua",
        "keybindings.lua",
        "monitors.lua",
        "autostart.lua",
        "window-rules.lua",
        "animations.lua",
        "input.lua",
        "decoration.lua",
        "cursor.lua",
        "env-variables.lua",
    ):
        (install / "config" / "hypr" / lua).write_text("")
    (install / "config" / "hyprpaper" / "hyprpaper.conf").write_text("")
    (install / "config" / "ags" / "app.tsx").write_text("")
    (install / "config" / "ags" / "style.css").write_text("")
    # AGS bar skeletons (enhance-ags-bar: icons registry + Bar + widgets)
    (install / "config" / "ags" / "icons.json").write_text("{}")
    for rel in ("ags/lib", "ags/bar", "ags/bar/widgets"):
        (install / "config" / rel).mkdir(parents=True, exist_ok=True)
    (install / "config" / "ags" / "lib" / "icon-registry.ts").write_text("")
    (install / "config" / "ags" / "bar" / "Bar.tsx").write_text("")
    for widget in ("workspaces", "clock", "battery", "network", "power-menu"):
        (install / "config" / "ags" / "bar" / "widgets" / f"{widget}.tsx").write_text("")
    (install / "config" / "hypr" / "colors.conf").write_text("")
    (install / "config" / "ags" / "colors.css").write_text("")

    (install / "config" / "nvim" / "init.lua").write_text("")
    (install / "config" / "starship" / "starship.toml").write_text("")
    (install / "config" / "wlogout" / "layout").write_text("")
    # Rendered shell configs (zsh_config + wlogout_config roles): verify checks
    # the FINAL .zshrc / style.css, not the .j2/.tpl sources.
    (install / "config" / "zsh" / ".zshrc").write_text(
        'command -v starship >/dev/null 2>&1 && eval "$(starship init zsh)"\n'
        '(cat "<INSTALL>/generated/palettes/colors.sequences" &)\n'
    )
    (install / "config" / "wlogout" / "style.css").write_text(
        '@import url("<INSTALL>/config/ags/colors.css");\nbutton { color: @color_15; }\n'
    )

    # Shell-tools clones (zsh_tools role — done-criterion 11): verify checks
    # ~/.oh-my-zsh, ~/.pyenv, ~/.nvm exist as dirs (in the HOME the playbook
    # runs as, which the shell.* block reads from group_vars/all.yml).
    for clone in ("oh-my-zsh", "pyenv", "nvm"):
        (home / f".{clone}").mkdir(parents=True, exist_ok=True)

    # Rendered icons (icons role — done-criterion: generated/icons populated).
    (install / "generated" / "icons" / "battery-0.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    )

    for name in (
        "hypr",
        "hyprpaper",
        "ags",
        "nvim",
        "starship",
        "wlogout",
        "zsh",
        "color-scheme-generator",
        "weg",
        "itr",
    ):
        (xdg / name).symlink_to(install / "config" / name, target_is_directory=True)
