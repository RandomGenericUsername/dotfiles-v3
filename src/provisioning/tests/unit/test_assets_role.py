from __future__ import annotations

import fnmatch
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
            env = task.get("environment")
            assert isinstance(env, dict), "weg check must set environment"
            assert env.get("PATH", "").startswith("{{ assets_weg_bin_dir }}:"), (
                "weg check must prepend assets_weg_bin_dir to PATH (mirror of "
                "2.7 csg guard) so the guard finds weg even when ~/.local/bin "
                "is not on the inherited playbook PATH (VM-verified 2026-08-19)"
            )

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
        """AC 2 / S1: an `ansible.builtin.unarchive` task unpacks the tarball
        INSIDE the pinned assets checkout (`{{ assets_wallpapers_tarball }}`,
        already absolute) into `{{ assets_wallpapers_dest }}` with
        `remote_src: true`."""
        matches = _tasks_with_module("ansible.builtin.unarchive")
        assert len(matches) == 1, (
            f"expected exactly one unarchive task (wallpapers); found {len(matches)}"
        )
        module = _module(matches[0])
        assert module["src"] == "{{ assets_wallpapers_tarball }}"
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

    def test_directory_kinds_deployed_via_single_mirror_loop(self) -> None:
        """AC 3-5 / S1: the directory kinds deploy through ONE
        `ansible.posix.synchronize` task looping `{{ assets_copies }}` with
        `delete: true`, src `{{ item.source }}` (an absolute path into the
        pinned assets checkout since S1), dest
        `{{ install_dir | trim }}/{{ item.target }}` — icon-mappings included
        (converge semantics restored 2026-09-07; the brief seed-once
        experiment was reverted: the authoring model is repo-authoritative).
        (2026-09-07: replaced ansible.builtin.copy with a mirror — files
        deleted from the pinned corpus (e.g. replaced icon template groups)
        must be pruned from the spine on the next apply, exactly as fresh
        installs see them; copy merged only and left stale templates behind.)

        S6 adds a SECOND mirror loop for the one kind that lives in a pinned
        CLI checkout (`csg-templates`, spine AD-10). Same module, same
        delete/dest semantics — every source is already absolute."""
        loop_matches = [
            task
            for task in _tasks_with_module("ansible.posix.synchronize")
            if task.get("loop") == "{{ assets_copies }}"
        ]
        assert len(loop_matches) == 1, (
            f"expected exactly one synchronize task looping assets_copies; "
            f"found {len(loop_matches)}"
        )
        task = loop_matches[0]
        module = _module(task)
        assert module["src"] == "{{ item.source }}"
        assert module["dest"] == "{{ install_dir | trim }}/{{ item.target }}"
        assert module["delete"] is True, (
            "synchronize must carry delete: true — the deploy is a mirror of "
            "the repo tree, not a merge"
        )
        assert task.get("when") == "not ansible_check_mode", (
            "synchronize task must be gated when: not ansible_check_mode — its "
            "dest dir is only would-created under --check, so the module "
            "aborts on a fresh target"
        )

        checkout_matches = [
            task
            for task in _tasks_with_module("ansible.posix.synchronize")
            if task.get("loop") == "{{ assets_checkout_copies }}"
        ]
        assert len(checkout_matches) == 1, (
            "expected exactly one synchronize task looping the pinned-checkout "
            f"copies; found {len(checkout_matches)}"
        )
        checkout_module = _module(checkout_matches[0])
        assert checkout_module["src"] == "{{ item.source }}", (
            "a pinned-checkout source is already absolute — it must NOT be "
            "prefixed with a repo root"
        )
        assert checkout_module["dest"] == "{{ install_dir | trim }}/{{ item.target }}"
        assert checkout_module["delete"] is True
        assert checkout_matches[0].get("when") == "not ansible_check_mode"

        # The old merge-only copy deploy must not linger alongside the mirror.
        copy_matches = [
            task
            for task in _tasks_with_module("ansible.builtin.copy")
            if task.get("loop") in ("{{ assets_copies }}", "{{ assets_checkout_copies }}")
        ]
        assert not copy_matches, (
            "no ansible.builtin.copy task may loop the copy sets — the "
            "directory kinds deploy via the mirror synchronize"
        )

        data = _vars()
        loop_names = {entry["name"] for entry in data["assets_copies"]}
        assert "icon-mappings" in loop_names, (
            "icon-mappings must converge via assets_copies (repo edits must "
            "propagate on every bootstrap)"
        )
        # No seed-once residue: the dedicated stat gate and seed copy are gone.
        marker_stats = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if "icon_mappings_seed" in str(_module(task).get("path", ""))
        ]
        assert not marker_stats, "seed-once stat gate must not remain"
        assert not any("icon_mappings_seed" in str(key) for key in data), (
            "seed-once vars must not remain"
        )

    def test_every_copy_source_ends_with_slash(self) -> None:
        """AC 13 contents semantics: every copy source ends with `/` so copy
        lands the directory contents directly in the target — without the slash
        the source dir itself would nest under the target."""
        data = _vars()
        copies = [
            dict(item)
            for item in list(data["assets_copies"]) + list(data["assets_checkout_copies"])
        ]
        assert copies, "the copy sets must not be empty"
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

    def test_pinned_checkout_is_fetched_before_every_copy(self) -> None:
        """S1/AD-6: the corpus is fetched ONCE, before any copy.

        A shallow `ansible.builtin.git` clone of `{{ assets_repo }}` at
        `{{ assets_pinned_tag }}` into `{{ assets_checkout_root }}` (depth 1),
        the clone's .git removed, `{{ assets_pinned_file }}` written with the
        tag, and a stat+assert on the checkout's icons/schema.json before the
        first copy. The task ORDER is the point: a copy from a missing checkout
        would silently deploy nothing.
        """
        tasks = _load_tasks()
        clones = [
            task
            for task in _tasks_with_module("ansible.builtin.git")
            if str(_module(task).get("dest", "")) == "{{ assets_checkout_root }}"
        ]
        assert len(clones) == 1, f"expected exactly one pinned assets clone; got {len(clones)}"
        clone = clones[0]
        module = _module(clone)
        assert module["repo"] == "{{ assets_repo }}"
        assert module["version"] == "{{ assets_pinned_tag }}"
        assert module["depth"] == 1, "the fetch must be shallow (AD-6: once, not history)"
        when = clone.get("when")
        assert isinstance(when, list) and "not ansible_check_mode" in when, (
            "the clone must be gated when: not ansible_check_mode"
        )
        assert any("assets_checkout.stat.exists" in str(item) for item in when), (
            "the clone must be skipped when the checkout is already present"
        )

        git_removals = [
            task
            for task in _tasks_with_module("ansible.builtin.file")
            if str(_module(task).get("path", "")) == "{{ assets_checkout_root }}/.git"
        ]
        assert git_removals, "the pinned checkout's .git must be removed (deploy as data)"
        assert _module(git_removals[0]).get("state") == "absent"

        pin_copies = [
            task
            for task in _tasks_with_module("ansible.builtin.copy")
            if str(_module(task).get("dest", "")) == "{{ assets_pinned_file }}"
        ]
        assert len(pin_copies) == 1, "the tag must be recorded in {{ assets_pinned_file }}"
        assert str(_module(pin_copies[0]).get("content")) == "{{ assets_pinned_tag }}\n"

        checkout_stats = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if str(_module(task).get("path", "")) == "{{ assets_checkout_root }}/icons/schema.json"
        ]
        assert checkout_stats, "the checkout must be stat-probed (before and after the clone)"
        assert any(
            "assets_checkout_present.stat.isreg" in str(_module(task).get("that", ""))
            for task in _tasks_with_module("ansible.builtin.assert")
        ), "a fail-loud assert must guard the checkout before the first copy"

        # ORDER: every copy task comes after the clone.
        clone_index = tasks.index(clone)
        copy_indexes = [
            index
            for index, task in enumerate(tasks)
            if _module_key(task) in ("ansible.builtin.unarchive", "ansible.posix.synchronize")
        ]
        assert copy_indexes, "no copy task found"
        assert all(index > clone_index for index in copy_indexes), (
            "every copy must run AFTER the pinned checkout is fetched"
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
        """AC 13 / S1: no source is a literal path into the composition repo.

        Every corpus source is a var that derives from the install spine:
        `{{ item.source }}` (both copy loops; the values are
        `<install>/assets/<tag>/...`), `{{ assets_wallpapers_tarball }}`,
        `{{ assets_csg_templates_source }}`, or `{{ assets_checkout_root }}` /
        `{{ assets_pinned_file }}` on the fetch tasks. A source that starts
        with a literal `/` or names `dotfiles/` is the failure this locks
        (AC 13). Checks every task's module body, not a substring scan that
        skips tasks.
        """
        allowed_prefixes = (
            "{{ item.source }}",
            "{{ assets_wallpapers_tarball }}",
            "{{ assets_csg_templates_source }}",
            "{{ assets_checkout_root }}",
            "{{ install_dir | trim }}",
            "{{ assets_pinned_file }}",
        )
        for task in _load_tasks():
            module_key = _module_key(task)
            assert module_key is not None
            raw = task.get(module_key)
            if isinstance(raw, str):
                raw = {module_key: raw}
            assert isinstance(raw, dict)
            src = raw.get("src")
            if src is not None:
                assert str(src).startswith(allowed_prefixes), (
                    f"task {task.get('name')!r} source must derive from the install "
                    f"spine (AC 13); got {src!r}"
                )
                assert "dotfiles/" not in str(src), (
                    f"task {task.get('name')!r} still names a composition-repo tree: "
                    f"{src!r}"
                )


class TestAssetsVars:
    _REQUIRED_KEYS = {
        "assets_repo",
        "assets_pinned_tag",
        "assets_classes",
        "assets_checkout_root",
        "assets_pinned_file",
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

    def test_pin_block_mirrors_the_manifest(self) -> None:
        """AD-6: repo + tag + class map are mirrored from `assets:`."""
        data = _vars()
        manifest = yaml.safe_load(_MANIFEST_PATH.read_text())
        block = manifest["assets"]
        assert str(data["assets_repo"]) == block["repo"]
        assert str(data["assets_pinned_tag"]) == block["tag"]
        assert data["assets_classes"] == block["classes"], (
            "the role's class map must equal the manifest's `assets.classes`"
        )
        assert str(data["assets_checkout_root"]) == (
            "{{ install_dir | trim }}/assets/{{ assets_pinned_tag }}"
        )
        assert str(data["assets_pinned_file"]) == "{{ install_dir | trim }}/assets/pinned"

    def test_templates_schema_glob_matches_the_corpus_naming(self) -> None:
        """The corpus ships `<name>.vars.schema.json` siblings (catalog.yaml:
        `templates/**/*.vars.schema.json`), not a bare `vars.schema.json`. The
        manifest and the role mirror must use the same glob, and it must match
        the real filenames — the stale `**/vars.schema.json` matches none."""
        data = _vars()
        manifest_classes = yaml.safe_load(_MANIFEST_PATH.read_text())["assets"]["classes"]
        for label, classes in (
            ("manifest", manifest_classes),
            ("role mirror", data["assets_classes"]),
        ):
            glob = str(classes["templates"]["schema"])
            assert glob == "**/*.vars.schema.json", (
                f"{label} templates schema glob must match the corpus naming"
            )
            assert fnmatch.fnmatch("zsh/.zshrc.vars.schema.json", glob), (
                f"{label} glob {glob!r} does not match a real schema filename"
            )
            assert not fnmatch.fnmatch(
                "zsh/.zshrc.vars.schema.json", "**/vars.schema.json"
            ), "the retired bare-filename glob must not match the corpus files"

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
        manifest. (assets_copies ∪ assets_checkout_copies) names ∪
        {wallpapers, weg-effects} == manifest entry names; copies match by
        (name, kind, source); every copy target equals the kind→spine-segment
        mapping (with the config-in-spine relocation: csg-templates →
        config/color-scheme-generator/templates); the wallpaper tarball var
        equals the manifest wallpapers source; the manifest weg-effects entry
        has kind weg-effects and no source.

        S6: `csg-templates` reads the pinned csg checkout, so its source is an
        ABSOLUTE `<install>/cli-tools/csg/<tag>/...` path. S1: the three corpus
        entries read the pinned assets checkout (`{{ assets_checkout_root }}` →
        `<install>/assets/<tag>/...`), and the manifest carries the `assets:`
        block that names that pin. Parity compares the NORMALIZED paths
        (install root and both pins replaced by placeholders), asserts the
        role's pin mirrors equal the manifest tags, and asserts repo/tag/classes
        agree — so a drifted pin fails here, not only at provision time.
        """
        data = _vars()
        copies = [dict(item) for item in data["assets_copies"]] + [
            dict(item) for item in data["assets_checkout_copies"]
        ]
        manifest_entries = _manifest_entries()
        manifest = {item["name"]: item for item in manifest_entries}

        names = [item["name"] for item in manifest_entries]
        assert len(names) == len(set(names)), (
            "manifest entry names must be unique — a duplicate collapses the parity lock"
        )

        copy_names = {entry["name"] for entry in copies}
        assert copy_names | {"wallpapers", "weg-effects"} == set(manifest), (
            "the copy sets' names ∪ {wallpapers, weg-effects} must equal the "
            "manifest entry names (single source of truth)"
        )

        def _normalize(source: str, pin: str) -> str:
            """Replace the install root, the role vars and the pins with placeholders."""
            text = str(source).rstrip("/")
            text = text.replace(
                "{{ assets_csg_templates_source }}",
                str(data["assets_csg_templates_source"]).rstrip("/"),
            )
            text = text.replace(
                "{{ assets_checkout_root }}",
                "{{ install_dir | trim }}/assets/{{ assets_pinned_tag }}",
            )
            text = text.replace("{{ assets_csg_pinned_tag }}", "<tag>")
            text = text.replace("{{ assets_pinned_tag }}", "<tag>")
            text = text.replace("{{ install_dir | trim }}", "<install>")
            text = text.replace(str(data["assets_pinned_tag"]), "<tag>")
            if pin:
                text = text.replace(pin, "<tag>")
            return text

        kind_to_segment = {
            kind.value: _deploy_segment(kind)
            for kind in AssetKind
            if kind is not AssetKind.WALLPAPER and kind is not AssetKind.WEG_EFFECTS
        }
        csg_manifest_source = str(manifest["csg-templates"]["source"])
        csg_pin = csg_manifest_source.split("/cli-tools/csg/")[1].split("/", 1)[0]
        for entry in copies:
            manifest_entry = manifest[entry["name"]]
            assert entry["kind"] == manifest_entry["kind"], (
                f"copy {entry['name']!r} kind diverges from the manifest"
            )
            pin = csg_pin if entry["name"] == "csg-templates" else ""
            assert _normalize(entry["source"], pin) == _normalize(
                manifest_entry["source"], pin
            ), (
                f"copy {entry['name']!r} source diverges from the manifest "
                f"(role={entry['source']!r}, manifest={manifest_entry['source']!r})"
            )
            assert entry["target"] == kind_to_segment[entry["kind"]], (
                f"copy {entry['name']!r} target must equal the kind→spine-segment "
                "mapping (deferred #164 lock, derived from AssetKind with the "
                "config-in-spine relocation for csg-templates)"
            )

        assert str(data["assets_csg_pinned_tag"]) == csg_pin, (
            "assets_csg_pinned_tag must mirror the manifest csg pin — the "
            "csg-templates source is derived from it (spine AD-10/AD-11)"
        )

        assert _normalize(
            str(data["assets_wallpapers_tarball"]), ""
        ) == _normalize(str(manifest["wallpapers"]["source"]), "")
        assert manifest["wallpapers"]["kind"] == AssetKind.WALLPAPER.value, (
            "the manifest wallpapers entry kind must be the wallpaper kind"
        )
        assert manifest["weg-effects"]["kind"] == AssetKind.WEG_EFFECTS.value
        assert "source" not in manifest["weg-effects"], (
            "the manifest weg-effects entry must have no source (it is emitted, not copied)"
        )

        # AD-6: the manifest's `assets:` block and the role mirror agree.
        block = yaml.safe_load(_MANIFEST_PATH.read_text())["assets"]
        assert str(data["assets_repo"]) == block["repo"]
        assert str(data["assets_pinned_tag"]) == block["tag"]
        assert data["assets_classes"] == block["classes"]
        # The three corpus entries name the SAME pin the block declares, so a
        # tag bump that edits `assets.tag` but not a source fails here.
        for name in ("wallpapers", "icon-templates", "icon-mappings"):
            assert str(manifest[name]["source"]).startswith(
                f"{{{{ install_dir | trim }}}}/assets/{block['tag']}/"
            ), f"manifest entry {name!r} does not name the manifest assets tag"

    def test_csg_templates_source_resolves_to_pinned_checkout(self) -> None:
        """S6/AD-10: the csg-templates asset is copied FROM the pinned csg
        checkout, not from the (deleted) in-tree package.

        The catalog lives in the cli_tools checkout at
        `<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates/`,
        which exists by the time this role runs because cli-tools.yaml precedes
        assets.yaml. This case renders the role vars with the csg pin and asserts
        the resolved source (a) is the tag-qualified checkout, (b) does NOT name
        the retired in-tree path, and (c) is backed by a fail-loud existence
        assert so a missing/mis-pinned checkout cannot deploy nothing silently.
        """
        data = _vars()
        manifest_entries = _manifest_entries()
        csg_entry = next(e for e in manifest_entries if e["name"] == "csg-templates")
        cli_manifest = yaml.safe_load(
            (_ANSIBLE_DIR.parents[2] / "dotfiles" / "provisioning" / "cli-tools.yaml").read_text()
        )
        csg_cli = next(e for e in cli_manifest["entries"] if e.get("name") == "csg")
        pin = str(csg_cli["tag"])

        assert str(data["assets_csg_pinned_tag"]) == pin, (
            "the assets role must mirror the csg pin from the CLI manifest"
        )

        install = "/tmp/opencode/assets-pin-check"
        source = str(data["assets_csg_templates_source"])
        source = source.replace("{{ install_dir | trim }}", install)
        source = source.replace("{{ assets_csg_pinned_tag }}", str(data["assets_csg_pinned_tag"]))
        assert source == (
            f"{install}/cli-tools/csg/{pin}/src/color_scheme_generator/defaults/templates"
        ), f"resolved csg-templates source is wrong: {source!r}"
        assert "src/cli-tools" not in source, (
            "the csg-templates source must not name the retired in-tree tree"
        )
        assert "src/cli-tools" not in str(csg_entry["source"]), (
            "the manifest csg-templates source must not name the retired tree"
        )

        checkout_copy = next(
            e for e in data["assets_checkout_copies"] if e["name"] == "csg-templates"
        )
        assert str(checkout_copy["source"]).startswith("{{ assets_csg_templates_source }}"), (
            "the copy must read the resolved checkout var (single source for the path)"
        )
        assert str(checkout_copy["target"]) == "config/color-scheme-generator/templates"

        # The dependency is explicit: a stat + assert on the resolved dir, so a
        # missing checkout (cli-tools never ran) fails loud instead of
        # synchronizing nothing over the previous catalog.
        asserts = [
            task
            for task in _tasks_with_module("ansible.builtin.assert")
            if "assets_csg_templates_dir.stat.isdir" in str(_module(task).get("that", ""))
        ]
        assert asserts, (
            "the assets role must assert the pinned csg template catalog exists "
            "before copying from it (spine AD-10)"
        )
        stats = [
            task
            for task in _tasks_with_module("ansible.builtin.stat")
            if str(_module(task).get("path", "")) == "{{ assets_csg_templates_source }}"
        ]
        assert stats, "the existence probe must stat the resolved checkout source"
        for task in asserts:
            assert task.get("when") == "not ansible_check_mode"


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
