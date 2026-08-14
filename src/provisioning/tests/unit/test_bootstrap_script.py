from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _find_bootstrap_script() -> Path:
    """Locate the real scripts/bootstrap.sh by walking up from this test file.

    Anchored on ``src/provisioning/pyproject.toml`` (the repo's provisioning
    project marker) so a sibling workspace's ``scripts/`` tree is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        script = parent / "scripts" / "bootstrap.sh"
        if script.is_file() and (parent / "src" / "provisioning" / "pyproject.toml").is_file():
            return script
    raise FileNotFoundError(
        "scripts/bootstrap.sh not found walking up from the test file; "
        "AC 1-5 real-script coverage requires the authored bootstrap"
    )


_SCRIPT = _find_bootstrap_script()
_TEXT = _SCRIPT.read_text()

_DISTRO_TOKENS_RE = re.compile(r"pacman|apt-get|apt |yum|dnf")


class TestBootstrapScriptFile:
    def test_file_exists_and_is_executable(self) -> None:
        """The fresh-machine entry point exists and is executable (chmod +x)."""
        assert _SCRIPT.is_file()
        assert os.access(_SCRIPT, os.X_OK), (
            "scripts/bootstrap.sh must be executable (chmod +x scripts/bootstrap.sh)"
        )

    def test_shebang_and_fail_fast(self) -> None:
        """Runs under bash with fail-fast on any error — a partially-provisioned
        machine is worse than a failed bootstrap."""
        assert _TEXT.startswith("#!/usr/bin/env bash\n"), "script must start with the bash shebang"
        assert "set -euo pipefail" in _TEXT.splitlines()[1], (
            "line 2 must be `set -euo pipefail` (fail-fast on any error)"
        )

    def test_derives_root_from_script_location(self) -> None:
        """ROOT derives from BASH_SOURCE — the script works even outside a git
        worktree; `git rev-parse --show-toplevel` is NOT authoritative."""
        assert "BASH_SOURCE" in _TEXT, "ROOT must derive from BASH_SOURCE[0], not git rev-parse"
        assert "git rev-parse" not in _TEXT, (
            "bootstrap.sh must NOT use the git top-level command to derive ROOT"
        )

    def test_uv_preseed_logic(self) -> None:
        """AC 1: a `command -v uv` presence check and the official astral
        standalone installer (curl, with wget fallback) for the absent case."""
        assert "command -v uv" in _TEXT, "uv preseed must gate on `command -v uv`"
        assert "astral.sh/uv/install.sh" in _TEXT, (
            "uv preseed must use the official standalone installer"
        )
        assert "curl -LsSf" in _TEXT, "uv preseed must support the curl installer form"
        assert "wget -qO-" in _TEXT, "uv preseed must fall back to the wget installer form"
        assert "$HOME/.local/bin" in _TEXT, (
            "uv preseed must prepend ~/.local/bin to PATH (installer + cli_tools bin dir)"
        )

    def test_python_preseed_is_uv_owned(self) -> None:
        """AC 1: uv owns Python provisioning — no hand-rolled python3
        detection/install branch."""
        assert "python3" not in _TEXT, (
            "uv owns Python provisioning (managed interpreter); do NOT hand-roll python3"
        )

    def test_collection_resolution_through_uv_run_directory(self) -> None:
        """AC 2: ansible-galaxy (ships with ansible-core) runs through the
        project env via `uv run --directory`, referencing requirements.yml."""
        assert "ansible-galaxy collection install -r" in _TEXT
        assert "requirements.yml" in _TEXT
        assert "uv run --directory" in _TEXT

    def test_loud_abort_on_collection_resolution_failure(self) -> None:
        """AC 2: a resolution failure (missing network, unresolvable pin) must
        abort loudly naming the requirements file and likely cause — never
        continue into bootstrap with missing modules."""
        assert "collection resolution FAILED" in _TEXT, (
            "galaxy install must carry a loud resolution-failure message"
        )
        assert "Requirements file" in _TEXT, (
            "the failure message must name the exact requirements.yml path"
        )
        assert "no network" in _TEXT, "the failure message must name the likely cause (no network)"
        assert "exit 1" in _TEXT, "the loud abort must exit non-zero"

    def test_bootstrap_and_verify_invoked_in_order_through_uv_run(self) -> None:
        """AC 3 + AC 4: `dotfiles-provision bootstrap` and the trailing
        `dotfiles-provision verify` both appear, bootstrap before verify, each
        via `uv run --directory`."""
        lines = _TEXT.splitlines()
        bootstrap = next(
            line for line in lines if "run_stage" in line and "dotfiles-provision bootstrap" in line
        )
        verify = next(
            line for line in lines if "run_stage" in line and "dotfiles-provision verify" in line
        )
        assert "uv run --directory" in bootstrap
        assert "uv run --directory" in verify
        assert lines.index(bootstrap) < lines.index(verify), (
            "bootstrap must be invoked BEFORE the trailing verify"
        )

    def test_no_distro_branching_tokens(self) -> None:
        """NFR-3 invariant lock: the script must contain NO distro-branching
        tokens — distro differences live ONLY in group_vars. A future edit that
        sneaks distro logic in fails here."""
        assert _DISTRO_TOKENS_RE.search(_TEXT) is None, (
            "bootstrap.sh must not reference distro package-manager tokens "
            "(NFR-3: distro logic lives in group_vars only)"
        )

    def test_container_engine_check_podman_preferred(self) -> None:
        """LOCKED decision (2026-08-13, Option A): the script checks for a
        container engine early — podman preferred, then docker — and fails
        loud (non-zero exit) with a helpful message when neither is on PATH.
        It must NOT install one (a distro-specific install would violate
        NFR-3)."""
        assert "command -v podman" in _TEXT, "container check must test podman"
        assert "command -v docker" in _TEXT, "container check must test docker"
        assert _TEXT.index("command -v podman") < _TEXT.index("command -v docker"), (
            "podman must be checked FIRST (preferred), then docker"
        )
        assert "exit 1" in _TEXT, "the container-engine abort must exit non-zero"
        assert "Install podman" in _TEXT, (
            "the abort must carry a helpful message naming the engine requirement"
        )

    def test_no_hardcoded_absolute_paths(self) -> None:
        """Everything derives from ROOT / $HOME — no hardcoded absolute paths."""
        assert "/home/" not in _TEXT
        assert "/root/" not in _TEXT

    def test_header_comment_block(self) -> None:
        """The header documents what the script is (CAP-4 entry point), the
        stage order, and the NFR-3 invariant."""
        assert "CAP-4" in _TEXT
        assert "uv preseed" in _TEXT
        assert "collections" in _TEXT
        assert "bootstrap" in _TEXT
        assert "verify" in _TEXT
        assert "NFR-3" in _TEXT

    def test_stage_failure_reported_with_return_code(self) -> None:
        """On any failure the script prints the failing stage with the return
        code and exits non-zero — no silent success."""
        assert "exit code" in _TEXT, "failure output must include the return code"
        assert "stage" in _TEXT

    def test_bash_syntax_check_exits_zero(self) -> None:
        """`bash -n scripts/bootstrap.sh` parses cleanly (skip if bash absent)."""
        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash not installed; skipping syntax-check")
        result = subprocess.run(
            [bash, "-n", str(_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def _link_dirname_into(bin_dir: Path) -> None:
    """PATH in the smoke tests is the stub dir alone (so the host's real
    podman/docker/uv are never seen), but the script's ROOT derivation runs
    `dirname` — symlink the real binary into the stub dir."""
    real = shutil.which("dirname") or "/usr/bin/dirname"
    os.symlink(real, bin_dir / "dirname")


def _scrubbed_env(**overrides: str) -> dict[str, str]:
    """A minimal env for bootstrap subprocesses: drop ambient ANSIBLE_/XDG_/UV_
    vars so nothing from the dev host leaks into the smoke run, then apply the
    explicit stub PATH/HOME/log overrides."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANSIBLE_", "XDG_", "UV_"))}
    env.update(overrides)
    return env


