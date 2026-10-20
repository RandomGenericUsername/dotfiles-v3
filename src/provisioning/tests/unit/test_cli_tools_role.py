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
    """The tasks that build CLI container images (argv `<cli> install ...`)."""
    return [
        task
        for task in _load_tasks()
        if (_argv_of(task) or [])[1:2] == ["install"]
    ]


def _cli_tools_image_builds() -> list[dict[str, str]]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    return [dict(item) for item in data["cli_tools_image_builds"]]


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

    def test_btop_studio_launcher_exports_repo_root(self) -> None:
        """The btop Theme Studio launcher mirrors icme: export the checkout via
        BTOP_STUDIO_REPO_ROOT and run the dedicated ags-btop-studio instance."""
        template = (_ROLES_DIR / "templates" / "btop-theme-studio.j2").read_text()
        assert "export BTOP_STUDIO_REPO_ROOT=" in template, (
            "the studio launcher must hand the checkout to the app explicitly"
        )
        assert 'INSTANCE="btop-theme-studio"' in template
        assert "${HOME}/.config/ags-btop-studio" in template

    def test_rofi_launcher_is_a_keybound_toggle(self) -> None:
        """`rofi-ui` is the single open/close entrypoint for the SUPER+D bind.

        It closes a live rofi (the pidfile rofi writes + a /proc comm check so
        a stale/recycled PID is never signalled, then SIGTERM) and launches
        otherwise. The KEY must not appear in the script — that is exactly what
        keeps open and close in sync when the bind in keybindings.lua changes.
        """
        template = (_ROLES_DIR / "templates" / "rofi-ui.j2").read_text()
        assert "-pid" in template, "rofi-ui must pin the pidfile rofi writes"
        assert "kill -TERM" in template, "rofi-ui must close a live rofi"
        assert "/proc/" in template and "comm" in template, (
            "rofi-ui must confirm the pid is still rofi before signalling"
        )
        assert "exec rofi -config" in template, "rofi-ui must launch rofi when down"
        assert "SUPER" not in template, (
            "the key must live only in keybindings.lua; rofi-ui must stay key-agnostic"
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

    def test_capture_tool_is_not_installed_by_this_role(self) -> None:
        """v0.4.0: the capture-tool backend ships in the pinned ags-apps unit.

        cli_tools runs BEFORE ags-apps on the bootstrap chain, so it cannot
        install or assert the CLI anymore. The retired copy task must not come
        back: it would install this checkout's old backend over the unit's
        pinned one (two sources of truth).
        """
        tasks_text = (_ROLES_DIR / "tasks" / "main.yml").read_text()
        assert "src/gui-tools/capture-tool" not in tasks_text, (
            "cli_tools must not install the capture-tool backend — the ags_apps "
            "role links it from the unit"
        )
        assert not any(
            "capture-tool" in str(task.get("name", "")) for task in _load_tasks()
        ), "no cli_tools task may install or verify capture-tool anymore"
        assert not any(
            "command -v capture-tool" in str(task.get(_module_key(task) or "", ""))
            for task in _load_tasks()
        ), "the capture-tool PATH assertion moved to the ags_apps role (after the link)"

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


class TestCliToolsCodexShadowCleanup:
    """provision-ai-ides-and-clis: the AUR openai-codex-bin owns /usr/bin/codex,
    but OpenAI's standalone installer leaves a self-updating symlink at
    <bin>/codex that precedes /usr/bin on PATH. The role removes it — guarded
    so a user's own codex is never touched — and drops the standalone payload
    while preserving ~/.codex config/auth."""

    @staticmethod
    def _shadow_stat_task() -> dict[str, object]:
        tasks = [
            task
            for task in _load_tasks()
            if task.get("register") == "cli_tools_codex_shadow"
        ]
        assert len(tasks) == 1, "expected exactly one stat of the codex shadow"
        return tasks[0]

    def test_shadow_symlink_is_removed_only_when_standalone(self) -> None:
        stat_task = self._shadow_stat_task()
        module = stat_task.get(_module_key(stat_task) or "", {})
        assert module.get("path") == "{{ cli_tools_bin_dir }}/codex"

        removals = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.file"
            and task.get(_module_key(task), {}).get("state") == "absent"
            and task.get(_module_key(task), {}).get("path") == "{{ cli_tools_bin_dir }}/codex"
        ]
        assert len(removals) == 1, "expected exactly one codex-shadow removal task"
        when = str(removals[0].get("when"))
        assert "not ansible_check_mode" in when, "shadow removal must be check-mode gated"
        assert "cli_tools_codex_shadow.stat.islnk" in when, (
            "must only remove a symlink (never a user's regular file)"
        )
        assert "/.codex/packages/standalone/" in when, (
            "must only remove the standalone installer's symlink"
        )

    def test_standalone_payload_removed_with_config_preserved(self) -> None:
        checks = [
            task
            for task in _load_tasks()
            if task.get("register") == "cli_tools_codex_standalone"
        ]
        assert len(checks) == 1, "expected a standalone-payload existence check"
        payload_module = checks[0].get(_module_key(checks[0]) or "", {})
        assert payload_module.get("path") == "{{ ansible_facts.env.HOME }}/.codex/packages/standalone"

        removals = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.file"
            and task.get(_module_key(task), {}).get("state") == "absent"
            and task.get(_module_key(task), {}).get("path") == "{{ ansible_facts.env.HOME }}/.codex/packages"
        ]
        assert len(removals) == 1, "expected the standalone packages payload removal"
        when = str(removals[0].get("when"))
        assert "not ansible_check_mode" in when
        assert "cli_tools_codex_standalone.stat.exists" in when
        # ~/.codex/config.toml and auth must never be named for removal.
        for task in removals:
            assert "config.toml" not in str(task), "user codex config must be preserved"


