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
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "symlinks"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_MANIFEST_PATH = _REPO_ROOT / "dotfiles" / "provisioning" / "symlinks.yaml"

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


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


def _source_stat_tasks() -> list[dict[str, object]]:
    """The source-presence stat loop: stat on `dotfiles/config/`, looping
    {{ symlinks_links }}, registering symlinks_source_check."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.stat")
        if "symlinks_source_check" == str(task.get("register"))
    ]


def _source_assert_tasks() -> list[dict[str, object]]:
    """The source-presence assert consuming symlinks_source_check."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.assert")
        if "symlinks_source_check" in str(_module(task).get("that", ""))
    ]


def _link_create_task() -> dict[str, object]:
    """The single symlink creation task: `state: link`, `force: false`,
    looping {{ symlinks_links }}."""
    matches = [
        task
        for task in _tasks_with_module("ansible.builtin.file")
        if str(_module(task).get("state")) == "link"
    ]
    assert len(matches) == 1, f"expected exactly one state: link task; found {len(matches)}"
    return matches[0]


def _dir_ensure_tasks() -> list[dict[str, object]]:
    """The XDG config home dir-ensure task: `state: directory` on
    {{ symlinks_xdg_config_home }} (no loop — the home is a single path)."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.file")
        if str(_module(task).get("state")) == "directory"
    ]


def _resolve_stat_tasks() -> list[dict[str, object]]:
    """The resolve-check stat loops: stat on `{{ symlinks_xdg_config_home }}/`,
    looping {{ symlinks_links }}."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.stat")
        if "{{ symlinks_xdg_config_home }}/" in str(_module(task).get("path", ""))
    ]


def _resolve_assert_tasks() -> list[dict[str, object]]:
    """The resolve-check asserts consuming symlinks_dest_check_*."""
    return [
        task
        for task in _tasks_with_module("ansible.builtin.assert")
        if "symlinks_dest_check_" in str(_module(task).get("that", ""))
    ]


class TestSymlinksRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestSymlinksTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_source_stat(self) -> None:
        """Role contract: the FIRST task is the fail-loud SOURCE-presence stat
        (stat on dotfiles/config/) — and explicitly NOT the install_dir assert
        this role deliberately omits (it consumes no install_dir)."""
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.stat", (
            "the first task must be the fail-loud source-presence stat "
            "(role contract — NOT an install_dir assert, which this role omits)"
        )
        module = _module(first)
        assert "dotfiles/config/" in str(module.get("path", "")), (
            "the source stat must check a dotfiles/config/ source"
        )
        assert module.get("follow") is True, (
            "the source stat must pass follow: true explicitly "
            "(stat does not resolve links by default)"
        )

    def test_source_stat_pair_loops_symlinks_links(self) -> None:
        """Fail-loud direct-run prerequisite: the source stat loop registers
        symlinks_source_check and the assert checks the registered results —
        both derive their count from symlinks_links | length, never a hardcoded
        literal, and both are UNGATED (repo content is static — a missing
        source must abort even under --check)."""
        stat_tasks = _source_stat_tasks()
        assert stat_tasks, "no source-presence stat loop task found"
        for task in stat_tasks:
            assert "{{ symlinks_links }}" in str(task.get("loop", ""))
            assert task.get("register") == "symlinks_source_check"
            assert task.get("when") is None, (
                "source stat must be ungated (static repo content — abort under --check too)"
            )

        assert_tasks = _source_assert_tasks()
        assert assert_tasks, "no source-presence assert task found"
        for task in assert_tasks:
            that = str(_module(task).get("that", ""))
            assert "symlinks_links | length" in that, (
                "source assert must derive its count from symlinks_links | length, "
                "not a hardcoded literal"
            )
            assert "symlinks_source_check" in that
            assert task.get("when") is None, "source assert must be ungated (static repo content)"

    def test_link_create_task_contract(self) -> None:
        """AC 2 + 4: the link task is `ansible.builtin.file` `state: link` with
        an ABSOLUTE `src` prefixed {{ symlinks_repo_root }}/dotfiles/config/
        (relative srcs resolve relative to the link file), a `dest` prefixed
        {{ symlinks_xdg_config_home }}/, `force: false` (the AC 4 no-clobber
        lock — a real dir/file at the dest fails loudly instead of converting),
        a loop over symlinks_links, NO `creates:`, and NO check-mode gate (the
        file module has FULL check-mode support)."""
        task = _link_create_task()
        module = _module(task)
        assert module.get("force") is False, (
            "link task must set force: false (AC 4 — never clobber a real dir/file)"
        )
        assert str(module.get("src", "")).startswith("{{ symlinks_repo_root }}/dotfiles/config/"), (
            "link src must derive from symlinks_repo_root/dotfiles/config/"
        )
        assert str(module.get("dest", "")).startswith("{{ symlinks_xdg_config_home }}/"), (
            "link dest must derive from symlinks_xdg_config_home"
        )
        assert "{{ symlinks_links }}" in str(task.get("loop", ""))
        assert _creates_value(task) is None, (
            "link task must not carry creates: (state: link is module-level idempotent)"
        )
        assert task.get("when") is None, (
            "link task must NOT be --check-gated (file state: link has full "
            "check-mode support — verified)"
        )

    def test_resolve_check_pair_all_gated(self) -> None:
        """AC 3 done-criterion 9: TWO stat loops (follow: false then follow:
        true) + TWO asserts (islnk then exists), ALL FOUR gated
        `when: not ansible_check_mode` (dests are absent on a fresh target
        under --check)."""
        stat_tasks = _resolve_stat_tasks()
        assert len(stat_tasks) == 2, (
            f"expected exactly 2 resolve-check stat loops (follow false + true); "
            f"found {len(stat_tasks)}"
        )
        by_follow: dict[bool, list[dict[str, object]]] = {True: [], False: []}
        for task in stat_tasks:
            assert task.get("when") == "not ansible_check_mode", (
                "resolve-check stat must be gated when: not ansible_check_mode"
            )
            assert "{{ symlinks_links }}" in str(task.get("loop", ""))
            follow = _module(task).get("follow")
            assert isinstance(follow, bool)
            by_follow[follow].append(task)
        assert len(by_follow[True]) == 1, "exactly one follow: true stat loop"
        assert len(by_follow[False]) == 1, "exactly one follow: false stat loop"

        assert_tasks = _resolve_assert_tasks()
        assert len(assert_tasks) == 2, (
            f"expected exactly 2 resolve-check asserts (islnk + exists); found {len(assert_tasks)}"
        )
        thats = [str(_module(t).get("that", "")) for t in assert_tasks]
        for task, that in zip(assert_tasks, thats):
            assert task.get("when") == "not ansible_check_mode", (
                "resolve-check assert must be gated when: not ansible_check_mode"
            )
            assert "symlinks_links | length" in that, (
                "resolve-check assert must derive its count from symlinks_links | length"
            )
        assert any("stat.islnk" in t for t in thats), (
            "the follow: false assert must check stat.islnk (proves it is a symlink, not a copy)"
        )
        assert any("stat.exists" in t for t in thats), (
            "the follow: true assert must check stat.exists (proves it resolves — "
            "a dangling link reports exists: false when followed)"
        )

    def test_xdg_config_home_dir_ensure_ungated(self) -> None:
        """AC 2 direct-run self-containment: a `file` `state: directory` task
        re-ensures {{ symlinks_xdg_config_home }} (the file module does NOT
        create link-dest parents; the filesystem role created it on the
        bootstrap chain). Natively check-safe — must NOT be --check-gated."""
        dir_tasks = _dir_ensure_tasks()
        assert dir_tasks, "no XDG config home dir-ensure task found"
        for task in dir_tasks:
            assert str(_module(task).get("path", "")) == "{{ symlinks_xdg_config_home }}"
            assert task.get("when") is None, (
                "XDG dir ensure is check-safe natively — must NOT be --check-gated"
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
        (`{{ symlinks_repo_root }}`, `{{ symlinks_xdg_config_home }}`,
        `ansible_facts.env`) — no literal absolute path is baked into any
        task's module body OR into vars/main.yml."""
        safe_vars = (
            "symlinks_repo_root",
            "symlinks_xdg_config_home",
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


class TestSymlinksVars:
    _REQUIRED_KEYS = {
        "symlinks_repo_root",
        "symlinks_xdg_config_home",
        "symlinks_links",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_repo_root_mirrors_assets_repo_root(self) -> None:
        data = _vars()
        assert str(data["symlinks_repo_root"]) == "{{ playbook_dir }}/../../../.."

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The link destinations must resolve to the SAME location the filesystem
        role (2.5) created: honors $XDG_CONFIG_HOME with the spec default
        `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["symlinks_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_symlinks_links_parity_with_manifest(self) -> None:
        """Parity lock: the role var exactly mirrors the manifest by
        (name, target) so they can never silently diverge (AC 2)."""
        data = _vars()
        role_entries = [dict(item) for item in data["symlinks_links"]]
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


class TestSymlinksPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "symlinks.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["symlinks"]
        assert "become" not in play, "symlinks playbook must not use become"
        assert "become_user" not in play, "symlinks playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the symlinks playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "symlinks playbook must not use group_by"
        assert "groups" not in play, "symlinks playbook must not group hosts"

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

    def test_playbook_executes_and_creates_symlinks(self) -> None:
        """Regression guard (review finding 2026-08-12 discipline): the role
        must ACTUALLY create symlinks — structural tests alone could not catch a
        silent no-op. Run the real playbook against a temp HOME/XDG home and
        assert every link lands, resolves, and points at the real repo source;
        re-running must be a no-op (AC 4 idempotency at runtime)."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            home.mkdir()
            xdg.mkdir()

            env = dict(os.environ)
            env["HOME"] = str(home)
            env["XDG_CONFIG_HOME"] = str(xdg)
            env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [ansible_playbook, str(self._PATH)],
                    capture_output=True,
                    text=True,
                    env=env,
                )

            first = run()
            assert first.returncode == 0, first.stdout + first.stderr

            for entry in _manifest_entries():
                target = xdg / entry["target"]
                source = _REPO_ROOT / "dotfiles" / "config" / entry["name"]
                assert target.is_symlink(), f"{target} was never linked (silent no-op?)"
                assert target.exists(), (
                    f"{target} is a dangling link — the repo source {source} is missing?"
                )
                assert Path(os.readlink(target)).resolve() == source.resolve(), (
                    f"{target} must point at the real repo source {source}"
                )

            second = run()
            assert second.returncode == 0, second.stdout + second.stderr
            assert "changed=0" in second.stdout, (
                "re-running the playbook must be a no-op (AC 4 — existing "
                "symlinks left unchanged); recap:\n" + second.stdout
            )