class TestBootstrapScriptRuntime:
    def test_invokes_stages_in_order_with_stubbed_path(self) -> None:
        """Runtime smoke test: stub podman/uv/ansible-galaxy/dotfiles-provision
        on a temp PATH and assert the script invokes the four stages in order —
        collections → bootstrap → verify (uv preseed skipped because uv is
        present). Structural tests alone can miss a silent no-op."""
        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash not installed; skipping runtime smoke test")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()
            _link_dirname_into(bin_dir)

            for name in ("podman", "uv", "ansible-galaxy", "dotfiles-provision"):
                stub = bin_dir / name
                stub.write_text(
                    "#!/bin/sh\n"
                    f'echo "{name} $*" >> "$BOOTSTRAP_TEST_LOG"\n'
                    + ('shift 3\nexec "$@"\n' if name == "uv" else "exit 0\n")
                )
                stub.chmod(0o755)

            env = _scrubbed_env(
                PATH=str(bin_dir),
                HOME=str(home),
                BOOTSTRAP_TEST_LOG=str(log),
            )
            result = subprocess.run(
                [bash, str(_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr

            prov_dir = str(_SCRIPT.parent.parent / "src" / "provisioning")
            req = str(
                _SCRIPT.parent.parent / "src" / "provisioning" / "ansible" / "requirements.yml"
            )
            expected = [
                f"uv run --directory {prov_dir} ansible-galaxy collection install -r {req}",
                f"ansible-galaxy collection install -r {req}",
                f"uv run --directory {prov_dir} dotfiles-provision bootstrap",
                "dotfiles-provision bootstrap",
                f"uv run --directory {prov_dir} dotfiles-provision verify",
                "dotfiles-provision verify",
            ]
            actual = [line for line in log.read_text().splitlines() if line.strip()]
            assert actual == expected, (
                "bootstrap.sh must invoke, in order: collections → bootstrap → verify, "
                "each through `uv run --directory`; got:\n" + "\n".join(actual)
            )

    def test_fails_loud_without_container_engine(self) -> None:
        """LOCKED Option A: with podman/docker absent from PATH the script
        aborts non-zero with a helpful message BEFORE running any stage (no
        uv / ansible-galaxy / dotfiles-provision invocation)."""
        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash not installed; skipping container-check test")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()
            _link_dirname_into(bin_dir)

            stub = bin_dir / "uv"
            stub.write_text('echo "uv $*" >> "$BOOTSTRAP_TEST_LOG"\nexit 0\n')
            stub.chmod(0o755)

            env = _scrubbed_env(
                PATH=str(bin_dir),
                HOME=str(home),
                BOOTSTRAP_TEST_LOG=str(log),
            )
            result = subprocess.run(
                [bash, str(_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode != 0, (
                "script must fail loud when no container engine is on PATH"
            )
            assert "no container engine" in result.stdout + result.stderr, (
                "the abort must carry a helpful message naming the requirement"
            )
            assert not log.exists() or log.read_text().strip() == "", (
                "no stage may run before the container-engine abort"
            )
