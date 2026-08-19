from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from provisioning.domain.enums import AssetKind


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_filesystem_role.py``: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-16 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "assets"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_MANIFEST_PATH = _REPO_ROOT / "dotfiles" / "provisioning" / "assets.yaml"

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
    module = task.get(_module_key(task) or "", {})
    assert isinstance(module, dict)
    return module


def _module_text(task: dict[str, object]) -> str:
    """Return the module body as text for free-form tasks (string-valued
    modules like `ansible.builtin.shell: command -v weg`)."""
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


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


# config-in-spine (2026-08-16): the assets role relocated its TOOL-CONFIG
# outputs under <install>/config/. The domain AssetKind.spine_segment() still
# returns the pre-relocation segments (csg-templates / weg-effects.yaml — the
# manifest is the pre-refactor layout), so the deploy-target derivation applies
# these relocations on top of the domain mapping.
_CONFIG_IN_SPINE_RELOCATIONS = {
    AssetKind.CSG_TEMPLATE.spine_segment(): "config/color-scheme-generator/templates",
    AssetKind.WEG_EFFECTS.spine_segment(): "config/weg",
}


def _deploy_segment(kind: AssetKind) -> str:
    """The config-in-spine deploy target for an asset kind: the domain
    spine_segment(), with TOOL-CONFIG kinds relocated under <install>/config/.
    For WEG_EFFECTS this is the PARENT DIRECTORY (config/weg) the emitted
    effects.yaml file lands in — not the file itself."""
    return _CONFIG_IN_SPINE_RELOCATIONS.get(kind.spine_segment(), kind.spine_segment())


def _tasks_with_module(module: str) -> list[dict[str, object]]:
    return [task for task in _load_tasks() if _module_key(task) == module]


class TestAssetsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestAssetsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Locks AC8: the FIRST task is an `ansible.builtin.assert` requiring
        the install_dir seam extra-var — the identical verbatim copy of the 2.5
        filesystem assert (no aliasing into a var)."""
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

    def test_weg_presence_fail_loud_guard(self) -> None:
        """Direct-run prerequisite (AC 9): a `shell` `command -v weg` task
        registers a var and an `assert` checks rc == 0, gated
        `when: not ansible_check_mode` — mirror of the 2.4 uv guard, so a
        direct assets.yaml run before cli_tools fails fast with a clear message
        instead of an opaque rc=2 at the last task."""
        shell_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.shell")
            if "command -v weg" in _module_text(task)
        ]
        assert shell_tasks, "no `command -v weg` presence check found"
        for task in shell_tasks:
            assert task.get("register"), "weg check must register its result"
            assert task.get("failed_when") is False, "weg check must not fail the play"

        assert_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if "assets_weg_check.rc == 0" in str(_module(task).get("that", ""))
        ]
        assert assert_tasks, "no assert locking assets_weg_check.rc == 0 found"
        for task in assert_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "weg assert must be gated when: not ansible_check_mode"
            )

    def test_wallpapers_tarball_membership_asserted(self) -> None:
        """Content-regression guard (AC 11, hardened): a `shell` tar listing of
        the tarball registers a var, and an `assert` checks the listing shows
        default.png — catches a regressed tarball that drops default.png even
        when a stale copy lingers on disk (unarchive never prunes)."""
        shell_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.shell")
            if "tar -tzf" in _module_text(task)
        ]
        assert shell_tasks, "no tarball membership `tar -tzf` check found"
        for task in shell_tasks:
            assert "default.png" in _module_text(task)
            assert task.get("register"), "tarball check must register its result"

        assert_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if "assets_wallpapers_tarball_check.rc == 0" in str(_module(task).get("that", ""))
        ]
        assert assert_tasks, "no assert locking tarball default.png membership found"
        for task in assert_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "tarball membership assert must be gated when: not ansible_check_mode"
            )

    def test_deploy_targets_ensured_via_file_directory(self) -> None:
        """AC 9: a `file` `state: directory` task loops `{{ assets_deploy_dirs }}`
        with path `{{ install_dir | trim }}/{{ item }}` — re-ensuring the four
        deploy targets so unarchive's dest-must-exist contract holds."""
        matches = [
            task
            for task in _tasks_with_module("ansible.builtin.file")
            if task.get("loop") == "{{ assets_deploy_dirs }}"
        ]
        assert matches, "no task ensuring the asset deploy targets found"
        for task in matches:
            module = _module(task)
            assert module["state"] == "directory"
            assert module["path"] == "{{ install_dir | trim }}/{{ item }}"

    def test_deploy_targets_are_exactly_the_five_spine_segments(self) -> None:
        """AC 9: assets_deploy_dirs is exactly the five segments this role
        deploys into (config-in-spine 2026-08-16: the two TOOL-CONFIG kinds
        relocated under <install>/config/) — derived from
        AssetKind (via the config-in-spine relocation map), never a hardcoded
        literal that could silently diverge from the domain."""
        data = _vars()
        dirs = {str(item) for item in data["assets_deploy_dirs"]}
        expected = {_deploy_segment(kind) for kind in AssetKind}
        assert dirs == expected

    def test_wallpapers_unpacked_via_unarchive(self) -> None:
        """AC 2: an `ansible.builtin.unarchive` task unpacks
        `{{ assets_repo_root }}/{{ assets_wallpapers_tarball }}` into
        `{{ assets_wallpapers_dest }}` with `remote_src: true`."""
        matches = _tasks_with_module("ansible.builtin.unarchive")
        assert len(matches) == 1, (
            f"expected exactly one unarchive task (wallpapers); found {len(matches)}"
        )
        module = _module(matches[0])
        assert module["src"] == "{{ assets_repo_root }}/{{ assets_wallpapers_tarball }}"
        assert module["dest"] == "{{ assets_wallpapers_dest }}"
        assert module["remote_src"] is True

    def test_unarchive_carries_no_creates(self) -> None:
        """AC 10 (FR-18 regenerate semantics): the unarchive task must NOT
        carry `creates:` — a creates guard would skip re-extraction whenever
        the dest matches, so a replaced wallpapers.tar.gz would never trigger
        Story 2.7's palette regeneration."""
        matches = _tasks_with_module("ansible.builtin.unarchive")
        assert matches, "no unarchive task found"
        for task in matches:
            assert _creates_value(task) is None, (
                f"unarchive task {task.get('name')!r} must NOT carry creates: "
                "(AC 10 — FR-18 regenerate semantics)"
            )

    def test_directory_kinds_deployed_via_single_copy_loop(self) -> None:
        """AC 3-5: exactly one `ansible.builtin.copy` task loops
        `{{ assets_copies }}` with `remote_src: true`, src
        `{{ assets_repo_root }}/{{ item.source }}`, dest
        `{{ install_dir | trim }}/{{ item.target }}`."""
        matches = _tasks_with_module("ansible.builtin.copy")
        assert len(matches) == 1, (
            f"expected exactly one copy task looping assets_copies; found {len(matches)}"
        )
        task = matches[0]
        assert task.get("loop") == "{{ assets_copies }}"
        module = _module(task)
        assert module["src"] == "{{ assets_repo_root }}/{{ item.source }}"
        assert module["dest"] == "{{ install_dir | trim }}/{{ item.target }}"
        assert module["remote_src"] is True
        assert task.get("when") == "not ansible_check_mode", (
            "copy task must be gated when: not ansible_check_mode — its dest "
            "dir is only would-created under --check, so the module aborts on "
            "a fresh target"
        )

    def test_every_copy_source_ends_with_slash(self) -> None:
        """AC 13 contents semantics: every assets_copies source ends with `/`
        so copy lands the directory contents directly in the target — without
        the slash the source dir itself would nest under the target."""
        data = _vars()
        copies = [dict(item) for item in data["assets_copies"]]
        assert copies, "assets_copies must not be empty"
        for entry in copies:
            assert str(entry["source"]).endswith("/"), (
                f"copy source {entry['name']!r} must end with '/' (AC 13)"
            )

    def test_weg_effects_emitted_via_command_with_stat_gate(self) -> None:
        """AC 6 + AC 14: a `command` task runs
        `weg dump-effects --output {{ assets_weg_effects_target }}` with PATH
        prepending `{{ assets_weg_bin_dir }}:`, gated on a stat of the target
        (skip when present and non-empty — FR-18-consistent regenerate on
        absence/truncation, not a bare existence `creates:` that would freeze a
        corrupt catalog)."""
        stat_matches = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if str(_module(task).get("path", "")) == "{{ assets_weg_effects_target }}"
        ]
        assert stat_matches, "no stat task on {{ assets_weg_effects_target }} found"
        for task in stat_matches:
            assert task.get("register"), "emit stat task must register its result"

        matches = [
            task
            for task in _tasks_with_module("ansible.builtin.command")
            if "weg" in _module_text(task)
        ]
        assert matches, "no `weg dump-effects` command task found"
        for task in matches:
            module = _module(task)
            argv = module.get("argv")
            assert isinstance(argv, list) and argv, "emit task must use argv list form"
            assert argv[:3] == ["weg", "dump-effects", "--output"], (
                f"emit task {task.get('name')!r} argv must run weg dump-effects --output"
            )
            assert len(argv) == 4 and argv[3] == "{{ assets_weg_effects_target }}", (
                "emit task must target assets_weg_effects_target"
            )
            when = task.get("when")
            assert when is not None, "emit task must be gated on the catalog stat"
            assert "assets_weg_catalog.stat.exists" in str(when)
            assert "assets_weg_catalog.stat.size == 0" in str(when)
            env = task.get("environment")
            assert isinstance(env, dict), "emit task must set environment"
            assert env.get("PATH", "").startswith("{{ assets_weg_bin_dir }}:"), (
                "emit task must prepend assets_weg_bin_dir to PATH (AC 14)"
            )

    def test_default_png_asserted_via_stat_plus_assert(self) -> None:
        """AC 11: a `stat` on `{{ install_dir }}/wallpapers/default.png`
        registers a var, and an `assert` checks that registered var's
        `stat.exists` — both gated `when: not ansible_check_mode`. An assert
        alone CANNOT check file existence, so the stat is mandatory."""
        stat_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if "{{ install_dir | trim }}/wallpapers/default.png"
            in str(_module(task).get("path", ""))
        ]
        assert stat_tasks, "no stat task on {{ install_dir }}/wallpapers/default.png found"
        for task in stat_tasks:
            assert task.get("register"), "stat task must register its result"
            assert task.get("when") == "not ansible_check_mode", (
                "stat task must be gated when: not ansible_check_mode"
            )

        assert_tasks = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if str(_module(task).get("that", "")) == "assets_default_png.stat.exists"
        ]
        assert assert_tasks, (
            "no assert task checking assets_default_png.stat.exists found "
            "(an assert alone cannot check file existence — the stat is mandatory)"
        )
        for task in assert_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "default.png assert must be gated when: not ansible_check_mode"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context (AC 12): NO become/become_user anywhere
        — everything the role writes lives under the user's install_dir."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_repo_paths_hardcoded(self) -> None:
        """AC 13: every `src`/`argv` source reference is interpolated via
        `{{ assets_repo_root }}/`, never an absolute repo path baked into the
        task. Checks every task's module body (not a substring scan that skips
        tasks)."""
        for task in _load_tasks():
            module_key = _module_key(task)
            assert module_key is not None
            raw = task.get(module_key)
            if isinstance(raw, str):
                raw = {module_key: raw}
            assert isinstance(raw, dict)
            src = raw.get("src")
            argv = raw.get("argv")
            if isinstance(argv, list):
                argv = " ".join(str(item) for item in argv)
            if src is not None:
                assert str(src).startswith("{{ assets_repo_root }}/"), (
                    f"task {task.get('name')!r} must interpolate sources via "
                    "'{{ assets_repo_root }}/' (AC 13)"
                )
            if isinstance(argv, str):
                for token in str(raw).split():
                    if token.startswith("/") and "assets_repo_root" not in token:
                        raise AssertionError(
                            f"task {task.get('name')!r} argv must not hardcode "
                            f"an absolute path: {token!r} (AC 13)"
                        )


