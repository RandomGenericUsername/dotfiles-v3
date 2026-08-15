"""Story 3.2 integration tests — real ``ansible-playbook --check`` dry-runs.

FR-25 / PRD §4.7 (AC 2, 5, 6): every provisioning playbook is exercised with
REAL ``ansible-playbook --check`` — never a fake, never a mocked executor,
never a ``subprocess.run`` stub — and must complete cleanly (exit 0, recap
``failed=0`` / ``unreachable=0``) while reporting the would-be plan WITHOUT
mutating the host.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from provisioning.adapters.ansible_fact_reader import (
    AnsibleFactReader,
    InvalidFactOutputError,
)

pytestmark = pytest.mark.integration

# The ten playbooks under ansible/playbooks/ (FR-25 "every playbook"): the nine
# per-role playbooks plus the aggregate bootstrap.yaml. packages.yaml and
# bootstrap.yaml both contain a become:true play (--check still runs
# fact-gathering as the become target, so they need root or passwordless sudo);
# the other eight are user-scoped and must ALWAYS run.
_PLAYBOOKS = (
    "packages.yaml",
    "cli-tools.yaml",
    "filesystem.yaml",
    "assets.yaml",
    "default-palette.yaml",
    "compositor-configs.yaml",
    "config-copies.yaml",
    "settings.yaml",
    "verify.yaml",
    "bootstrap.yaml",
)
_BECOME_PLAYBOOKS = frozenset({"packages.yaml", "bootstrap.yaml"})

_ansible_playbook = shutil.which("ansible-playbook")
if _ansible_playbook is None:
    pytest.skip(
        "ansible-playbook not on PATH — the AC 2/4/5/6 dry-run suite invokes "
        "real ansible-playbook --check (FR-25); skipping loudly on hosts "
        "without it (repo test discipline)"
    )


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors the sibling role test files (test_bootstrap_playbook.py:12-25):
    anchored on ``pyproject.toml`` so a sibling project's ``ansible/`` tree in
    a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-6 integration coverage requires the authored playbooks"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"
_INVENTORY = _ANSIBLE_DIR / "inventory" / "localhost.yaml"

_RECAP_LINE_RE = re.compile(r"^\s*\S+\s*:.*\bok=\d+.*\bfailed=\d+.*$", re.MULTILINE)


def _scrubbed_env(**overrides: str) -> dict[str, str]:
    """Scrubbed env for ansible subprocesses (mirror test_verify_role.py
    ``_test_env``): drop ambient ANSIBLE_*/XDG_*/UV_TOOL_* so a developer's
    real config never silently overrides the scaffold ``ansible.cfg`` or leaks
    a real install spine, then apply the explicit overrides."""
    drop_prefixes = ("ANSIBLE_", "XDG_", "UV_TOOL_")
    env = {k: v for k, v in os.environ.items() if not k.startswith(drop_prefixes)}
    env.update(overrides)
    return env


def _detect_os_family() -> str:
    """Detect the host's ``os_family`` seam (group_vars basename) ONCE (AC 2).

    Real ``ansible -m setup localhost`` → ``ansible_os_family`` → group_vars
    basename (Archlinux→arch, Debian→debian-family). Reuses the production
    parsing seam (AnsibleFactReader) rather than re-deriving it; an unsupported
    family fails loud — packages.yaml's group_by guard would abort the dry-run
    anyway with a wrong seam.
    """
    if shutil.which("ansible") is None:
        pytest.skip("ansible not on PATH; cannot detect the os_family seam")
    env = _scrubbed_env()

    def _runner(command: list[str]) -> str:
        proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
        if proc.returncode != 0:
            raise InvalidFactOutputError(
                f"ansible -m setup exited with {proc.returncode}: {(proc.stderr or '')[:200]}"
            )
        return proc.stdout

    family: str = AnsibleFactReader(runner=_runner).os_family()
    return family


_OS_FAMILY = _detect_os_family()


def _run_check(
    playbook: Path,
    extra_vars: dict[str, str],
    env: dict[str, str],
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Shell real ``ansible-playbook -i <inventory> --check`` with the scaffold
    ``ANSIBLE_CONFIG`` and the given seam extra-vars (AC 2, 6)."""
    assert _ansible_playbook is not None
    args = [_ansible_playbook, "-i", str(_INVENTORY), "--check"]
    for key, value in extra_vars.items():
        args += ["-e", f"{key}={value}"]
    args.append(str(playbook))
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout)


