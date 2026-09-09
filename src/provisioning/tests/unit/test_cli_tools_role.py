from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_packages_role.py``: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-5 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "cli_tools"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_MANIFEST_PATH = _REPO_ROOT / "dotfiles" / "provisioning" / "cli-tools.yaml"

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


def _creates_value(task: dict[str, object]) -> object | None:
    """Return the ``creates`` value whether declared top-level or in args."""
    direct = task.get("creates")
    if direct is not None:
        return direct
    args = task.get("args")
    if isinstance(args, dict):
        return args.get("creates")
    return None


def _manifest_entries() -> list[dict[str, str]]:
    data = yaml.safe_load(_MANIFEST_PATH.read_text())
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    return [dict(item) for item in entries]


def _install_tasks() -> list[dict[str, object]]:
    """The tasks that run `uv tool install` for each manifest entry.

    Only the FIRST-install task (the one carrying the `creates:` guard)
    counts; the upgrade task (`--force`, 2026-09-07) is separate and has its
    own locks."""
    return [
        task
        for task in _load_tasks()
        if "uv tool install" in str(task.get(_module_key(task) or "", ""))
        if "--force" not in str(task.get(_module_key(task) or "", ""))
    ]


def _argv_of(task: dict[str, object]) -> list[str] | None:
    """Return the argv list of a task, or None when the module body is not an
    argv-form command (e.g. free-form `command: string` tasks)."""
    module = task.get(_module_key(task) or "", {})
    if not isinstance(module, dict):
        return None
    argv = module.get("argv")
    if not isinstance(argv, list):
        return None
    return [str(item) for item in argv]


def _image_build_tasks() -> list[dict[str, object]]:
    """The tasks that build CLI container images (argv starting `csg install`)."""
    return [task for task in _load_tasks() if (_argv_of(task) or [])[:2] == ["csg", "install"]]


class TestCliToolsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_icme_launcher_exports_repo_root(self) -> None:
        """The ICME launcher must export ICME_REPO_ROOT, not just `cd`.

        `ags run -d` re-roots the app process into the app dir, so the
        editor's cwd ancestor walk can never find a checkout — without the
        explicit export the session silently falls back to spine defaults.
        """
        template = (
            _ROLES_DIR / "templates" / "icon-color-mapping-editor.j2"
        ).read_text()
        assert "export ICME_REPO_ROOT=" in template, (
            "launcher must hand the checkout to the app explicitly; "
            "`cd` alone is defeated by `ags run -d` re-rooting"
        )


class TestCliToolsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_install_tasks_cover_all_manifest_entries(self) -> None:
        """Locks AC2: every manifest entry must be installed by a `uv tool
        install` task. Accepts either a single loop task over cli_tools or the
        spec-sanctioned three unrolled per-entry tasks."""
        install_tasks = _install_tasks()
        manifest_entries = _manifest_entries()
        if len(install_tasks) == 1:
            task = install_tasks[0]
            assert _module_key(task) == "ansible.builtin.command"
            assert task.get("loop") == "{{ cli_tools }}"
        else:
            assert len(install_tasks) == len(manifest_entries), (
                "expected one `uv tool install` task per manifest entry "
                f"({len(manifest_entries)}), found {len(install_tasks)}"
            )
            for task in install_tasks:
                assert _module_key(task) == "ansible.builtin.command"

    def test_install_task_creates_guard_is_dry_run_and_idempotent(self) -> None:
        """Locks AC5: `creates: {{ cli_tools_bin_dir }}/{{ item.name }}` is the
        ONLY mechanism on the install task — check-mode-safe by construction
        (filesystem check, not a registered rc)."""
        install_tasks = _install_tasks()
        assert install_tasks, "no uv tool install task found"
        for task in install_tasks:
            creates = _creates_value(task)
            assert creates == "{{ cli_tools_bin_dir }}/{{ item.name }}", (
                f"install task {task.get('name')!r} must carry "
                "creates: '{{ cli_tools_bin_dir }}/{{ item.name }}'"
            )

    def test_install_task_not_gated_on_presence_check_rc(self) -> None:
        """Locks the Story 2.3 check-mode lesson: under --check a skipped
        `command -v` registers rc=0, so gating the install on a presence-check
        rc would report `skipped` instead of would-change."""
        install_tasks = _install_tasks()
        assert install_tasks, "no uv tool install task found"
        for task in install_tasks:
            when = str(task.get("when", ""))
            assert "uv_check" not in when and "command -v" not in when, (
                f"install task {task.get('name')!r} must not gate on a presence-check rc"
            )

    def test_upgrade_tasks_repin_from_current_source(self) -> None:
        """Upgrade-after-install lock (2026-09-07): a `--force` re-pin task
        must exist for every manifest entry, WITHOUT a `creates:` guard (the
        first-install `creates:` guard alone let already-provisioned machines
        run stale tool envs forever), gated off check-mode, and pinned to the
        same UV_TOOL_BIN_DIR as the install task."""
        upgrade_tasks = [
            task
            for task in _load_tasks()
            if "--force" in str(task.get(_module_key(task) or "", ""))
        ]
        manifest_entries = _manifest_entries()
        assert len(upgrade_tasks) == len(manifest_entries) or (
            len(upgrade_tasks) == 1
        ), "expected one upgrade loop task (or one per entry)"
        task = upgrade_tasks[0]
        module = task.get(_module_key(task))
        assert isinstance(module, str) and "--force" in module
        environment = task.get("environment")
        assert isinstance(environment, dict)
        assert environment["UV_TOOL_BIN_DIR"] == "{{ cli_tools_bin_dir }}"
        assert task.get("when") == "not ansible_check_mode"
        creates = _creates_value(task)
        assert creates is None, "upgrade task must NOT carry creates: (must re-pin every run)"

    def test_uv_presence_check_is_shell_based(self) -> None:
        """F1 lock: `command -v uv` must run via ansible.builtin.shell — the
        command module execs argv directly and `command` is a shell builtin,
        not a binary, so it returns rc=2 on every host and the assert below
        would fail even when uv is installed."""
        checks = [
            task
            for task in _load_tasks()
            if "command -v uv" in str(task.get(_module_key(task) or "", ""))
        ]
        assert checks, "no `command -v uv` presence check task found"
        for task in checks:
            assert _module_key(task) == "ansible.builtin.shell", (
                "uv presence check must use ansible.builtin.shell (command -v is a shell builtin)"
            )
            assert task.get("failed_when") is False
            assert task.get("changed_when") is False

    def test_verify_task_prepends_bin_dir_to_path(self) -> None:
        """Locks AC3 + F1: a verify task resolves each binary with the uv bin
        dir prepended to PATH in the run context. `command -v` is a shell
        builtin (no /usr/bin/command executable), so it MUST run via
        ansible.builtin.shell, never ansible.builtin.command."""
        verify_tasks = [
            task
            for task in _load_tasks()
            if "command -v {{ item.name }}" in str(task.get(_module_key(task) or "", ""))
        ]
        assert verify_tasks, "no `command -v {{ item.name }}` verify task found"
        for task in verify_tasks:
            assert _module_key(task) == "ansible.builtin.shell", (
                "verify task must use ansible.builtin.shell (command -v is a shell builtin)"
            )
            assert task.get("changed_when") is False
            env = task.get("environment")
            assert isinstance(env, dict), "verify task must set environment"
            assert env.get("PATH", "").startswith("{{ cli_tools_bin_dir }}:"), (
                "verify task must prepend cli_tools_bin_dir to PATH (AC 3)"
            )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: `uv tool install` targets the
        intended user, never root (running as root would install into
        /root/.local/bin and AC 3 would be silently false)."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_repo_paths_hardcoded(self) -> None:
        """Every source is `{{ cli_tools_repo_root }}/...`, never an absolute
        repo path baked into the task."""
        install_tasks = _install_tasks()
        assert install_tasks, "no uv tool install task found"
        for task in install_tasks:
            command = str(task.get("ansible.builtin.command", ""))
            assert "uv tool install" in command, (
                f"install task {task.get('name')!r} must run `uv tool install`"
            )
            assert "{{ cli_tools_repo_root }}/" in command, (
                f"install task {task.get('name')!r} must use "
                "'{{ cli_tools_repo_root }}/{{ item.source }}'"
            )
            assert "{{ item.source }}" in command
            assert "{{ cli_tools_repo_root }}/" in command.replace("'", ""), (
                "repo source must be interpolated, never an absolute literal"
            )


