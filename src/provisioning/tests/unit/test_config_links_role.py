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

    Mirrors ``test_config_copies_role.py`` / ``test_verify_role.py``:
    anchored on ``pyproject.toml`` so the sibling project's ``ansible/`` tree
    in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "config_links"
_TASKS_MAIN = _ROLES_DIR / "tasks" / "main.yml"
_TASKS_LINK_ONE = _ROLES_DIR / "tasks" / "_link_one.yml"
_PLAYBOOK_PATH = _ANSIBLE_DIR / "playbooks" / "config-links.yaml"

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
    "loop_control",
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


def _load_tasks(path: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, list)
    return data


def _module_key(task: dict[str, object]) -> str | None:
    """Return the module FQCN key for a task, or None for bare-key tasks."""
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, object]) -> dict[str, object]:
    """Return the module body as a dict for a task."""
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return {}
    assert isinstance(module, dict)
    return module


def _vars() -> Any:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _sibling_vars(role: str) -> Any:
    data = yaml.safe_load((_ANSIBLE_DIR / "roles" / role / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _link_one_tasks_with_module(module: str) -> list[dict[str, object]]:
    return [task for task in _load_tasks(_TASKS_LINK_ONE) if _module_key(task) == module]


def _when_list(task: dict[str, object]) -> list[str]:
    """Return the task's `when` as a normalized list of strings."""
    when = task.get("when")
    if when is None:
        return []
    if isinstance(when, list):
        return [str(item) for item in when]
    return [str(when)]


def _backup_mv_task() -> dict[str, object]:
    matches = [
        task
        for task in _link_one_tasks_with_module("ansible.builtin.command")
        if "mv" in str(_module(task).get("argv", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one backup mv task in _link_one.yml; found {len(matches)}"
    )
    return matches[0]


def _seed_copy_task() -> dict[str, object]:
    matches = _link_one_tasks_with_module("ansible.builtin.copy")
    assert len(matches) == 1, (
        f"expected exactly one seed copy task in _link_one.yml; found {len(matches)}"
    )
    return matches[0]


def _lineinfile_task() -> dict[str, object]:
    matches = _link_one_tasks_with_module("ansible.builtin.lineinfile")
    assert len(matches) == 1, (
        f"expected exactly one lineinfile task in _link_one.yml; found {len(matches)}"
    )
    return matches[0]


def _symlink_task() -> dict[str, object]:
    matches = [
        task
        for task in _link_one_tasks_with_module("ansible.builtin.file")
        if str(_module(task).get("state")) == "link"
    ]
    assert len(matches) == 1, (
        f"expected exactly one symlink task in _link_one.yml; found {len(matches)}"
    )
    return matches[0]


def _ensure_spine_dir_task() -> dict[str, object]:
    matches = [
        task
        for task in _link_one_tasks_with_module("ansible.builtin.file")
        if str(_module(task).get("state")) == "directory"
        and "config/{{ config_link_name }}" in str(_module(task).get("path", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one spine-dir ensure task in _link_one.yml; found {len(matches)}"
    )
    return matches[0]


def _pause_task() -> dict[str, object]:
    matches = _link_one_tasks_with_module("ansible.builtin.pause")
    assert len(matches) == 1, (
        f"expected exactly one ask-policy pause task in _link_one.yml; found {len(matches)}"
    )
    return matches[0]


def _task_order() -> dict[str, int]:
    """Map module FQCNs to their first index in _link_one.yml (ordering pins)."""
    order: dict[str, int] = {}
    for index, task in enumerate(_load_tasks(_TASKS_LINK_ONE)):
        key = _module_key(task)
        if key is not None and key not in order:
            order[key] = index
    return order


class TestConfigLinksRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "tasks/_link_one.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestConfigLinksTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        for path in (_TASKS_MAIN, _TASKS_LINK_ONE):
            tasks = _load_tasks(path)
            assert tasks, f"{path.name} must not be empty"
            for task in tasks:
                assert isinstance(task, dict)
                assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        """Role contract: the FIRST task in tasks/main.yml is the fail-loud
        install_dir seam assert, verbatim from the sibling roles."""
        tasks = _load_tasks(_TASKS_MAIN)
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert (role contract)"
        )
        that = str(_module(first).get("that", ""))
        assert "install_dir is defined" in that
        assert "install_dir | trim | length > 0" in that

    def test_main_loop_over_managed_dirs_includes_link_one(self) -> None:
        """tasks/main.yml includes _link_one.yml once, looping
        config_links_managed_dirs — all per-entry logic lives in the include."""
        tasks = _load_tasks(_TASKS_MAIN)
        includes = [task for task in tasks if _module_key(task) == "ansible.builtin.include_tasks"]
        assert len(includes) == 1, f"expected exactly one include_tasks; found {len(includes)}"
        assert "{{ config_links_managed_dirs }}" in str(includes[0].get("loop", ""))

    def test_backup_mv_task_is_check_gated(self) -> None:
        """Check-mode discipline: the backup mv (the only mutating command) is
        gated `when: not ansible_check_mode` — a dry run never moves or links."""
        task = _backup_mv_task()
        assert "not ansible_check_mode" in _when_list(task), (
            "the backup mv must stay --check-gated (dry run must be dry)"
        )

    def test_ask_policy_pause_is_check_gated(self) -> None:
        """TTY-aware prompting: the ask-policy pause never fires under --check
        (a dry run must never prompt)."""
        task = _pause_task()
        when = _when_list(task)
        assert "not ansible_check_mode" in when, (
            "the ask-policy pause must be check-gated (never prompt under --check)"
        )

    def test_symlink_task_ungated_by_check_mode_for_absent_targets(self) -> None:
        """The symlink task is a `file state: link` (check-safe — reports
        would-change without writing). It stays UNgated for absent targets
        (a dry run still predicts the link) but skips the prediction under
        --check when a conflicting pre-existing target exists — the backup mv
        is check-gated (skipped), so the file module would otherwise fail
        loud predicting over a non-empty real dir ("refusing to convert")."""
        task = _symlink_task()
        when = _when_list(task)
        assert "not config_links_is_correct_link" in when
        assert "not (ansible_check_mode and config_links_existing.stat.exists)" in when

    def test_seed_copy_gated_isdir_and_not_correct_link_and_before_mv(self) -> None:
        """gt-3-1: the seed copy runs only for gtk dirs whose pre-existing
        target is a REAL DIR that is not already our link (the isdir gate
        skips a regular file / foreign symlink — the mv still handles those),
        and sits BEFORE the backup mv task (seed → backup → symlink ordering —
        a seed failure aborts while the user's live dir is intact)."""
        task = _seed_copy_task()
        module = _module(task)
        when = _when_list(task)
        assert "config_link_name in config_links_gtk_dirs" in when
        assert "config_links_existing.stat.exists" in when
        assert "config_links_existing.stat.isdir" in when
        assert "not config_links_is_correct_link" in when
        assert task.get("when") != "not ansible_check_mode", (
            "the seed copy must NOT be --check-gated (copy is check-safe; the "
            "source is real machine content that exists under --check too)"
        )
        src = str(module.get("src", ""))
        assert src.startswith("{{ config_links_xdg_config_home }}/{{ config_link_name }}/"), (
            "seed copy src must derive from config_links_xdg_config_home"
        )
        assert src.endswith("/"), "seed copy src must end with '/' (contents-into-dest)"
        dest = str(module.get("dest", ""))
        assert "{{ install_dir | trim }}/config/{{ config_link_name }}/" in dest
        assert dest.endswith("/"), "seed copy dest must end with '/'"
        assert module.get("remote_src") is True, "seed copy must set remote_src: true"
        assert module.get("force") is not False, (
            "seed copy must keep the default force: true (unconditional-copy — "
            "a re-run where the user restored their dir re-seeds the spine)"
        )
        order = _task_order()
        assert order["ansible.builtin.copy"] < order["ansible.builtin.command"], (
            "the seed copy must be ordered BEFORE the backup mv task"
        )

    def test_lineinfile_carries_create_and_import_line_after_seed(self) -> None:
        """gt-3-1: the palette-import ensure is a lineinfile WITHOUT regexp
        (append-if-absent — re-runs never duplicate the import), with
        create: true (gtk-4.0's file is NEW), gated only on gtk-dirs
        membership (NOT on the classification — it repairs a spine missing
        the import), NOT --check-gated (lineinfile is check-safe), and
        ordered AFTER the seed copy and BEFORE the symlink task."""
        task = _lineinfile_task()
        module = _module(task)
        assert "regexp" not in module, (
            "the lineinfile must NOT carry regexp (no-regexp = insert at EOF "
            "only when absent — re-runs never duplicate the import)"
        )
        assert module.get("create") is True, (
            "the lineinfile must set create: true (gtk-4.0's gtk.css is NEW)"
        )
        assert module.get("line") == "{{ config_links_gtk_import_line }}"
        assert "{{ install_dir | trim }}/config/{{ config_link_name }}/gtk.css" in str(
            module.get("path", "")
        ), "the lineinfile must target the SPINE path (never through ~/.config)"
        when = _when_list(task)
        assert when == ["config_link_name in config_links_gtk_dirs"], (
            "the lineinfile must be gated ONLY on gtk-dirs membership (not on "
            "the classification, not on check mode)"
        )
        order = _task_order()
        assert order["ansible.builtin.lineinfile"] > order["ansible.builtin.copy"], (
            "the lineinfile must be ordered AFTER the seed copy (the copy must "
            "not overwrite the appended line)"
        )
        tasks = _load_tasks(_TASKS_LINK_ONE)
        lineinfile_index = next(
            i for i, t in enumerate(tasks) if _module_key(t) == "ansible.builtin.lineinfile"
        )
        symlink_index = next(
            i
            for i, t in enumerate(tasks)
            if _module_key(t) == "ansible.builtin.file" and str(_module(t).get("state")) == "link"
        )
        assert lineinfile_index < symlink_index, (
            "the lineinfile must be ordered BEFORE the symlink task"
        )

    def test_ensure_spine_dir_gated_on_gtk_dirs(self) -> None:
        """gt-3-1: the spine-dir ensure (seed dirs only) is gated on gtk-dirs
        membership and NOT --check-gated (file state: directory is natively
        check-safe)."""
        task = _ensure_spine_dir_task()
        module = _module(task)
        assert "{{ install_dir | trim }}/config/{{ config_link_name }}" == str(module.get("path"))
        assert task.get("when") == "config_link_name in config_links_gtk_dirs", (
            "the spine-dir ensure must be gated on gtk-dirs membership only"
        )

    def test_no_become_anywhere_in_role(self) -> None:
        """User-scoped privilege context: NO become/become_user anywhere."""
        for path in (_TASKS_MAIN, _TASKS_LINK_ONE):
            for task in _load_tasks(path):
                assert "become" not in task, (
                    f"task {task.get('name')!r} must not use become (user-scoped role)"
                )
                assert "become_user" not in task

    def test_no_absolute_paths_hardcoded(self) -> None:
        """Trim lock: every path derives from the role vars
        ({{ install_dir | trim }}, {{ config_links_xdg_config_home }},
        ansible_facts.env) — no literal absolute path is baked into any
        task's module body OR into vars/main.yml."""
        for source_name, source_path in (
            ("tasks/main.yml", _TASKS_MAIN),
            ("tasks/_link_one.yml", _TASKS_LINK_ONE),
            ("vars/main.yml", _ROLES_DIR / "vars" / "main.yml"),
        ):
            text = str(yaml.safe_load(source_path.read_text()))
            for token in text.split():
                if token.startswith("/") and not any(
                    var in token
                    for var in ("install_dir", "config_links_xdg_config_home", "ansible_facts.env")
                ):
                    raise AssertionError(
                        f"{source_name} hardcodes an absolute path: {token!r} (trim lock)"
                    )

    def test_no_runtime_pointer_creation_and_no_state_root(self) -> None:
        """§11 boundary (AD-5) + gt-2-2 ownership: config_links never creates
        the colors.css pointer files (runtime-owned) and never derives a
        state path — no state_root / XDG_STATE_HOME reference anywhere, and
        no task writes into a colors.css path."""
        for path in (_TASKS_MAIN, _TASKS_LINK_ONE, _ROLES_DIR / "vars" / "main.yml"):
            text = path.read_text()
            assert "state_root" not in text
            assert "XDG_STATE_HOME" not in text
            if path.name != "main.yml" or path.parent.name != "tasks":
                continue
            for task in _load_tasks(path):
                module = _module(task)
                probe = (
                    str(module.get("src", ""))
                    + str(module.get("path", ""))
                    + str(module.get("dest", ""))
                )
                if "colors.css" in probe:
                    raise AssertionError(
                        f"task {task.get('name')!r} writes a colors.css path "
                        "(runtime-owned pointer — gt-2-2 boundary)"
                    )


class TestConfigLinksVars:
    _REQUIRED_KEYS = {
        "config_links_xdg_config_home",
        "config_links_backup_root",
        "config_links_backup_policy",
        "config_links_managed_dirs",
        "config_links_gtk_dirs",
        "config_links_gtk_import_line",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_managed_dirs_parity_with_verify(self) -> None:
        """Parity lock (locked from the config_links side; verify locks it too):
        config_links_managed_dirs mirrors verify_managed_link_dirs EXACTLY —
        the verify 5-layer symlink check must cover every dir this role creates."""
        managed = [str(d) for d in _vars()["config_links_managed_dirs"]]
        verify = [str(d) for d in _sibling_vars("verify")["verify_managed_link_dirs"]]
        assert managed == verify, (
            "config_links_managed_dirs must be parity-EXACT with "
            "verify_managed_link_dirs (every managed link is asserted)"
        )

    def test_gtk_dirs_are_subset_of_managed_dirs(self) -> None:
        """gt-3-1: the gtk treatment list is a subset of the managed list."""
        managed = {str(d) for d in _vars()["config_links_managed_dirs"]}
        gtk = [str(d) for d in _vars()["config_links_gtk_dirs"]]
        assert set(gtk) <= managed, (
            "config_links_gtk_dirs must be a subset of config_links_managed_dirs"
        )
        assert set(gtk) == {"gtk-3.0", "gtk-4.0"}

    def test_gtk_import_line_is_the_exact_palette_import(self) -> None:
        """The import line is pinned EXACTLY — verify's grep gate asserts the
        same literal, so a drifted import path must fail both sides."""
        assert str(_vars()["config_links_gtk_import_line"]) == '@import "colors.css";'

    def test_xdg_config_home_honors_xdg_and_defaults_to_home(self) -> None:
        """The link targets must resolve to the SAME location the filesystem
        role (2.5) created: honors $XDG_CONFIG_HOME with the spec default
        `{{ ansible_facts.env.HOME }}/.config` via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["config_links_xdg_config_home"])
        assert "ansible_facts.env.XDG_CONFIG_HOME" in value
        assert "ansible_facts.env.HOME" in value
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_backup_root_nested_under_xdg_config_home(self) -> None:
        """Timestamped backups live under ~/.config/.dotfiles-backups —
        derived from config_links_xdg_config_home (no second XDG read)."""
        value = str(_vars()["config_links_backup_root"])
        assert value == "{{ config_links_xdg_config_home }}/.dotfiles-backups"

    def test_vars_use_non_deprecated_env_fact(self) -> None:
        """F4 lock: vars read ansible_facts.env, never the deprecated
        top-level ansible_env fact."""
        text = str(_vars())
        assert "ansible_facts.env." in text
        assert "{{ ansible_env." not in text

    def test_header_documents_migrate_and_nwg_look(self) -> None:
        """AC 7: the role header documents the migrate-then-symlink design
        and the nwg-look write-through (writes land in the spine through the
        link)."""
        header = (_ROLES_DIR / "vars" / "main.yml").read_text()
        assert "Migrate-then-symlink" in header
        assert "nwg-look" in header


class TestConfigLinksPlaybook:
    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(_PLAYBOOK_PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["config_links"]
        assert "become" not in play, "config-links playbook must not use become"
        assert "become_user" not in play, "config-links playbook must not use become_user"


def _run_config_links(
    install: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("ansible-playbook"), str(_PLAYBOOK_PATH), "-e", f"install_dir={install}"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _base_env(tmp: Path) -> tuple[dict[str, str], Path, Path, Path]:
    home = Path(tmp) / "home"
    xdg = Path(tmp) / "xdg"
    install = Path(tmp) / "install"
    home.mkdir()
    xdg.mkdir()
    install.mkdir()
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("ANSIBLE_", "XDG_", "UV_TOOL_"))
    }
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(xdg),
        ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"),
    )
    return env, home, xdg, install


def _import_counts(path: Path) -> int:
    return path.read_text().count('@import "colors.css";')


@pytest.mark.integration
class TestConfigLinksExecution:
    def test_playbook_fresh_machine_creates_skeleton_and_links_idempotently(self) -> None:
        """AC (fresh machine, gt-3-1): a bare machine gets spine
        config/gtk-{3,4}.0/ each holding a gtk.css with EXACTLY one
        `@import "colors.css";` line, ~/.config/gtk-{3,4}.0 become spine
        symlinks, and re-running the playbook is a no-op (changed=0) — no
        duplicate import."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            env, home, xdg, install = _base_env(Path(tmp))

            first = _run_config_links(install, env)
            assert first.returncode == 0, first.stdout + first.stderr

            for name in ("gtk-3.0", "gtk-4.0"):
                spine_dir = install / "config" / name
                assert spine_dir.is_dir(), f"{spine_dir} was never created"
                gtk_css = spine_dir / "gtk.css"
                assert gtk_css.is_file(), f"{gtk_css} was never created"
                assert _import_counts(gtk_css) == 1, (
                    f"{gtk_css} must hold exactly one import line; got {_import_counts(gtk_css)}"
                )
                xdg_link = xdg / name
                assert xdg_link.is_symlink(), f"{xdg_link} must be a symlink"
                assert os.readlink(xdg_link) == str(spine_dir), (
                    f"{xdg_link} must point at the spine dir {spine_dir}"
                )

            second = _run_config_links(install, env)
            assert second.returncode == 0, second.stdout + second.stderr
            assert "changed=0" in second.stdout, (
                "re-running the playbook must be a no-op (idempotency); recap:\n" + second.stdout
            )
            for name in ("gtk-3.0", "gtk-4.0"):
                assert _import_counts(install / "config" / name / "gtk.css") == 1, (
                    "re-runs must never duplicate the import line"
                )

    def test_playbook_migrates_existing_user_dirs_into_the_spine(self) -> None:
        """AC (migration machine, gt-3-1): pre-existing real dirs at
        ~/.config/gtk-3.0 (settings.ini + a gtk.css WITHOUT the import) and
        ~/.config/gtk-4.0 (settings.ini only) are migrated: the spine holds
        BOTH files, the migrated gtk-3.0/gtk.css keeps the user's snippet
        verbatim with exactly ONE import appended at EOF, gtk-4.0/gtk.css is
        the new import file, a timestamped backup dir exists under
        ~/.config/.dotfiles-backups/ for each, and a re-run is changed=0 with
        the import count still 1."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            env, home, xdg, install = _base_env(Path(tmp))

            gtk3 = xdg / "gtk-3.0"
            gtk4 = xdg / "gtk-4.0"
            gtk3.mkdir()
            gtk4.mkdir()
            (gtk3 / "settings.ini").write_text("[Settings]\ngtk-theme-name=Arc-Dark\n")
            (gtk3 / "gtk.css").write_text(
                "/* xfce padding snippet (user-owned) */\n.xfce4-panel { padding: 2px; }\n"
            )
            (gtk4 / "settings.ini").write_text(
                "[Settings]\ngtk-application-prefer-dark-theme=true\n"
            )

            first = _run_config_links(install, env)
            assert first.returncode == 0, first.stdout + first.stderr

            spine3 = install / "config" / "gtk-3.0"
            spine4 = install / "config" / "gtk-4.0"
            migrated_css = spine3 / "gtk.css"
            assert (spine3 / "settings.ini").is_file(), (
                "the user's settings.ini was never seeded into the spine"
            )
            assert migrated_css.is_file(), "the user's gtk.css was never seeded into the spine"
            migrated_text = migrated_css.read_text()
            assert "xfce padding snippet" in migrated_text, (
                "the migrated gtk.css must preserve the user's snippet verbatim"
            )
            assert migrated_text.index("xfce padding snippet") < migrated_text.index(
                '@import "colors.css";'
            ), "the import must be APPENDED at EOF, below the user's snippet"
            assert _import_counts(migrated_css) == 1
            assert _import_counts(spine4 / "gtk.css") == 1, (
                "gtk-4.0/gtk.css must be the new import file"
            )
            assert (spine4 / "settings.ini").is_file(), "gtk-4.0's settings.ini must be seeded too"

            for name in (xdg / "gtk-3.0", xdg / "gtk-4.0"):
                assert name.is_symlink(), f"{name} must be a symlink after migration"
                assert os.readlink(name).startswith(str(install))

            backup_root = xdg / ".dotfiles-backups"
            for name in ("gtk-3.0", "gtk-4.0"):
                backups = sorted(backup_root.glob(f"{name}-*"))
                assert len(backups) == 1, (
                    f"exactly one timestamped backup for {name} must exist; got {backups}"
                )
                assert (backups[0] / "settings.ini").is_file(), (
                    "the backup must preserve the ORIGINAL dir contents verbatim"
                )

            second = _run_config_links(install, env)
            assert second.returncode == 0, second.stdout + second.stderr
            assert "changed=0" in second.stdout, (
                "re-running after migration must be a no-op; recap:\n" + second.stdout
            )
            assert _import_counts(migrated_css) == 1, (
                "re-runs must never duplicate the import line after migration"
            )