class TestCliToolsImageBuildTasks:
    def test_image_build_task_loops_over_configured_clis(self) -> None:
        """Container mode (product decision 2026-08-12) requires the cli_tools
        role to build the csg AND weg container images — `uv tool install`
        only installs the host-side launchers."""
        tasks = _image_build_tasks()
        assert len(tasks) == 1, "expected a single image-build loop task"
        assert tasks[0].get("loop") == "{{ cli_tools_image_builds }}", (
            "image build must iterate the configured list so csg and weg are "
            "both built"
        )
        names = {b["name"] for b in _cli_tools_image_builds()}
        assert {"csg", "weg"} <= names, "csg and weg must both be image-built"

    def test_image_build_task_passes_container_engine(self) -> None:
        tasks = _image_build_tasks()
        assert tasks, "expected an image-build task"
        argv = _argv_of(tasks[0])
        assert "--container-engine" in argv
        declared = "{{ container_runtime_engine }}"
        assert argv[argv.index("--container-engine") + 1] == declared, (
            "image-build task must pass --container-engine from the DECLARED "
            "engine {{ container_runtime_engine }} — the single source of truth "
            "shared with the rendered settings"
        )

    def test_image_build_task_passes_package_context(self) -> None:
        """AD-5/AD-7: the build context is the CLI's own package dir, not the
        dotfiles repo root."""
        tasks = _image_build_tasks()
        assert tasks, "expected an image-build task"
        argv = _argv_of(tasks[0])
        assert "--context" in argv, "the build verb now takes --context"
        assert argv[argv.index("--context") + 1] == (
            "{{ cli_tools_repo_root }}/{{ item.source }}"
        ), "image-build task must pass the item's package dir as the context"
        assert "--source-root" not in argv, (
            "--source-root is now a deprecated alias; provisioning uses --context"
        )

    def test_image_build_task_is_check_mode_gated(self) -> None:
        """Command modules execute under --check, so the image build must be
        gated `when: not ansible_check_mode` (dry-run must stay dry)."""
        tasks = _image_build_tasks()
        assert tasks, "expected an image-build task"
        for task in tasks:
            assert "not ansible_check_mode" in str(task.get("when", "")), (
                f"image-build task {task.get('name')!r} must be check-mode gated"
            )

    def test_image_build_task_has_no_creates_guard(self) -> None:
        """Image EXISTENCE does not imply FRESHNESS: a `creates:` guard would
        skip rebuilding a stale image (the exact defect this chain fixes)."""
        tasks = _image_build_tasks()
        assert tasks, "expected an image-build task"
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


