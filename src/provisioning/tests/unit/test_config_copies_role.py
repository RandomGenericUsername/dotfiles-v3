from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_assets_role.py`` / ``test_compositor_configs_role.py``:
    anchored on ``pyproject.toml`` so the sibling project's ``ansible/`` tree
    in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-4 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "config_copies"
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


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


def _install_dir_assert_task() -> dict[str, object]:
    """The fail-loud install_dir seam assert: the FIRST task (config-in-spine
    2026-08-16 — the role now consumes install_dir; dests live at
    <install>/config/)."""
    tasks = _load_tasks()
    assert tasks, "tasks/main.yml must not be empty"
    first = tasks[0]
    assert _module_key(first) == "ansible.builtin.assert", (
        "the first task must be the fail-loud install_dir assert (role contract)"
    )
    return first


def _fact_gathering_assert_task() -> dict[str, object]:
    """The fail-loud fact-gathering guard: an assert on ansible_facts.env.HOME
    with a gather_facts fail_msg (the SECOND task — vars still derive from
    ansible_facts.env)."""
    tasks = _load_tasks()
    assert tasks, "tasks/main.yml must not be empty"
    assert _module_key(tasks[0]) == "ansible.builtin.assert", (
        "the first task must be the fail-loud install_dir assert (role contract)"
    )
    matches = [
        task
        for task in _assert_tasks()
        if "ansible_facts.env.HOME is defined" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, "expected exactly one fact-gathering assert on ansible_facts.env.HOME"
    return matches[0]


def _non_empty_guard_task() -> dict[str, object]:
    """The non-empty guard on config_copies_entries (prevents vacuous 0 == 0)."""
    matches = [
        task
        for task in _assert_tasks()
        if "config_copies_entries | length > 0" in str(_module(task).get("that", ""))
    ]
    assert len(matches) == 1, f"expected exactly one non-empty guard assert; found {len(matches)}"
    return matches[0]


def _source_stat_tasks() -> list[dict[str, object]]:
    """The source-presence stat loop: stat on `dotfiles/config/`, looping
    {{ config_copies_entries }}, registering config_copies_source_check."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.stat")
        if "config_copies_source_check" == str(task.get("register"))
    ]


def _source_assert_tasks() -> list[dict[str, object]]:
    """The source-presence assert consuming config_copies_source_check."""
    return [
        task
        for task in _assert_tasks()
        if "config_copies_source_check" in str(_module(task).get("that", ""))
    ]


def _copy_task() -> dict[str, object]:
    """The single directory-copy task."""
    matches = _tasks_with_module("ansible.builtin.copy")
    assert len(matches) == 1, f"expected exactly one copy task; found {len(matches)}"
    return matches[0]


def _spine_home_dir_ensure_tasks() -> list[dict[str, object]]:
    """The config-in-spine home dir-ensure task: `state: directory` on
    {{ config_copies_spine_config_dir }} (no loop — the spine root is a single
    path)."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.file")
        if str(_module(task).get("state")) == "directory"
        and str(_module(task).get("path")) == "{{ config_copies_spine_config_dir }}"
    ]


def _target_dir_ensure_tasks() -> list[dict[str, object]]:
    """The per-target dir-ensure tasks: `state: directory` on
    {{ config_copies_spine_config_dir }}/<target>, looping config_copies_entries."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.file")
        if str(_module(task).get("state")) == "directory"
        and "{{ config_copies_spine_config_dir }}/" in str(_module(task).get("path", ""))
        and str(_module(task).get("path")) != "{{ config_copies_spine_config_dir }}"
    ]


def _resolve_stat_tasks() -> list[dict[str, object]]:
    """The resolve-check stat loops: stat on `{{ config_copies_xdg_config_home }}/`,
    looping {{ config_copies_entries }}."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.stat")
        if "config_copies_dest_check" == str(task.get("register"))
    ]


