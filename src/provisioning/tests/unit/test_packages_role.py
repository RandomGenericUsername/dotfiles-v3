from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from provisioning.domain.enums import Distro


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors ``test_ansible_scaffold.py``: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-7 real-scaffold coverage requires the authored role"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "packages"

_VARS_REQUIRED_KEYS = {
    "main.yml": {"packages_state", "aur_build_dir", "aur_packages"},
    "arch.yml": {
        "packages_use_aur",
        "aur_builder_user",
        "aur_builder_group",
        "aur_packages",
        "yay_repo",
        "aur_conflict_probe_paths",
    },
    "debian.yml": {"packages_use_aur"},
}

# Package names authored in group_vars (Story 2.2) — they MUST live there,
# never in the role's vars (NFR-3 distro isolation, AC 4).
_ARCH_PACKAGE_NAMES = (
    "hyprland",
    "hyprpaper",
    "aylurs-gtk-shell-git",
    "ttf-jetbrains-mono-nerd",
    "noto-fonts",
    "noto-fonts-cjk",
    "ttf-nerd-fonts-symbols",
)
_DEBIAN_PACKAGE_NAMES = (
    "hyprland",
    "hyprpaper",
    "aylurs-gtk-shell-git",
    "fonts-noto",
    "fonts-noto-cjk",
    "fonts-noto-color-emoji",
)

# Task modules that would hardcode a distro package manager (forbidden — only
# ansible.builtin.package may appear, which auto-detects pacman/apt).
_FORBIDDEN_MODULE_FQCNS = ("ansible.builtin.pacman", "ansible.builtin.apt")

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
    """Return the module FQCN key for a task, or None for bare-key tasks.

    A task dict is {module: args, **keywords}; the module key is the one key
    that is not a reserved task keyword and not the args dict itself.
    """
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


class TestPackagesRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml", "vars/arch.yml", "vars/debian.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"


class TestPackagesTasks:
    def test_tasks_parse_to_list_of_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_distro_branching_only_in_include_vars(self) -> None:
        tasks = _load_tasks()
        include_vars_tasks = [
            t for t in tasks if _module_key(t) in ("include_vars", "ansible.builtin.include_vars")
        ]
        assert len(include_vars_tasks) == 2, (
            "exactly two include_vars tasks expected (arch + debian), "
            f"found {len(include_vars_tasks)}"
        )
        for task in tasks:
            if "ansible_os_family" not in str(task):
                continue
            assert _module_key(task) in ("include_vars", "ansible.builtin.include_vars"), (
                "ansible_os_family may only appear in the two include_vars tasks"
            )
        whens = [str(t.get("when", "")) for t in tasks]
        assert sum("ansible_os_family" in w for w in whens) == 2

    def test_no_hardcoded_package_manager_modules(self) -> None:
        tasks = _load_tasks()
        for task in tasks:
            module = _module_key(task)
            assert module not in _FORBIDDEN_MODULE_FQCNS, (
                f"task {task.get('name')!r} hardcodes {module} — use ansible.builtin.package "
                "(auto-detects pacman/apt)"
            )

    def test_aur_gated_on_packages_use_aur_not_os_family(self) -> None:
        tasks = _load_tasks()
        for task in tasks:
            when = str(task.get("when", ""))
            if "packages_use_aur" in when:
                assert "ansible_os_family" not in when, (
                    f"task {task.get('name')!r} must gate on packages_use_aur only, "
                    "never ansible_os_family"
                )

    def test_makepkg_bootstrap_is_command_module_with_creates(self) -> None:
        tasks = _load_tasks()
        makepkg = next(t for t in tasks if "makepkg" in str(t.get("name", "")))
        assert _module_key(makepkg) == "ansible.builtin.command"
        assert makepkg.get("become_user") == "{{ aur_builder_user }}"
        args = makepkg.get("args")
        assert isinstance(args, dict)
        assert args["creates"] == "/usr/bin/yay"
        assert "{{ aur_build_dir }}" in str(args.get("chdir", ""))

    def test_makepkg_when_not_gated_on_yay_check_rc(self) -> None:
        """Locks AC5: under --check a skipped command registers rc=0, so gating
        the makepkg task on yay_check.rc would make it report `skipped` instead
        of would-change. The `creates: /usr/bin/yay` guard must be the only
        idempotency mechanism on the makepkg task."""
        tasks = _load_tasks()
        makepkg = next(t for t in tasks if "makepkg" in str(t.get("name", "")))
        when = str(makepkg.get("when", ""))
        assert "yay_check" not in when, (
            "makepkg task must not gate on yay_check.rc (skipped command under "
            "--check registers rc=0, silently skipping the would-change report)"
        )

    def test_aur_conflict_probe_runs_before_the_aur_install(self) -> None:
        """Hardening (2026-08-18): a pre-flight `pacman -Qo` probe + assert must
        run BEFORE the kewlfft.aur.aur install, so stray non-pacman python files
        (a past pip install into system python) fail loud with a clear message
        instead of dying deep inside a yay run with 'conflicting files'."""
        tasks = _load_tasks()
        probe = next(t for t in tasks if "Check for foreign files" in str(t.get("name", "")))
        assert_ = next(t for t in tasks if "Assert no foreign files" in str(t.get("name", "")))
        install_idx = tasks.index(next(t for t in tasks if _module_key(t) == "kewlfft.aur.aur"))
        assert tasks.index(probe) < install_idx, "probe must run before the AUR install"
        assert tasks.index(assert_) < install_idx, "assert must run before the AUR install"

    def test_aur_conflict_assert_is_fail_loud_and_check_gated(self) -> None:
        tasks = _load_tasks()
        assert_ = next(t for t in tasks if "Assert no foreign files" in str(t.get("name", "")))
        body = assert_.get(_module_key(assert_) or "", {})
        assert isinstance(body, dict), "assert task must have a module body"
        that = str(body.get("that", ""))
        assert "FOREIGN" in that, "the assert must detect FOREIGN probe results"
        assert "packages_use_aur" in str(assert_.get("when", ""))
        assert "not ansible_check_mode" in str(assert_.get("when", "")), (
            "the foreign-file probe/assert must be --check-gated (dry-run must not run pacman -Qo)"
        )

    def test_aur_conflict_probe_paths_are_non_empty(self) -> None:
        """The probe path list must be non-empty on Arch (it is the collision
        surface the check guards against)."""
        data = yaml.safe_load((_ROLES_DIR / "vars" / "arch.yml").read_text())
        paths = data.get("aur_conflict_probe_paths", [])
        assert isinstance(paths, list) and paths, (
            "aur_conflict_probe_paths must be a non-empty list"
        )