class TestCliToolsEngineAssertionBattery:
    """Option 2b: one DECLARED engine (container_runtime_engine), validated by a
    four-layer fail-loud battery — domain → presence → usability → capability
    smoke. There is NO detection probe and NO resolved-engine set_fact."""

    def test_no_detection_probe_and_no_resolved_engine_set_fact(self) -> None:
        for task in _load_tasks():
            body = str(task.get(_module_key(task) or "", ""))
            assert "command -v podman" not in body, (
                "engine detection must be removed — the engine is DECLARED, "
                "never probed for a podman/docker preference"
            )
            assert _module_key(task) != "ansible.builtin.set_fact", (
                "no set_fact may resolve an engine — container_runtime_engine is "
                "declared in group_vars/all.yml"
            )

    def test_layer1_domain_assert_is_ungated_and_names_both_remedies(self) -> None:
        asserts = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.assert"
            and 'container_runtime_engine in ["podman", "docker"]'
            in str(task.get("ansible.builtin.assert", ""))
        ]
        assert asserts, "expected the Layer-1 domain assert"
        for task in asserts:
            assert task.get("when") is None, (
                "the domain assert must be UNGATED (runs under --check too)"
            )
            msg = str(task.get("ansible.builtin.assert", {}).get("fail_msg", ""))
            assert "container_runtime_engine" in msg
            assert "-e container_runtime_engine=" in msg
            assert "DOTFILES_CONTAINER_ENGINE=" in msg

    @staticmethod
    def _task_with_register(register: str) -> dict[str, object]:
        matches = [task for task in _load_tasks() if task.get("register") == register]
        assert len(matches) == 1, f"expected exactly one task registering {register!r}"
        return matches[0]

    @staticmethod
    def _asserts_mentioning(fragment: str) -> list[dict[str, object]]:
        return [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.assert"
            and fragment in str(task.get("ansible.builtin.assert", ""))
        ]

    def test_layer2_presence_probe_and_gated_assert(self) -> None:
        probe = self._task_with_register("cli_tools_engine_presence")
        assert _module_key(probe) == "ansible.builtin.shell", (
            "command -v is a shell builtin — the presence probe must use shell"
        )
        assert "command -v {{ container_runtime_engine }}" in str(
            probe.get("ansible.builtin.shell", "")
        )
        assert probe.get("changed_when") is False
        assert probe.get("failed_when") is False
        assert probe.get("when") == "not ansible_check_mode", (
            "the presence probe must be gated (shell never runs under --check)"
        )
        env = probe.get("environment")
        assert isinstance(env, dict)
        assert env.get("PATH", "").startswith("{{ cli_tools_bin_dir }}:")

        asserts = self._asserts_mentioning("cli_tools_engine_presence.rc == 0")
        assert asserts, "expected the presence assert"
        for task in asserts:
            assert task.get("when") == "not ansible_check_mode"

    def test_layer3_usability_probe_is_bounded_and_assert_gated(self) -> None:
        probe = self._task_with_register("cli_tools_engine_usability")
        assert _module_key(probe) == "ansible.builtin.shell"
        assert "timeout 30 {{ container_runtime_engine }} info" in str(
            probe.get("ansible.builtin.shell", "")
        ), "usability probe must be bounded (`timeout 30 ... info`)"
        assert probe.get("changed_when") is False
        assert probe.get("failed_when") is False
        assert probe.get("when") == "not ansible_check_mode"

        asserts = self._asserts_mentioning("cli_tools_engine_usability.rc == 0")
        assert asserts, "expected the usability assert"
        for task in asserts:
            assert task.get("when") == "not ansible_check_mode"

    def test_layer4_capability_smoke_battery(self) -> None:
        # Probe file (tempfile) — gated.
        tempfile_tasks = [task for task in _load_tasks() if task.get("register") == "probe"]
        assert len(tempfile_tasks) == 1, "expected exactly one smoke probe tempfile task"
        tempfile_task = tempfile_tasks[0]
        assert _module_key(tempfile_task) == "ansible.builtin.tempfile"
        tempfile_body = tempfile_task.get("ansible.builtin.tempfile", {})
        assert tempfile_body.get("state") == "file"
        assert tempfile_body.get("prefix") == "weg-container-smoke-"
        assert tempfile_task.get("when") == "not ansible_check_mode"

        # Copy content into the probe file — gated.
        copy_tasks = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.copy"
            and task.get("ansible.builtin.copy", {}).get("dest") == "{{ probe.path }}"
        ]
        assert len(copy_tasks) == 1, "expected the smoke probe content write"
        copy_task = copy_tasks[0]
        copy_body = copy_task.get("ansible.builtin.copy", {})
        assert "weg-container-smoke" in str(copy_body.get("content", ""))
        assert copy_body.get("mode") == "0644"
        assert copy_task.get("when") == "not ansible_check_mode"

        # The run itself: argv-form command, gated, probes changed/failed false.
        run = self._task_with_register("cli_tools_engine_smoke")
        assert _module_key(run) == "ansible.builtin.command", (
            "the smoke run must use argv-form command (NOT shell) so quoting is safe"
        )
        argv = _argv_of(run)
        assert argv is not None
        assert "run" in argv and "--rm" in argv
        assert argv[argv.index("-e") + 1] == "WEG_SMOKE=ok"
        assert "{{ cli_tools_engine_smoke_image }}" in argv
        assert any(":/smoke/probe.txt:ro" in arg for arg in argv), (
            "the smoke must bind-mount the probe file read-only"
        )
        assert argv[0] == "timeout", "the smoke run must be bounded"
        assert run.get("changed_when") is False
        assert run.get("failed_when") is False
        assert run.get("when") == "not ansible_check_mode"

        asserts = self._asserts_mentioning("'SMOKE_OK' in (cli_tools_engine_smoke.stdout")
        assert asserts, "expected the smoke success assert"
        for task in asserts:
            assert task.get("when") == "not ansible_check_mode"
            msg = str(task.get("ansible.builtin.assert", {}).get("fail_msg", ""))
            assert "cli_tools_engine_smoke.rc" in msg
            assert "cli_tools_engine_smoke.stderr" in msg

        # Cleanup — gated file state absent.
        cleanups = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.file"
            and task.get("ansible.builtin.file", {}).get("path") == "{{ probe.path }}"
            and task.get("ansible.builtin.file", {}).get("state") == "absent"
        ]
        assert len(cleanups) == 1, "expected the smoke probe cleanup"
        assert cleanups[0].get("when") == "not ansible_check_mode"

    def test_battery_tasks_are_all_named_and_never_use_become(self) -> None:
        battery_registers = {
            "cli_tools_engine_presence",
            "cli_tools_engine_usability",
            "cli_tools_engine_smoke",
        }
        for task in _load_tasks():
            assert task.get("name"), "every task must carry a name"
            if task.get("register") in battery_registers:
                assert "become" not in task
                assert "become_user" not in task