class TestAssetsVars:
    _REQUIRED_KEYS = {
        "assets_repo_root",
        "assets_weg_bin_dir",
        "assets_deploy_dirs",
        "assets_wallpapers_tarball",
        "assets_wallpapers_dest",
        "assets_copies",
        "assets_weg_effects_target",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_repo_root_mirrors_cli_tools(self) -> None:
        data = _vars()
        assert str(data["assets_repo_root"]) == "{{ playbook_dir }}/../../../.."

    def test_weg_bin_dir_defaults_under_home(self) -> None:
        """uv's bin-dir resolution: UV_TOOL_BIN_DIR -> XDG_BIN_HOME ->
        $HOME/.local/bin. Falls back to $HOME/.local/bin when no XDG/uv var is
        set, and honors the overrides in lockstep with cli_tools_bin_dir.
        (Fixes the custom-XDG fresh-machine failure where `weg` was installed
        elsewhere but the role looked only at $HOME/.local/bin.)"""
        data = _vars()
        value = str(data["assets_weg_bin_dir"])
        assert "UV_TOOL_BIN_DIR" in value
        assert "XDG_BIN_HOME" in value
        assert "ansible_facts.env.HOME + '/.local/bin'" in value

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        data = _vars()
        text = str(data)
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text

    def test_wallpapers_dest_and_weg_effects_target_are_trim_locked(self) -> None:
        """2.5 review lock: path-bearing vars consume the same trimmed
        `{{ install_dir | trim }}` value the fail-loud assert validates."""
        data = _vars()
        assert str(data["assets_wallpapers_dest"]) == "{{ install_dir | trim }}/wallpapers"
        assert str(data["assets_weg_effects_target"]) == (
            "{{ install_dir | trim }}/config/weg/effects.yaml"
        )

    def test_parity_with_manifest(self) -> None:
        """AC 15 parity lock (resolves deferred #164 — key off kind +
        spine_segment(), not name): the role's partition exactly mirrors the
        manifest. assets_copies names ∪ {wallpapers, weg-effects} == manifest
        entry names; copies match by (name, kind, source.rstrip("/")); every
        copy target equals the kind→spine-segment mapping (with the
        config-in-spine relocation: csg-templates → config/color-scheme-
        generator/templates); the wallpaper tarball var equals the manifest
        wallpapers source; the manifest weg-effects entry has kind weg-effects
        and no source."""
        data = _vars()
        copies = [dict(item) for item in data["assets_copies"]]
        manifest_entries = _manifest_entries()
        manifest = {item["name"]: item for item in manifest_entries}

        names = [item["name"] for item in manifest_entries]
        assert len(names) == len(set(names)), (
            "manifest entry names must be unique — a duplicate collapses the parity lock"
        )

        copy_names = {entry["name"] for entry in copies}
        assert copy_names | {"wallpapers", "weg-effects"} == set(manifest), (
            "assets_copies names ∪ {wallpapers, weg-effects} must equal the "
            "manifest entry names (single source of truth)"
        )

        kind_to_segment = {
            kind.value: _deploy_segment(kind)
            for kind in AssetKind
            if kind is not AssetKind.WALLPAPER and kind is not AssetKind.WEG_EFFECTS
        }
        for entry in copies:
            manifest_entry = manifest[entry["name"]]
            assert entry["kind"] == manifest_entry["kind"], (
                f"copy {entry['name']!r} kind diverges from the manifest"
            )
            assert str(entry["source"]).rstrip("/") == str(manifest_entry["source"]).rstrip("/"), (
                f"copy {entry['name']!r} source diverges from the manifest"
            )
            assert entry["target"] == kind_to_segment[entry["kind"]], (
                f"copy {entry['name']!r} target must equal the kind→spine-segment "
                "mapping (deferred #164 lock, derived from AssetKind with the "
                "config-in-spine relocation for csg-templates)"
            )

        assert str(data["assets_wallpapers_tarball"]) == manifest["wallpapers"]["source"]
        assert manifest["wallpapers"]["kind"] == AssetKind.WALLPAPER.value, (
            "the manifest wallpapers entry kind must be the wallpaper kind"
        )
        assert manifest["weg-effects"]["kind"] == AssetKind.WEG_EFFECTS.value
        assert "source" not in manifest["weg-effects"], (
            "the manifest weg-effects entry must have no source (it is emitted, not copied)"
        )


class TestAssetsPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "assets.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["assets"]
        assert "become" not in play, "assets playbook must not use become"
        assert "become_user" not in play, "assets playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the assets playbook — no `group_by` task
        module and no `groups` grouping key in the parsed play."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "assets playbook must not use group_by"
        assert "groups" not in play, "assets playbook must not group hosts"

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