class TestCliToolsImageBuildTasks:
    def test_image_build_task_exists_for_csg(self) -> None:
        """Container mode (product decision 2026-08-12) requires the cli_tools
        role to build the csg container image — `uv tool install` only installs
        the host-side launcher."""
        tasks = _image_build_tasks()
        assert tasks, "expected a `csg install` image-build task"
        csg_tasks = [t for t in tasks if _argv_of(t)[0] == "csg"]
        assert csg_tasks, "expected a `csg install` task"

    def test_image_build_task_passes_container_engine(self) -> None:
        tasks = _image_build_tasks()
        assert tasks, "expected a `csg install` image-build task"
        csg = [t for t in tasks if _argv_of(t)[0] == "csg"][0]
        argv = _argv_of(csg)
        assert "--container-engine" in argv
        resolved = "{{ cli_tools_container_engine }}"
        assert argv[argv.index("--container-engine") + 1] == resolved, (
            "image-build task must pass --container-engine from the RESOLVED "
            "engine (override-or-detection, podman preferred, then docker) — "
            "never a hardcoded engine"
        )

    def test_container_engine_detected_with_fail_loud_assert(self) -> None:
        """Engine detection (podman → docker → fail) is a read-only probe
        (skipped when the override escape hatch is set); a set_fact resolves the
        engine from override-or-probe (trimmed), and a gated assert fails loud
        when neither is usable."""
        probes = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.shell"
            and "command -v podman" in str(task.get("ansible.builtin.shell", ""))
            and "command -v docker" in str(task.get("ansible.builtin.shell", ""))
        ]
        assert probes, "expected a podman/docker detection probe"
        for task in probes:
            assert task.get("register") == "cli_tools_engine_check"
            assert task.get("failed_when") is False
            assert task.get("changed_when") is False
            assert "cli_tools_container_engine_override" in str(task.get("when", "")), (
                "probe must be skipped when the engine override is set"
            )

        set_facts = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.set_fact"
            and "cli_tools_container_engine" in str(task.get("ansible.builtin.set_fact", {}))
        ]
        assert set_facts, "expected a set_fact resolving cli_tools_container_engine"

        asserts = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.assert"
            and "cli_tools_container_engine" in str(task.get("ansible.builtin.assert", {}))
        ]
        assert asserts, "expected an assert on the resolved engine"
        for task in asserts:
            assert task.get("when") == "not ansible_check_mode", (
                "engine assert must be gated when: not ansible_check_mode"
            )

    def test_image_build_task_passes_source_root(self) -> None:
        tasks = _image_build_tasks()
        assert tasks, "expected a `csg install` image-build task"
        csg = [t for t in tasks if _argv_of(t)[0] == "csg"][0]
        argv = _argv_of(csg)
        assert "--source-root" in argv
        assert argv[argv.index("--source-root") + 1] == "{{ cli_tools_repo_root }}", (
            "image-build task must pass --source-root = cli_tools_repo_root "
            "(deterministic build context on the provisioning path)"
        )

    def test_image_build_task_is_check_mode_gated(self) -> None:
        """Command modules execute under --check, so the image build must be
        gated `when: not ansible_check_mode` (dry-run must stay dry)."""
        tasks = _image_build_tasks()
        assert tasks, "expected a `csg install` image-build task"
        for task in tasks:
            assert "not ansible_check_mode" in str(task.get("when", "")), (
                f"image-build task {task.get('name')!r} must be check-mode gated"
            )

    def test_image_build_task_has_no_creates_guard(self) -> None:
        """Image EXISTENCE does not imply FRESHNESS: a `creates:` guard would
        skip rebuilding a stale image (the exact defect this chain fixes)."""
        tasks = _image_build_tasks()
        assert tasks, "expected a `csg install` image-build task"
        for task in tasks:
            assert _creates_value(task) is None, (
                f"image-build task {task.get('name')!r} must NOT carry creates: "
                "(existence != freshness)"
            )

    def test_no_become_on_image_build_tasks(self) -> None:
        tasks = _image_build_tasks()
        for task in tasks:
            assert "become" not in task, (
                f"image-build task {task.get('name')!r} must not use become "
                "(rootless podman builds into the user storage)"
            )