class TestCliToolsVars:
    def test_vars_parse_with_required_keys(self) -> None:
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert isinstance(data, dict), "vars/main.yml must parse to a dict"
        assert {"cli_tools_repo_root", "cli_tools_bin_dir", "cli_tools"}.issubset(set(data))

    def test_engine_is_declared_not_detected(self) -> None:
        """Option 2b: the engine is DECLARED once
        (`container_runtime_engine` in group_vars/all.yml, shipped default
        podman) and consumed by BOTH the build and the rendered settings — the
        role carries no detection probe and no resolved-engine set_fact, and the
        old override escape hatch is gone."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        assert "cli_tools_container_engine" not in data, (
            "the role must not pin its own engine — container_runtime_engine in "
            "group_vars/all.yml is the single source of truth"
        )
        assert "cli_tools_container_engine_override" not in data, (
            "the old override escape hatch must be deleted (superseded by the "
            "declared container_runtime_engine)"
        )
        assert data.get("cli_tools_engine_smoke_image"), (
            "the Layer-4 smoke must use a pinned image var"
        )

        # No detection probe and no resolved-engine set_fact anywhere in tasks.
        for task in _load_tasks():
            assert "command -v podman" not in str(task.get(_module_key(task) or "", "")), (
                "engine detection must be gone — the engine is DECLARED"
            )
            assert _module_key(task) != "ansible.builtin.set_fact", (
                "no set_fact may resolve an engine — it is declared in group_vars"
            )

        # The build consumes the DECLARED engine.
        argv = _argv_of(_image_build_tasks()[0])
        assert argv is not None
        assert argv[argv.index("--container-engine") + 1] == "{{ container_runtime_engine }}"

    def test_image_builds_list_contains_only_container_mode_clis(self) -> None:
        """csg and weg are both container-mode CLIs and must be image-built;
        itr has no container mode and must not be."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
        builds = [dict(item) for item in data["cli_tools_image_builds"]]
        names = {b["name"] for b in builds}
        assert names == {"csg", "weg"}, "image builds must be exactly the container-mode CLIs"
        for build in builds:
            assert build.get("source"), (
                f"{build['name']}: image build must name its package dir as the build context"
            )

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