def _resolve_assert_tasks() -> list[dict[str, object]]:
    """The resolve-check asserts consuming config_copies_dest_check."""
    return [
        task
        for task in _assert_tasks()
        if "config_copies_dest_check" in str(_module(task).get("that", ""))
    ]


class TestConfigCopiesRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestConfigCopiesTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Role contract (config-in-spine 2026-08-16): the FIRST task is the
        fail-loud install_dir seam assert, verbatim from the sibling roles —
        this role now CONSUMES install_dir (destinations live at
        <install>/config/), so an undefined spine root aborts first."""
        first = _install_dir_assert_task()
        module = _module(first)
        that = str(module.get("that", ""))
        assert "install_dir is defined" in that, "the first task must assert install_dir is defined"
        assert "install_dir | trim | length > 0" in that

    def test_second_task_is_fail_loud_fact_gathering_assert(self) -> None:
        """Role contract: the SECOND task is the fail-loud fact-gathering guard
        (vars still derive from ansible_facts.env HOME/XDG derivations) — NOT an
        install_dir-only role. Without gather_facts: true the XDG derivation
        dies with an opaque traceback, so the friendly guard stays early."""
        second = _fact_gathering_assert_task()
        module = _module(second)
        that = str(module.get("that", ""))
        assert "ansible_facts.env.HOME is defined" in that, (
            "the guard must assert ansible_facts.env.HOME is defined"
        )
        fail_msg = str(module.get("fail_msg", ""))
        assert "gather_facts" in fail_msg, (
            "the guard's fail_msg must name the gather_facts: true requirement"
        )

    def test_non_empty_guard_prevents_vacuous_passes(self) -> None:
        """All count asserts derive from `config_copies_entries | length`, so an
        empty list would pass every guard (0 == 0) and silently disable the
        role — a non-empty assert makes the desync fail loudly."""
        task = _non_empty_guard_task()
        assert task.get("when") is None, "the non-empty guard must be ungated"

    def test_source_stat_pair_loops_config_copies_entries(self) -> None:
        """Fail-loud direct-run prerequisite: the source stat loop registers
        config_copies_source_check and the assert checks the registered results —
        both derive their count from config_copies_entries | length, never a
        hardcoded literal, and both are UNGATED (repo content is static — a
        missing source must abort even under --check)."""
        stat_tasks = _source_stat_tasks()
        assert stat_tasks, "no source-presence stat loop task found"
        for task in stat_tasks:
            assert "{{ config_copies_entries }}" in str(task.get("loop", ""))
            assert task.get("register") == "config_copies_source_check"
            assert task.get("when") is None, (
                "source stat must be ungated (static repo content — abort under --check too)"
            )
            assert _module(task).get("follow") is True, (
                "source stat must pass follow: true explicitly"
            )

        assert_tasks = _source_assert_tasks()
        assert assert_tasks, "no source-presence assert task found"
        for task in assert_tasks:
            that = str(_module(task).get("that", ""))
            assert "config_copies_entries | length" in that, (
                "source assert must derive its count from config_copies_entries | length, "
                "not a hardcoded literal"
            )
            assert "config_copies_source_check" in that
            assert "stat.isdir" in that, (
                "source assert must check stat.isdir — a regular file at a "
                "source path must fail loudly, not be silently copied"
            )
            assert task.get("when") is None, "source assert must be ungated (static repo content)"

    def test_copy_task_contract(self) -> None:
        """AC 2 + 4: the copy task is `ansible.builtin.copy` with a trailing-`/`
        `src` prefixed {{ config_copies_repo_root }}/dotfiles/config/ (contents-
        into-dest semantics), a trailing-`/` `dest` prefixed
        {{ config_copies_spine_config_dir }}/ (config-in-spine 2026-08-16 —
        dests land at <install>/config/<target>), `remote_src: true`
        (localhost mirror of the assets role), a loop over config_copies_entries,
        NO `creates:`, and NO check-mode gate (the copy module has FULL
        check-mode support). NOT `force: false` — a directory src + force: false
        + a pre-existing dest dir is a silent no-op (2.9 review finding); the
        default force: true + checksums is the idempotency mechanism."""
        task = _copy_task()
        module = _module(task)
        assert module.get("force") is not False, (
            "copy task must NOT set force: false (directory src + force: false + "
            "pre-existing dest dir is a silent no-op — 2.9 review finding); the "
            "default force: true + checksums is the idempotency mechanism"
        )
        src = str(module.get("src", ""))
        assert src.startswith("{{ config_copies_repo_root }}/dotfiles/config/"), (
            "copy src must derive from config_copies_repo_root/dotfiles/config/"
        )
        assert src.endswith("/"), (
            "copy src must end with '/' (contents-into-dest semantics — no accidental nested dir)"
        )
        dest = str(module.get("dest", ""))
        assert dest.startswith("{{ config_copies_spine_config_dir }}/"), (
            "copy dest must derive from config_copies_spine_config_dir"
        )
        assert dest.endswith("/"), "copy dest must end with '/'"
        assert module.get("remote_src") is True, (
            "copy must set remote_src: true (localhost mirror of the assets role)"
        )
        assert "{{ config_copies_entries }}" in str(task.get("loop", ""))
        assert _creates_value(task) is None, (
            "copy task must not carry creates: (a gate would freeze a stale copy)"
        )
        assert task.get("when") is None, (
            "copy task must NOT be --check-gated (copy has full check-mode support — verified)"
        )

    def test_resolve_check_pair_all_gated(self) -> None:
        """AC 3 + runtime independence (pivot): ONE stat loop with follow: false
        + ONE assert on stat.isdir, both gated `when: not ansible_check_mode`
        (dests are absent on a fresh target under --check). follow: false makes
        a symlink report islnk: true / isdir: false, so the isdir count proves
        every dest is a REAL directory — not a copy and not a link back into
        the repo."""
        stat_tasks = _resolve_stat_tasks()
        assert len(stat_tasks) == 1, (
            f"expected exactly 1 resolve-check stat loop (follow: false); found {len(stat_tasks)}"
        )
        for task in stat_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "resolve-check stat must be gated when: not ansible_check_mode"
            )
            assert "{{ config_copies_entries }}" in str(task.get("loop", ""))
            assert _module(task).get("follow") is False, (
                "resolve stat must pass follow: false (a symlink reports islnk: true "
                "/ isdir: false — only real directories pass)"
            )

        assert_tasks = _resolve_assert_tasks()
        assert len(assert_tasks) == 1, (
            f"expected exactly 1 resolve-check assert; found {len(assert_tasks)}"
        )
        for task in assert_tasks:
            that = str(_module(task).get("that", ""))
            assert task.get("when") == "not ansible_check_mode", (
                "resolve-check assert must be gated when: not ansible_check_mode"
            )
            assert "config_copies_entries | length" in that, (
                "resolve-check assert must derive its count from config_copies_entries | length"
            )
            assert "stat.isdir" in that, (
                "resolve-check assert must check stat.isdir (real dirs, not symlinks)"
            )

    def test_dir_ensure_tasks_ungated(self) -> None:
        """AC 2 direct-run self-containment: `file` `state: directory` re-ensures
        {{ config_copies_spine_config_dir }} AND each target dir under the
        config-in-spine home (copy does NOT create the top-level dest parent).
        Natively check-safe — must NOT be --check-gated."""
        home_tasks = _spine_home_dir_ensure_tasks()
        assert home_tasks, "no config-in-spine home dir-ensure task found"
        for task in home_tasks:
            assert task.get("when") is None, (
                "spine home dir ensure is check-safe natively — must NOT be --check-gated"
            )

        target_tasks = _target_dir_ensure_tasks()
        assert target_tasks, "no per-target dir-ensure task found"
        for task in target_tasks:
            assert "{{ config_copies_entries }}" in str(task.get("loop", "")), (
                "target dir-ensure must loop config_copies_entries"
            )
            assert task.get("when") is None, (
                "target dir ensure is check-safe natively — must NOT be --check-gated"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere —
        everything the role writes lives under the user's config home."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path-bearing reference derives from the role vars
        (`{{ config_copies_repo_root }}`, `{{ config_copies_xdg_config_home }}`,
        `ansible_facts.env`) — no literal absolute path is baked into any
        task's module body OR into vars/main.yml."""
        safe_vars = (
            "config_copies_repo_root",
            "config_copies_xdg_config_home",
            "config_copies_spine_config_dir",
            "config_copies_entries",
            "install_dir",
            "ansible_facts.env",
        )
        for source_name, source_data in (
            ("tasks", _load_tasks()),
            ("vars", _vars()),
        ):
            text = str(source_data)
            for token in text.split():
                if token.startswith("/") and not any(var in token for var in safe_vars):
                    raise AssertionError(
                        f"{source_name}/main.yml hardcodes an absolute path: {token!r} (trim lock)"
                    )


