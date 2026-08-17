from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_compositor_configs_role.py``: anchored on ``pyproject.toml``
    so the sibling project's ``ansible/`` tree in a shared workspace is never
    matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-8 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "settings"
_TEMPLATES_DIR = _ROLES_DIR / "templates"

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

_EXPECTED_TEMPLATES = {
    "csg": "csg-settings.toml.j2",
    "weg": "weg-settings.toml.j2",
    "itr": "itr-settings.toml.j2",
}

# Trim lock (review finding 2026-08-12): detect hardcoded absolute paths even
# when they are quoted (`"/home/user/x"`) or glued after a Jinja expression
# (`}}/home/user/generated`) — the old token `startswith("/")` scan missed
# both. A fragment is hardcoded unless a seam var (install_dir / the XDG home
# var / ansible_facts.env) appears within 80 chars before it.
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


def _render_task() -> dict[str, object]:
    """The single render task: the `template` task looping over
    {{ settings_files }} (default force: true — content-compare idempotent)."""
    matches = [
        task
        for task in _tasks_with_module("ansible.builtin.template")
        if "settings_files" in str(task.get("loop", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one render task looping over settings_files; found {len(matches)}"
    )
    return matches[0]


def _dir_ensure_task() -> dict[str, object]:
    """The config-dir ensure task: `file` `state: directory` looping over
    {{ settings_config_dirs }}."""
    matches = [
        task
        for task in _tasks_with_module("ansible.builtin.file")
        if "settings_config_dirs" in str(task.get("loop", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one config-dir ensure task looping over "
        f"settings_config_dirs; found {len(matches)}"
    )
    return matches[0]


class TestSettingsRoleTree:
    _REQUIRED_FILES = (
        "tasks/main.yml",
        "vars/main.yml",
        "templates/csg-settings.toml.j2",
        "templates/weg-settings.toml.j2",
        "templates/itr-settings.toml.j2",
    )

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestSettingsTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Role contract (AC 6 — the pre-render validation): the FIRST task is
        an `ansible.builtin.assert` requiring the install_dir seam extra-var —
        the identical verbatim copy of the 2.5/2.6/2.7/2.9 assert (no aliasing
        into a var)."""
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

    def test_config_dirs_ensured_via_file_directory_ungated(self) -> None:
        """Direct-run self-containment: a `file` `state: directory` task
        re-ensures the three per-tool config dirs (template does NOT create
        dest parents; the filesystem role did not create the tool subdirs).
        Natively check-safe — must NOT be --check-gated."""
        task = _dir_ensure_task()
        assert _module(task)["state"] == "directory"
        assert "settings_config_dirs" in str(task.get("loop", ""))
        assert task.get("when") is None, (
            "dir ensure is check-safe natively — must NOT be --check-gated"
        )

    def test_render_task_contract(self) -> None:
        """AC 2-5, 7: the render task is `ansible.builtin.template` with
        `src: "{{ item.template }}"` (resolved relative to
        roles/settings/templates/) and `dest` derived from
        {{ settings_spine_config_dir }}/ ending in settings.toml, looping over
        {{ settings_files }}. Default `force: true` (content-compare idempotent
        — a template edit propagates on re-apply). NO `creates:` and NOT
        check-gated (template module has FULL check-mode support — 2.9-verified
        pattern)."""
        task = _render_task()
        module = _module(task)
        assert module.get("force") is not False, (
            "render task must NOT set force: false (the rendered settings files "
            "ARE the overwrite candidates — default force: true + content-compare "
            "is the idempotency mechanism)"
        )
        assert str(module.get("src")) == "{{ item.template }}", (
            "render src must be {{ item.template }} (resolved relative to "
            "roles/settings/templates/)"
        )
        assert str(module.get("dest")) == "{{ item.dest }}", (
            "render dest must be {{ item.dest }} (the per-tool dest derives from "
            "settings_spine_config_dir in vars/main.yml)"
        )
        for file_ in _vars()["settings_files"]:
            dest = str(file_["dest"])
            assert dest.startswith("{{ settings_spine_config_dir }}/"), (
                "settings_files dest must derive from settings_spine_config_dir"
            )
            assert dest.endswith("settings.toml"), "settings_files dest must end with settings.toml"
        assert "settings_files" in str(task.get("loop", ""))
        assert _creates_value(task) is None, (
            "render task must not carry creates: (a gate would freeze a stale "
            "path and silently break a spine-path change)"
        )
        assert task.get("when") is None, (
            "render task must NOT be --check-gated (template has full check-mode "
            "support — verified)"
        )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere —
        everything the role writes lives under the user's config home and
        install_dir."""
        for task in _load_tasks():
            assert "become" not in task, (
                f"task {task.get('name')!r} must not use become (user-scoped role)"
            )
            assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path-bearing reference derives from the role vars
        (`{{ settings_spine_config_dir }}`, `{{ settings_xdg_config_home }}`,
        `{{ install_dir | trim }}`, `ansible_facts.env`) — no literal absolute
        path is baked into any task's module body OR into vars/main.yml.
        Hardened (review finding 2026-08-12): the scan catches quoted literals
        (`"/home/user/x"`) and paths glued after a Jinja `}}` that the old
        `startswith("/")` token check missed."""
        seam_vars = (
            "settings_xdg_config_home",
            "settings_spine_config_dir",
            "settings_config_dirs",
            "settings_files",
            "install_dir",
            "ansible_facts.env",
        )
        for source_name, source_data in (
            ("tasks", _load_tasks()),
            ("vars", _vars()),
        ):
            hit = _hardcoded_absolute_path(str(source_data), seam_vars)
            assert hit is None, (
                f"{source_name}/main.yml hardcodes an absolute path: {hit!r} (trim lock)"
            )


class TestSettingsVars:
    _REQUIRED_KEYS = {
        "settings_xdg_config_home",
        "settings_spine_config_dir",
        "settings_config_dirs",
        "settings_files",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The render destinations must resolve to the SAME location the
        filesystem role (2.5) created: honors $XDG_CONFIG_HOME with the spec
        default `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env
        (F4 lock)."""
        data = _vars()
        value = str(data["settings_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_no_settings_repo_root_key(self) -> None:
        """Design lock: unlike assets/compositor_configs/config_copies, the
        settings role has NO repo-root var — the templates ARE the role content
        and `src:` resolves relative to roles/settings/templates/."""
        data = _vars()
        assert "settings_repo_root" not in data, (
            "settings role must NOT define settings_repo_root — the templates are "
            "role-internal content (no repo-file sources)"
        )

    def test_settings_files_are_exactly_three(self) -> None:
        """AC 1: settings_files has exactly the three {name, template, dest}
        entries (csg/weg/itr) with matching template filenames."""
        data = _vars()
        files = list(data["settings_files"])
        assert len(files) == 3, (
            f"settings_files must have exactly 3 entries (csg/weg/itr); found {len(files)}"
        )
        names = {str(f["name"]) for f in files}
        assert names == {"csg", "weg", "itr"}, (
            f"settings_files names must be {{csg, weg, itr}}; found {names}"
        )
        for file_ in files:
            template = str(file_["template"])
            assert template == _EXPECTED_TEMPLATES[str(file_["name"])], (
                f"settings_files[{file_['name']}].template must be "
                f"{_EXPECTED_TEMPLATES[str(file_['name'])]}; got {template}"
            )
            assert (_TEMPLATES_DIR / template).is_file(), (
                f"template {template} missing from roles/settings/templates/"
            )
            dest = str(file_["dest"])
            assert dest.startswith("{{ settings_spine_config_dir }}/"), (
                "settings_files dest must derive from settings_spine_config_dir"
            )
            assert dest.endswith("settings.toml")

    def test_every_dest_parent_is_ensured_in_config_dirs(self) -> None:
        """Self-containment (review finding 2026-08-12): the template module
        does NOT create dest parents, so every settings_files dest's parent
        must be one of the ensured settings_config_dirs. The two lists are
        otherwise unlinked — a 4th tool without a matching dir would fail only
        at runtime with a raw "destination directory does not exist"."""
        data = _vars()
        ensured = {str(d) for d in data["settings_config_dirs"]}
        for file_ in data["settings_files"]:
            dest = str(file_["dest"])
            parent = dest.rsplit("/", 1)[0]
            assert parent in ensured, (
                f"{file_['name']} dest parent {parent!r} is not in "
                f"settings_config_dirs (template module does not create dest parents)"
            )

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated top-level
        ansible_env fact (INJECT_FACTS_AS_VARS injection that hard-breaks on
        ansible-core >= 2.24)."""
        data = _vars()
        text = str(data)
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text


class TestSettingsTemplates:
    def test_each_template_derives_spine_paths_from_install_dir_trim(self) -> None:
        """AC 5 + trim lock: every spine-path value in each .j2 consumes
        `{{ install_dir | trim }}` — never a literal absolute path. Hardened
        (review finding 2026-08-12): quoted/glued hardcodes are caught, not
        just bare `/`-prefixed tokens."""
        for _name, filename in _EXPECTED_TEMPLATES.items():
            text = (_TEMPLATES_DIR / filename).read_text()
            hit = _hardcoded_absolute_path(text, ("install_dir | trim",))
            assert hit is None, (
                f"{filename} hardcodes a path fragment not derived from "
                f"{{{{ install_dir | trim }}}}: {hit!r} (trim lock)"
            )

    def test_no_default_fallback_on_install_dir(self) -> None:
        """AC 6: a `default()` fallback on install_dir would silently render an
        empty path (`/generated/...` or `None/generated/...`) — forbidden."""
        for filename in _EXPECTED_TEMPLATES.values():
            text = (_TEMPLATES_DIR / filename).read_text()
            assert "install_dir | default" not in text, (
                f"{filename} must NOT carry a default() fallback on install_dir "
                "(AC 6 — an empty path must never render)"
            )

    def test_csg_renders_spine_contract_and_keeps_overwrite_false(self) -> None:
        """AC 2: CSG [output] directory → {{ install_dir | trim }}/generated/
        palettes; `overwrite = false` MUST be kept (2.7's per-task env override
        is the only overwrite path)."""
        text = (_TEMPLATES_DIR / "csg-settings.toml.j2").read_text()
        assert 'directory = "{{ install_dir | trim }}/generated/palettes"' in text
        assert "overwrite = false" in text, (
            "CSG template must keep overwrite = false (2.7 owns the per-task "
            "COLORSCHEME__OUTPUT__OVERWRITE override)"
        )

    def test_weg_renders_spine_contract_and_locks_strict_false(self) -> None:
        """AC 3: WEG [output] directory → {{ install_dir | trim }}/generated/
        effects and [processing] temp_dir → {{ install_dir | trim }}/generated/
        .weg-tmp. `strict = false` is locked (chaining-spine.md contract,
        matches the settings schema default — see Dev Notes)."""
        text = (_TEMPLATES_DIR / "weg-settings.toml.j2").read_text()
        assert 'directory = "{{ install_dir | trim }}/generated/effects"' in text
        assert 'temp_dir = "{{ install_dir | trim }}/generated/.weg-tmp"' in text
        assert "strict = false" in text, (
            "WEG template must lock strict = false (chaining-spine.md contract, "
            "matches settings_schema.py ExecutionSchema.strict default)"
        )

    def test_itr_renders_spine_contract_uncommented(self) -> None:
        """AC 4: ITR [output] output_dir → {{ install_dir | trim }}/generated/
        icons, [templates] dir → {{ install_dir | trim }}/icon-templates, and
        [color_scheme] path → {{ install_dir | trim }}/generated/palettes/
        colors.yaml — the [templates]/[color_scheme] sections MUST be present
        and UNCOMMENTED (the packaged default has them commented out; this role
        renders them active so the resolver chain reaches the spine paths)."""
        text = (_TEMPLATES_DIR / "itr-settings.toml.j2").read_text()
        assert 'output_dir = "{{ install_dir | trim }}/generated/icons"' in text
        assert 'dir = "{{ install_dir | trim }}/icon-templates"' in text
        assert 'path = "{{ install_dir | trim }}/generated/palettes/colors.yaml"' in text
        assert "[templates]" in text and "[color_scheme]" in text, (
            "ITR template must have [templates] and [color_scheme] sections present"
        )
        assert not any(
            line.strip().startswith("#")
            and line.strip().lstrip("#").strip().startswith(("[templates]", "[color_scheme]"))
            for line in text.splitlines()
        ), (
            "ITR [templates]/[color_scheme] sections must be UNCOMMENTED (the "
            "packaged default has them commented — this role renders them active)"
        )


class TestSettingsPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "settings.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["settings"]
        assert "become" not in play, "settings playbook must not use become"
        assert "become_user" not in play, "settings playbook must not use become_user"

    def test_no_group_by_distro_selection(self) -> None:
        """Distro-agnostic (NFR-3): unlike packages.yaml there is NO group_by
        distro-selection mechanism in the settings playbook."""
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert "group_by" not in play, "settings playbook must not use group_by"
        assert "groups" not in play, "settings playbook must not group hosts"

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

    def test_playbook_executes_and_renders_settings(self) -> None:
        """Regression guard (review finding 2026-08-12 discipline): the role
        must ACTUALLY render the three settings files — structural tests alone
        could not catch a silent no-op. Run the real playbook against a temp
        HOME + XDG_CONFIG_HOME + install_dir, assert each settings.toml exists
        under the config-in-spine home <install>/config/, parses as valid TOML,
        and its spine paths equal the install_dir-derived absolute paths; a
        --check run writes nothing and reports no failures; re-running is a
        no-op (AC 4 idempotency); no None/empty-path values render (AC 6)."""
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

            def run(*extra: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        ansible_playbook,
                        str(self._PATH),
                        *extra,
                        "-e",
                        f"install_dir={install}",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=120,
                )

            check = run("--check")
            assert check.returncode == 0, check.stdout + check.stderr
            assert "failed=0" in check.stdout, (
                "--check must report no failures (template/file are check-safe "
                "natively); recap:\n" + check.stdout
            )
            for name, path in _expected_files(install).items():
                assert not path.exists(), (
                    f"--check wrote {name} settings.toml {path} — check mode must not write"
                )

            first = run()
            assert first.returncode == 0, first.stdout + first.stderr

            for name, path in _expected_files(install).items():
                assert path.is_file(), f"{name} settings.toml {path} was never rendered"

            csg = tomllib.loads(_expected_files(install)["csg"].read_text())
            assert str(csg["output"]["directory"]) == str(install / "generated" / "palettes")
            assert csg["output"]["overwrite"] is False, (
                "rendered CSG file must keep overwrite = false (2.7 owns the env override)"
            )
            assert csg["output"]["default_formats"] == ["conf", "gtk.css", "yaml"], (
                "rendered CSG default_formats must match the chain formats (review "
                "finding 2026-08-12 — json/sh has no Phase 1 consumer)"
            )
            weg = tomllib.loads(_expected_files(install)["weg"].read_text())
            assert str(weg["output"]["directory"]) == str(install / "generated" / "effects")
            assert str(weg["processing"]["temp_dir"]) == str(install / "generated" / ".weg-tmp")
            assert weg["execution"]["strict"] is False
            itr = tomllib.loads(_expected_files(install)["itr"].read_text())
            assert str(itr["output"]["output_dir"]) == str(install / "generated" / "icons")
            assert str(itr["templates"]["dir"]) == str(install / "icon-templates")
            assert str(itr["color_scheme"]["path"]) == str(
                install / "generated" / "palettes" / "colors.yaml"
            )

            for name, path in _expected_files(install).items():
                text = path.read_text()
                assert "None/generated" not in text and "/None" not in text, (
                    f"{name} settings.toml renders a None path (AC 6)"
                )
                parsed = tomllib.loads(text)
                for leaf in _flatten_strings(parsed):
                    if leaf in ("", "None"):
                        assert leaf != "None", (
                            f"{name} settings.toml renders the literal 'None' (AC 6)"
                        )
                    else:
                        assert "/None" not in leaf and "None/" not in leaf, (
                            f"{name} settings.toml renders a None path (AC 6): {leaf!r}"
                        )

            second = run()
            assert second.returncode == 0, second.stdout + second.stderr
            assert "changed=0" in second.stdout, (
                "re-running the playbook must be a no-op (content-compare "
                "idempotency — NFR-1); recap:\n" + second.stdout
            )

    def test_playbook_renders_into_home_config_without_xdg(self) -> None:
        """The real-world default (config-in-spine 2026-08-16): the render
        destination is <install>/config/ REGARDLESS of XDG_CONFIG_HOME — the
        settings role no longer renders into the XDG config home (the
        config-links role symlinks ~/.config/<tool> -> <install>/config/<tool>).
        This test proves the playbook renders without XDG_CONFIG_HOME set (and
        the settings_xdg_config_home fallback var still resolves harmlessly)."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            install = Path(tmp) / "install"
            home.mkdir()
            install.mkdir()

            env = _test_env(
                HOME=str(home),
                ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"),
            )
            env.pop("XDG_CONFIG_HOME", None)

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
            assert result.returncode == 0, result.stdout + result.stderr

            for name, path in _expected_files(install).items():
                assert path.is_file(), (
                    f"{name} settings.toml {path} was never rendered under "
                    "install/config (config-in-spine home)"
                )

    def test_runtime_gate_with_cli_tools(self) -> None:
        """AC 8 (optional): if a CLI is on PATH, invoke its --config gate
        against the rendered files — per-tool (review finding 2026-08-12), so
        a machine with only one CLI still gates that half. A temp HOME won't
        find uv-installed tools, so absent CLIs are skipped — the authoritative
        gate is Story 2.12 (verify) + Story 3.3 (settings-parity)."""
        csg = shutil.which("csg")
        weg = shutil.which("weg")
        if csg is None and weg is None:
            pytest.skip("csg/weg not installed; skipping runtime gate (owned by 2.12/3.3)")
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
            assert result.returncode == 0, result.stdout + result.stderr

            gates: list[tuple[list[str], Path]] = []
            if csg is not None:
                gates.append(
                    (
                        [csg, "info", "--config"],
                        install / "config" / "color-scheme-generator" / "settings.toml",
                    )
                )
            if weg is not None:
                gates.append(
                    ([weg, "info", "--config"], install / "config" / "weg" / "settings.toml")
                )
            for cmd, config in gates:
                gate = subprocess.run(
                    [*cmd, str(config)],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=120,
                )
                assert gate.returncode == 0, (
                    f"{' '.join(cmd)} <rendered> must exit 0 (AC 8); stdout:\n"
                    + gate.stdout
                    + "\nstderr:\n"
                    + gate.stderr
                )


def _test_env(**overrides: str) -> dict[str, str]:
    """A scrubbed env for playbook subprocesses (review finding 2026-08-12):
    drop ambient ANSIBLE_* vars — a developer's ANSIBLE_INVENTORY /
    ANSIBLE_ROLES_PATH / etc. would otherwise silently override ansible.cfg —
    then apply the explicit HOME/XDG_CONFIG_HOME/ANSIBLE_CONFIG."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
    env.update(overrides)
    return env


def _expected_files(install: Path) -> dict[str, Path]:
    """The rendered settings files, now under the config-in-spine home
    <install>/config/ (NOT the XDG config home — settings renders into the
    spine; the config-links role symlinks ~/.config/<tool> -> the spine)."""
    return {
        "csg": install / "config" / "color-scheme-generator" / "settings.toml",
        "weg": install / "config" / "weg" / "settings.toml",
        "itr": install / "config" / "itr" / "settings.toml",
    }


def _flatten_strings(value: object) -> list[str]:
    """Yield every string leaf in a parsed TOML structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    return []