class TestHyprPanoLauncher:
    """The clipboard overlay launcher must reveal the overlay on ONE press.

    The overlay starts hidden (``visible={false}``, keymode ON_DEMAND), so
    starting the instance alone shows nothing. Since ags-apps v0.3.0 the app
    registers a ``requestHandler`` (toggle/show/hide/popup-close); the launcher
    drives it: warm -> ``ags request toggle``, cold -> background ``ags run``
    then ``ags request show``. A bare (or ``exec``ed) ``ags run`` would leave
    the window hidden and force the user to press twice.
    """

    _TEMPLATE = _ROLES_DIR / "templates" / "hypr-pano-ui.j2"

    @classmethod
    def _code(cls) -> str:
        """The template with comment lines stripped.

        The assertions below must lock the SCRIPT, not the prose: the header
        documents the same command spellings the body runs, so a naive
        substring check would pass on a comment alone.
        """
        return "\n".join(
            line
            for line in cls._TEMPLATE.read_text().splitlines()
            if not line.lstrip().startswith("#")
        )

    def test_warm_press_toggles_through_the_request_handler(self) -> None:
        code = self._code()
        assert 'INSTANCE="hypr-pano"' in code
        assert 'DIR="${HOME}/.config/ags-hypr-pano"' in code
        assert 'LOG="${HOME}/.local/state/ags/hypr-pano.log"' in code
        assert 'ags request "$1" -i "$INSTANCE"' in code, (
            "the launcher must issue `ags request` against the hypr-pano instance"
        )
        assert "request toggle" in code, (
            "a warm press must toggle through the app's requestHandler, not "
            "the window command"
        )

    def test_cold_start_backgrounds_ags_run_then_requests_show(self) -> None:
        code = self._code()
        assert 'ags run -d "$DIR" --log-file "$LOG" &' in code, (
            "the cold start must run in the BACKGROUND so this shell survives "
            "to issue the reveal request"
        )
        assert "request show" in code, (
            "the cold start must reveal the freshly started (hidden) overlay"
        )

    def test_launcher_never_execs_ags_run(self) -> None:
        assert "exec ags run" not in self._code(), (
            "`exec` replaces the shell, so the follow-up `request show` could "
            "never run; the cold start must background `ags run`"
        )

    def test_launcher_preserves_the_guard_rails(self) -> None:
        code = self._code()
        assert "set -uo pipefail" in code
        assert "ags quit -i" in code, (
            "a failed request must quit the zombie instance before cold-starting"
        )
        assert "ags list" in code, "start-if-down needs the bus check"
        assert "timeout 8 ags request" in code, (
            "the request must be bounded so a wedged instance cannot hang the bind"
        )

    # -- executable sandbox: prove the cold path issues `show` AFTER `run` --

    _STUB = """\
#!/usr/bin/env bash
# Stub `ags`: log every call, and simulate an instance that only registers on
# the bus once `run` has been invoked. `$AGS_STUB_FAIL_REQUEST` forces one
# request name to fail, to exercise the zombie-quit fallback.
printf '%s\\n' "$*" >> "$AGS_STUB_LOG"
case "$1" in
  list)
    [ -f "$AGS_STUB_STATE/started" ] && echo "hypr-pano"
    ;;
  run)
    : > "$AGS_STUB_STATE/started"
    ;;
  quit)
    rm -f "$AGS_STUB_STATE/started"
    ;;
  request)
    if [ -n "${AGS_STUB_FAIL_REQUEST:-}" ] && [ "$2" = "$AGS_STUB_FAIL_REQUEST" ]; then
      exit 1
    fi
    ;;
esac
exit 0
"""

    def _run_launcher(
        self, tmp_path: Path, *, warm: bool, fail_request: str = ""
    ) -> list[str]:
        """Execute the launcher against a stub `ags`; return the call log."""
        home = tmp_path / "home"
        (home / ".local" / "state" / "ags").mkdir(parents=True)
        state = tmp_path / "state"
        state.mkdir()
        if warm:
            (state / "started").touch()
        log = tmp_path / "calls.log"
        log.touch()
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "ags"
        stub.write_text(self._STUB)
        stub.chmod(0o755)
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        env["AGS_STUB_LOG"] = str(log)
        env["AGS_STUB_STATE"] = str(state)
        if fail_request:
            env["AGS_STUB_FAIL_REQUEST"] = fail_request
        result = subprocess.run(
            ["bash", str(self._TEMPLATE)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return log.read_text().splitlines()

    def test_cold_start_issues_run_then_request_show(self, tmp_path: Path) -> None:
        calls = self._run_launcher(tmp_path, warm=False)
        joined = "\n".join(calls)
        assert any(c.startswith("run -d") for c in calls), joined
        assert "request show -i hypr-pano" in calls, joined
        run_at = next(i for i, c in enumerate(calls) if c.startswith("run -d"))
        show_at = calls.index("request show -i hypr-pano")
        assert run_at < show_at, (
            "the reveal request must come AFTER the instance is started:\n" + joined
        )
        assert not any("request toggle" in c for c in calls), joined

    def test_warm_press_requests_toggle_without_starting(self, tmp_path: Path) -> None:
        calls = self._run_launcher(tmp_path, warm=True)
        joined = "\n".join(calls)
        assert "request toggle -i hypr-pano" in calls, joined
        assert not any(c.startswith("run ") for c in calls), joined

    def test_failed_warm_request_falls_back_to_cold_start(self, tmp_path: Path) -> None:
        calls = self._run_launcher(tmp_path, warm=True, fail_request="toggle")
        joined = "\n".join(calls)
        assert "request toggle -i hypr-pano" in calls, joined
        assert "quit -i hypr-pano" in calls, joined
        assert any(c.startswith("run -d") for c in calls), joined
        assert "request show -i hypr-pano" in calls, joined