class TestConfigCopiesVars:
    _REQUIRED_KEYS = {
        "config_copies_repo_root",
        "config_copies_xdg_config_home",
        "config_copies_spine_config_dir",
        "config_copies_entries",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_repo_root_mirrors_assets_repo_root(self) -> None:
        data = _vars()
        assert str(data["config_copies_repo_root"]) == "{{ playbook_dir }}/../../../.."

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The copy destinations must resolve to the SAME location the filesystem
        role (2.5) created: honors $XDG_CONFIG_HOME with the spec default
        `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["config_copies_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_config_copies_entries_parity_with_manifest(self) -> None:
        """Parity lock: the role var exactly mirrors the manifest by
        (name, target) so they can never silently diverge (AC 2)."""
        data = _vars()
        role_entries = [dict(item) for item in data["config_copies_entries"]]
        manifest_entries = _manifest_entries()
        assert len(role_entries) == len(manifest_entries)
        assert {tuple(e.items()) for e in role_entries} == {
            tuple(e.items()) for e in manifest_entries
        }

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        data = _vars()
        text = str(data)
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text


class TestConfigCopiesPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "config-copies.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["config_copies"]
        assert "become" not in play, "config-copies playbook must not use become"
        assert "become_user" not in play, "config-copies playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the config-copies playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "config-copies playbook must not use group_by"
        assert "groups" not in play, "config-copies playbook must not group hosts"

    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = dict(os.environ)
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [ansible_playbook, "--syntax-check", str(self._PATH)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_executes_and_creates_config_copies(self) -> None:
        """Regression guard (review finding 2026-08-12 discipline): the role
        must ACTUALLY copy configs — structural tests alone could not catch a
        silent no-op. Run the real playbook against a temp HOME/XDG home and
        install_dir and assert every dest is a REAL directory in the
        config-in-spine home (<install>/config/<target> — not a symlink; the
        runtime-independence guarantee), contains the repo source's entries,
        and re-running is a no-op (AC 4 idempotency at runtime)."""
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

            env = dict(os.environ)
            env["HOME"] = str(home)
            env["XDG_CONFIG_HOME"] = str(xdg)
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")

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
                )

            first = run()
            assert first.returncode == 0, first.stdout + first.stderr

            for entry in _manifest_entries():
                target = install / "config" / entry["target"]
                source = _REPO_ROOT / "dotfiles" / "config" / entry["name"]
                assert target.is_dir(), f"{target} was never copied (silent no-op?)"
                assert not target.is_symlink(), (
                    f"{target} must be a REAL directory, not a symlink (runtime "
                    "independence — the machine must work after the repo is deleted)"
                )
                assert set(os.listdir(target)) == set(os.listdir(source)), (
                    f"{target} contents do not match the repo source {source}"
                )

            second = run()
            assert second.returncode == 0, second.stdout + second.stderr
            assert "changed=0" in second.stdout, (
                "re-running the playbook must be a no-op (AC 4 — unchanged "
                "configs left alone); recap:\n" + second.stdout
            )