class TestCliToolsVars:
    def test_vars_parse_with_required_keys(self) -> None:
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert isinstance(data, dict), "vars/main.yml must parse to a dict"
        assert {"cli_tools_repo_root", "cli_tools_bin_dir", "cli_tools"}.issubset(set(data))

    def test_container_engine_detected_at_runtime_not_pinned(self) -> None:
        """podman/docker are DOCUMENTED DEPENDENCIES: the engine is resolved at
        runtime (override-or-detection, podman preferred, then docker, then fail
        loud) — the RESOLVED engine is never a vars value, and the override
        escape hatch defaults to empty (auto-detect). A machine with only docker
        must not false-fail on a hardcoded podman."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert "cli_tools_container_engine" not in data, (
            "the resolved engine must come from set_fact (override-or-detection), "
            "never pinned in vars"
        )
        assert data.get("cli_tools_container_engine_override") == "", (
            "the override escape hatch must default to empty (auto-detect)"
        )

    def test_image_builds_list_contains_only_container_mode_clis(self) -> None:
        """Only csg is image-built today (itr has no container mode; weg is only
        consumed via local `dump-effects` by the assets role)."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        builds = [dict(item) for item in data["cli_tools_image_builds"]]
        assert {"name": "csg"} in builds
        names = {b["name"] for b in builds}
        assert names <= {"csg", "weg"}, "image builds must be container-mode CLIs only"

    def test_cli_tools_parity_with_manifest(self) -> None:
        """Parity lock: the role var exactly mirrors the manifest by
        (name, source) so they can never silently diverge (AC 2)."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        role_entries = [dict(item) for item in data["cli_tools"]]
        manifest_entries = _manifest_entries()
        assert len(role_entries) == len(manifest_entries)
        assert {tuple(e.items()) for e in role_entries} == {
            tuple(e.items()) for e in manifest_entries
        }

    def test_cli_tools_bin_dir_defaults_under_home(self) -> None:
        """uv's bin-dir resolution, in order: UV_TOOL_BIN_DIR -> XDG_BIN_HOME ->
        $HOME/.local/bin. The DECLARED value must fall back to $HOME/.local/bin
        when neither XDG/uv var is set, and must honor the XDG overrides so the
        PATH prepend + `creates` match where uv actually installs (fixes the
        custom-XDG-layout failure where uv wrote to $XDG_DATA_HOME/uv/tools but
        the role looked only at $HOME/.local/bin)."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        value = str(data["cli_tools_bin_dir"])
        assert "UV_TOOL_BIN_DIR" in value
        assert "XDG_BIN_HOME" in value
        assert "ansible_facts.env.HOME + '/.local/bin'" in value

    def test_bin_dir_uses_non_deprecated_env_fact(self) -> None:
        """F4 lock: use ansible_facts.env (not the deprecated top-level
        ansible_env fact injected via INJECT_FACTS_AS_VARS), which hard-breaks
        on ansible-core >= 2.24."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert "ansible_facts.env.HOME" in str(data["cli_tools_bin_dir"])
        assert "{{ ansible_env." not in str(data["cli_tools_bin_dir"])


class TestCliToolsPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "cli-tools.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["cli_tools"]
        assert "become" not in play, "cli-tools playbook must not use become"

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