class TestPackagesVars:
    def test_vars_parse_with_required_keys(self) -> None:
        for basename, required in _VARS_REQUIRED_KEYS.items():
            data = yaml.safe_load((_ROLES_DIR / "vars" / basename).read_text())
            assert isinstance(data, dict), f"vars/{basename} must parse to a dict"
            assert required.issubset(set(data)), (
                f"vars/{basename} missing keys: {required - set(data)}"
            )

    def test_arch_vars_set_aur_switches(self) -> None:
        data = yaml.safe_load((_ROLES_DIR / "vars" / "arch.yml").read_text())
        assert data["packages_use_aur"] is True

    def test_debian_vars_disable_aur(self) -> None:
        data = yaml.safe_load((_ROLES_DIR / "vars" / "debian.yml").read_text())
        assert data["packages_use_aur"] is False

    def test_vars_do_not_carry_package_names(self) -> None:
        arch_text = (_ROLES_DIR / "vars" / "arch.yml").read_text()
        debian_text = (_ROLES_DIR / "vars" / "debian.yml").read_text()
        # AUR-routed packages (correct-course 2026-08-18: AGS = aylurs-gtk-shell-git)
        # are the EXCEPTION — their AUR names are AUR-channel routing config in
        # vars/arch.yml aur_packages, NOT pacman names (NFR-3 still holds for the
        # pacman/apt names below). The pacman-installable names must stay in
        # group_vars.
        arch_aur = ("aylurs-gtk-shell-git",)
        for name in _ARCH_PACKAGE_NAMES:
            if name in arch_aur:
                continue
            assert name not in arch_text, (
                f"package name {name!r} must live in group_vars, not vars/arch.yml"
            )
        for name in _DEBIAN_PACKAGE_NAMES:
            assert name not in debian_text, (
                f"package name {name!r} must live in group_vars, not vars/debian.yml"
            )


class TestPackagesPlaybook:
    _PATH = _ANSIBLE_DIR / "playbooks" / "packages.yaml"

    def test_parses_with_distro_selection_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 2
        first, second = plays
        assert first["hosts"] == "localhost"
        assert first["gather_facts"] is True
        group_by = next(
            t for t in first["tasks"] if "ansible.builtin.group_by" in t or "group_by" in t
        )
        assert (
            group_by.get("ansible.builtin.group_by", group_by.get("group_by"))["key"]
            == "{{ os_family }}"
        )
        assert second["hosts"] == "{{ os_family }}"
        assert second["become"] is True
        assert second["roles"] == ["packages"]

    def test_guard_asserts_os_family_seam_matches_fact(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        first = plays[0]
        guard = next(t for t in first["tasks"] if "ansible.builtin.assert" in t)
        that = guard["ansible.builtin.assert"]["that"]
        assert "arch" in str(that) and "Archlinux" in str(that)
        assert "debian-family" in str(that) and "Debian" in str(that)

    def test_syntax_check_exits_zero(self) -> None:
        env = dict(os.environ)
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        for os_family in ("arch", "debian-family"):
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "--syntax-check",
                    str(self._PATH),
                    "-e",
                    f"os_family={os_family}",
                    "-e",
                    "install_dir=/tmp/x",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stdout + result.stderr


class TestGroupVarsValueShape:
    """Locks deferred D3 from the Story 2.2 review: every packages value is a
    non-empty str or non-empty list[str] (scalar or list of names)."""

    def test_packages_map_values_are_scalar_or_list_of_names(self) -> None:
        for basename in (Distro.ARCH.value, Distro.DEBIAN_FAMILY.value):
            data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / f"{basename}.yml").read_text())
            packages = data["packages"]
            assert isinstance(packages, dict)
            for key, value in packages.items():
                if isinstance(value, str):
                    assert value.strip(), f"{basename}: empty scalar under {key}"
                elif isinstance(value, list):
                    assert len(value) > 0, f"{basename}: empty list under {key}"
                    assert all(isinstance(item, str) and item.strip() for item in value), (
                        f"{basename}: non-str/empty item under {key}"
                    )
                else:
                    pytest.fail(f"{basename}: {key} has unsupported shape {type(value).__name__}")