def _assert_clean_dry_run(playbook_name: str, result: subprocess.CompletedProcess[str]) -> None:
    """AC 2: exit 0 AND a recap reporting failed=0/unreachable=0. Deprecation
    warnings (INJECT_FACTS_AS_VARS on ansible-core >= 2.21) are NON-fatal —
    stderr is never asserted empty."""
    assert result.returncode == 0, (
        f"{playbook_name} --check must exit 0; stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    recap = _RECAP_LINE_RE.findall(result.stdout)
    assert recap, f"{playbook_name} --check must print a PLAY RECAP block; stdout:\n{result.stdout}"
    for line in recap:
        assert re.search(r"failed=0", line), f"recap must report failed=0; line: {line}"
        assert re.search(r"unreachable=0", line), f"recap must report unreachable=0; line: {line}"


def _become_available() -> bool:
    """True when a become:true play can run --check on this host: EUID 0 or
    passwordless sudo. Fact-gathering still runs as the become target under
    --check, so a password-protected sudo dies at the become prompt."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return True
    sudo = shutil.which("sudo")
    if sudo is None:
        return False
    probe = subprocess.run([sudo, "-n", "true"], capture_output=True, text=True, timeout=30)
    return probe.returncode == 0


def _command_exists(name: str, env: dict[str, str]) -> bool:
    proc = subprocess.run(
        ["sh", "-c", f"command -v {name} >/dev/null 2>&1"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc.returncode == 0


class TestDryRunEveryPlaybook:
    @pytest.mark.parametrize("playbook_name", _PLAYBOOKS, ids=list(_PLAYBOOKS))
    def test_check_completes_clean_without_mutation(self, playbook_name: str) -> None:
        """AC 2: real --check of every playbook completes cleanly (exit 0,
        recap failed=0/unreachable=0) reporting the would-be plan, and never
        creates the scratch install_dir (the strongest local no-mutation
        proof)."""
        playbook = _PLAYBOOKS_DIR / playbook_name
        if playbook_name in _BECOME_PLAYBOOKS and not _become_available():
            pytest.skip(
                f"{playbook_name} contains a become:true play — its --check "
                "fact-gathering runs as the become target and needs passwordless "
                "sudo or root; this host has neither (sudo -n true fails). The "
                "become-gated dry-runs are exercised inside the root container "
                "(test_apply_verify_container.py) or on a root/passwordless-sudo "
                "host"
            )
        with tempfile.TemporaryDirectory() as tmp:
            install_dir = Path(tmp) / "install"
            env = _scrubbed_env(ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"))
            result = _run_check(
                playbook,
                {"install_dir": str(install_dir), "os_family": _OS_FAMILY},
                env,
            )
            _assert_clean_dry_run(playbook_name, result)
            assert not install_dir.exists(), (
                f"{playbook_name} --check must NOT create the scratch "
                f"install_dir ({install_dir}) — dry-run must be dry"
            )


class TestYayNeverBuildsUnderCheck:
    def test_packages_check_never_builds_yay(self) -> None:
        """AC 4: the AUR yay self-bootstrap (makepkg -si, packages role) NEVER
        builds under --check — the mutation-free proof (/usr/bin/yay absent
        afterward), NOT a ``skipped`` recap (a command WITH ``creates:``
        reports would-change on a fresh target without running). Requires a
        root-capable context for packages.yaml's become play; the fresh root
        container is the authoritative vehicle (test_apply_verify_container.py)."""
        env = _scrubbed_env(ANSIBLE_CONFIG=str(_ANSIBLE_DIR / "ansible.cfg"))
        if not _become_available():
            pytest.skip(
                "no root-capable context on this host (EUID 0 or passwordless "
                "sudo) — packages.yaml's become:true play cannot run --check. "
                "AC 4 is proven inside the root container "
                "(test_apply_verify_container.py) or on a host with "
                "passwordless sudo/root"
            )
        if _command_exists("yay", env):
            pytest.skip(
                "yay is already installed on this host — the AC-4 mutation-free "
                "proof requires a target WITHOUT /usr/bin/yay (a fresh machine); "
                "the fresh root container is authoritative "
                "(test_apply_verify_container.py)"
            )
        with tempfile.TemporaryDirectory() as tmp:
            install_dir = Path(tmp) / "install"
            result = _run_check(
                _PLAYBOOKS_DIR / "packages.yaml",
                {"install_dir": str(install_dir), "os_family": _OS_FAMILY},
                env,
            )
            _assert_clean_dry_run("packages.yaml", result)
            assert not _command_exists("yay", env), (
                "makepkg must NEVER run under --check — /usr/bin/yay must stay "
                "absent after the dry run (mutation-free proof)"
            )
            assert not install_dir.exists(), (
                "packages.yaml --check must not create the scratch install_dir"
            )
