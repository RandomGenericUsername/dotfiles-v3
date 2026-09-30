from __future__ import annotations

import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


def _find_bootstrap_script() -> Path:
    """Locate the real bootstrap.sh by walking up from this test file.

    Anchored on ``src/provisioning/pyproject.toml`` (the repo's provisioning
    project marker) so a sibling workspace's ``scripts/`` tree is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        script = parent / "bootstrap.sh"
        if script.is_file() and (parent / "src" / "provisioning" / "pyproject.toml").is_file():
            return script
    raise FileNotFoundError(
        "bootstrap.sh not found walking up from the test file; "
        "AC 1-5 real-script coverage requires the authored bootstrap"
    )


_SCRIPT = _find_bootstrap_script()
_TEXT = _SCRIPT.read_text()

_DISTRO_TOKENS_RE = re.compile(r"\b(?:pacman|apt-get|apt|yum|dnf)\b", re.IGNORECASE)

_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:./!#\}-])/\w+(?:/\w+)*")


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
        """AC 1 + NFR-9: uv preseed gates on `command -v uv`, installs a
        PINNED release tarball (never `| sh` of unverified remote bytes),
        verifies the committed SHA-256 before execution, and asserts the
        installed binary reports the pinned version."""
        assert "command -v uv" in _TEXT, "uv preseed must gate on `command -v uv`"
        assert "UV_VERSION" in _TEXT, "uv preseed must pin a release version (NFR-9)"
        assert "astral.sh/uv/install.sh" not in _TEXT, (
            "uv preseed must NOT pipe the astral installer to sh (supply-chain)"
        )
        assert re.search(r"\|\s*sh\b", _TEXT) is None, (
            "uv preseed must never execute piped remote bytes (supply-chain)"
        )
        assert "releases/download" in _TEXT, (
            "uv preseed must fetch the pinned release tarball from GitHub releases"
        )
        assert "sha256sum" in _TEXT, "uv preseed must verify the tarball SHA-256 before extraction"
        assert "curl -fsSL" in _TEXT, "uv preseed must support the hardened curl form"
        assert "wget --timeout" in _TEXT, "uv preseed must support the hardened wget fallback"
        assert "--version" in _TEXT, (
            "uv preseed must assert the installed binary reports the pinned version"
        )
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
        assert 'exit "$galaxy_rc"' in _TEXT, (
            "the loud abort must exit with ansible-galaxy's TRUE exit code "
            "(not a hardcoded 1), so the failure code propagates"
        )

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
        sneaks distro logic in fails here. Word-boundary anchored and
        case-insensitive so `apt` at EOL, `dnf `, or `Apt` cannot evade, and
        innocuous words containing the tokens do not false-positive."""
        assert _DISTRO_TOKENS_RE.search(_TEXT) is None, (
            "bootstrap.sh must not reference distro package-manager tokens "
            "(NFR-3: distro logic lives in group_vars only); matched: "
            + ", ".join(sorted(set(_DISTRO_TOKENS_RE.findall(_TEXT))))
        )

    def test_container_engine_check_podman_preferred(self) -> None:
        """LOCKED decision (2026-08-13, Option A): the script probes for a
        USABLE container engine early — podman preferred, then docker — and
        fails loud (non-zero exit) with a helpful message when none works. The
        probe tests usability (`engine info`, bounded), not mere presence: a
        stopped docker daemon must not pass the gate. It must NOT install one
        (a distro-specific install would violate NFR-3)."""
        assert "engine_usable podman" in _TEXT, "container check must probe podman"
        assert "engine_usable docker" in _TEXT, "container check must probe docker"
        assert _TEXT.index("engine_usable podman") < _TEXT.index("engine_usable docker"), (
            "podman must be probed FIRST (preferred), then docker"
        )
        assert "info >/dev/null" in _TEXT, (
            "the probe must test usability (`engine info`), not mere presence"
        )
        assert "timeout 15" in _TEXT, (
            "the usability probe must be bounded so a hung engine cannot stall"
        )
        assert "exit 1" in _TEXT, "the container-engine abort must exit non-zero"
        assert "Install podman" in _TEXT, (
            "the abort must carry a helpful message naming the engine requirement"
        )

    def test_no_bootstrap_container_engine_override(self) -> None:
        """Confirmation CR (2026-08-15): the script must NOT define a
        BOOTSTRAP_CONTAINER_ENGINE override — the roles' own
        cli_tools_container_engine_override / default_palette_container_engine_override
        are the sanctioned escape hatches. A second source of truth let the gate
        and the roles diverge (an off-PATH engine passed the gate then died
        mid-chain); this lock prevents the dead-var from returning."""
        assert "BOOTSTRAP_CONTAINER_ENGINE" not in _TEXT, (
            "bootstrap.sh must not carry its own engine override — the roles' "
            "override vars are the single escape hatch (confirmation CR 2026-08-15)"
        )

    def test_no_hardcoded_absolute_paths(self) -> None:
        """Everything derives from ROOT / $HOME — no hardcoded absolute paths.

        Scans for ANY /dir(/dir...) pattern — multi-segment (/usr/local, /opt/x)
        AND single-segment (/tmp, /opt, /bin) — so no absolute path class can
        pass. The shebang line and the environment-independent /dev/null
        redirect device are tolerated. Word/variable fragments that merely END
        in /name (e.g. ${UV_TARGET}/uv) are excluded by the lookbehind.
        """
        for i, line in enumerate(_TEXT.splitlines(), 1):
            if line.startswith("#!"):
                continue
            for match in _ABSOLUTE_PATH_RE.finditer(line):
                if match.group(0) == "/dev/null":
                    continue
                pytest.fail(
                    f"bootstrap.sh:{i} contains a hardcoded absolute path "
                    f"`{match.group(0)}`: {line.strip()}"
                )

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
        """`bash -n scripts/bootstrap.sh` parses cleanly."""
        bash = _require_bash()
        result = subprocess.run(
            [bash, "-n", str(_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_single_prompt_reuses_secret_for_whole_run(self) -> None:
        """Bare runs must not assume passwordless escalation and must never
        trust a warm terminal ticket: the probe runs detached (setsid, the
        same no-terminal context ansible's piped become runs in), a terminal
        prompts ONCE (hidden input) with up to three validation attempts, and
        the secret is exported for the aggregates (ANSIBLE_SUDO_PASS) instead
        of forwarding per-invocation flags. A non-terminal run without
        passwordless escalation aborts loud (exit 2)."""
        assert "setsid sudo -n true" in _TEXT, (
            "the probe must run detached (setsid), matching ansible's piped context"
        )
        assert "BOOTSTRAP_ARGS+=(--ask-become-pass)" not in _TEXT, (
            "no per-invocation become prompt may survive — one prompt covers all runs"
        )
        assert "read -rsp" in _TEXT, (
            "the terminal prompt must use hidden input"
        )
        assert "sudo -Sv" in _TEXT, (
            "the entered secret must be validated (warming the terminal ticket)"
        )
        assert "ANSIBLE_SUDO_PASS" in _TEXT, (
            "the secret must reach the aggregates via ANSIBLE_SUDO_PASS"
        )
        assert "[ -t 0 ]" in _TEXT, (
            "the prompt must be gated on stdin being a terminal"
        )
        assert "stdin is not a terminal" in _TEXT, (
            "a non-terminal run without passwordless escalation must abort loud"
        )


def _require_bash() -> str:
    """bash is a hard requirement of the artifact under test (a bash script).
    Fail loud when absent instead of silently skipping — a bash-less CI would
    otherwise report green with zero coverage of the runtime tests."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.fail(
            "bash is not installed, so scripts/bootstrap.sh cannot be validated "
            "(syntax or runtime). Do not silently skip these tests — the CI must "
            "provide bash."
        )
    return bash


def _make_stub(path: Path, script: str) -> None:
    path.write_text(script)
    path.chmod(0o755)


def _echo_stub(name: str, tail: str) -> str:
    """A stub binary that logs `name $*` to $BOOTSTRAP_TEST_LOG then runs
    `tail` (e.g. `exit 0`, or `shift 3` + `exec "$@"` for the uv passthrough)."""
    return f'#!/bin/sh\necho "{name} $*" >> "$BOOTSTRAP_TEST_LOG"\n{tail}\n'


def _uv_passthrough_stub(version: str = "0.9.22") -> str:
    """A uv stub that logs `uv $*` to $BOOTSTRAP_TEST_LOG, answers the pinned
    --version assert (P4), then passes `uv run --directory ...` through by
    shifting the `run --directory <dir>` prefix and exec-ing the rest."""
    return (
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f'  echo "uv {version}"\n'
        "  exit 0\n"
        "fi\n"
        'echo "uv $*" >> "$BOOTSTRAP_TEST_LOG"\n'
        "shift 3\n"
        'exec "$@"\n'
    )


def _scrubbed_env(**overrides: str) -> dict[str, str]:
    """A controlled env for bootstrap subprocesses: drop ambient ANSIBLE_/XDG_/UV_
    vars so nothing from the dev host leaks into the smoke run, and scrub
    BASH_ENV/ENV/PROMPT_COMMAND so no init file from the dev host is sourced.
    Also drops the script's own documented overrides and bash behavioral vars
    (BOOTSTRAP_CONTAINER_ENGINE, IFS, POSIXLY_CORRECT) so a dev host exporting
    any of them cannot change the script's semantics under test (confirmation CR
    2026-08-15). The host PATH is retained (so dirname/readlink/timeout/mktemp/sed
    resolve naturally) with the stub dir PREPENDED so stubs shadow host binaries."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ANSIBLE_", "XDG_", "UV_", "BOOTSTRAP_CONTAINER_"))
        and k not in ("BASH_ENV", "ENV", "PROMPT_COMMAND", "IFS", "POSIXLY_CORRECT")
    }
    env.update(overrides)
    return env


class TestBootstrapScriptRuntime:
    def test_invokes_stages_in_order_with_stubbed_path(self) -> None:
        """Runtime smoke test: stub podman/uv/ansible-galaxy/dotfiles-provision
        on a temp PATH and assert the script invokes the container-engine probe
        and the three stages in order — collections → bootstrap → verify (uv
        preseed skipped because uv is present). Structural tests alone can miss
        a silent no-op."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()

            _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))
            # Silent sudo stub (exit 0, no logging): these smoke tests simulate
            # a passwordless host, so the pre-bootstrap `sudo -n true` probe
            # passes and the stage log stays exact.
            _make_stub(bin_dir / "sudo", "#!/bin/sh\nexit 0\n")
            for name in ("uv", "ansible-galaxy", "dotfiles-provision"):
                if name == "ansible-galaxy":
                    _make_stub(
                        bin_dir / name,
                        '#!/bin/sh\necho "ansible-galaxy $*" >> "$BOOTSTRAP_TEST_LOG"\n'
                        'mkdir -p "$HOME/.ansible/collections/ansible_collections"\n'
                        'touch "$HOME/.ansible/collections/ansible_collections/.stub"\n'
                        "exit 0\n",
                    )
                elif name == "uv":
                    _make_stub(bin_dir / name, _uv_passthrough_stub())
                else:
                    _make_stub(bin_dir / name, _echo_stub(name, "exit 0"))

            env = _scrubbed_env(
                PATH=f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
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

            prov_dir = str(_SCRIPT.parent / "src" / "provisioning")
            req = str(_SCRIPT.parent / "src" / "provisioning" / "ansible" / "requirements.yml")
            expected = [
                "podman info",
                f"uv run --directory {prov_dir} ansible-galaxy collection install -r {req}",
                f"ansible-galaxy collection install -r {req}",
                f"uv run --directory {prov_dir} dotfiles-provision bootstrap",
                "dotfiles-provision bootstrap",
                f"uv run --directory {prov_dir} dotfiles-provision verify",
                "dotfiles-provision verify",
            ]
            actual = [line for line in log.read_text().splitlines() if line.strip()]
            assert actual == expected, (
                "bootstrap.sh must probe the engine, then invoke, in order: "
                "collections → bootstrap → verify, each through `uv run "
                "--directory`; got:\n" + "\n".join(actual)
            )

    def test_fails_loud_when_no_engine_is_usable(self) -> None:
        """LOCKED Option A: with podman/docker present on PATH but UNUSABLE
        (their `info` probe fails, e.g. a stopped daemon), the script aborts
        non-zero with a helpful message BEFORE running any provisioning stage.
        The gate is usability, not mere presence."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()

            for name in ("podman", "docker"):
                _make_stub(bin_dir / name, _echo_stub(name, "exit 1"))
            _make_stub(bin_dir / "uv", _echo_stub("uv", "exit 0"))

            env = _scrubbed_env(
                PATH=f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
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
                "script must fail loud when no container engine is usable"
            )
            output = result.stdout + result.stderr
            assert "no container engine" in output, (
                "the abort must carry a helpful message naming the requirement"
            )
            log_lines = log.read_text().splitlines()
            assert log_lines == ["podman info", "docker info"], (
                "the engine probes must run, but no provisioning stage may "
                "execute before the abort; got:\n" + "\n".join(log_lines)
            )

    def test_collections_failure_aborts_with_true_exit_code(self) -> None:
        """A failing ansible-galaxy must abort non-zero with the TRUE exit
        code (an `if ! cmd`-style negation bug once reported 0 for real
        failures) and surface the command's own stderr."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()

            _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))
            _make_stub(bin_dir / "uv", _uv_passthrough_stub())
            _make_stub(
                bin_dir / "ansible-galaxy",
                "#!/bin/sh\n"
                'echo "ansible-galaxy $*" >> "$BOOTSTRAP_TEST_LOG"\n'
                'echo "galaxy exploded: connection refused" >&2\n'
                "exit 42\n",
            )

            env = _scrubbed_env(
                PATH=f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
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
            assert result.returncode == 42, (
                "the collections abort must propagate ansible-galaxy's true "
                f"exit code; got {result.returncode}"
            )
            output = result.stdout + result.stderr
            assert "collection resolution FAILED (exit code 42)" in output, output
            assert "Requirements file" in output, output
            assert "galaxy exploded: connection refused" in output, (
                "the abort must surface the command's own stderr, not a network-only guess"
            )
            log_lines = log.read_text().splitlines()
            assert not any(line.startswith("dotfiles-provision") for line in log_lines), (
                "no bootstrap stage may run after a collections failure"
            )

    def test_uv_preseed_installs_when_absent(self) -> None:
        """P2 (confirmation CR 2026-08-15): the ENTIRE uv-preseed install branch
        (platform case, download, checksum pipeline, extract, pinned --version
        assert) previously had ZERO behavioral coverage — all runtime tests
        stubbed uv as present. Here uv is ABSENT and uname/mktemp/curl/
        sha256sum/tar are stubbed so the install branch actually executes and
        the script then proceeds through collections → bootstrap → verify."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()

            _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))
            # Silent sudo stub (exit 0, no logging): the post-preseed run must
            # clear the pre-bootstrap `sudo -n true` probe so the stage log
            # stays exact (same passwordless-host simulation as the smoke test).
            _make_stub(bin_dir / "sudo", "#!/bin/sh\nexit 0\n")
            _make_stub(
                bin_dir / "uname",
                '#!/bin/sh\ncase "$1" in\n'
                "  -s) echo Linux ;;\n  -m) echo x86_64 ;;\n  *) exit 1 ;;\nesac\n",
            )
            _make_stub(
                bin_dir / "mktemp",
                '#!/bin/sh\nf="${TMPDIR:-/tmp}/bootstrap-stub.$$"\n: > "$f"\necho "$f"\n',
            )
            _make_stub(
                bin_dir / "curl",
                '#!/bin/sh\nout=""; prev=""\n'
                'for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done\n'
                'printf "stub tarball\\n" > "$out"\nexit 0\n',
            )
            _make_stub(bin_dir / "sha256sum", "#!/bin/sh\ncat >/dev/null\nexit 0\n")
            _make_stub(
                bin_dir / "tar",
                "#!/bin/sh\n"
                'cat > "$HOME/.local/bin/uv" <<"STUB"\n' + _uv_passthrough_stub() + "STUB\n"
                'printf "#!/bin/sh\\nexit 0\\n" > "$HOME/.local/bin/uvx"\n'
                'chmod +x "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx"\n'
                "exit 0\n",
            )
            _make_stub(
                bin_dir / "ansible-galaxy",
                '#!/bin/sh\necho "ansible-galaxy $*" >> "$BOOTSTRAP_TEST_LOG"\n'
                'mkdir -p "$HOME/.ansible/collections/ansible_collections"\n'
                'touch "$HOME/.ansible/collections/ansible_collections/.stub"\n'
                "exit 0\n",
            )
            _make_stub(bin_dir / "dotfiles-provision", _echo_stub("dotfiles-provision", "exit 0"))

            env = _scrubbed_env(
                PATH=f"{bin_dir}:/usr/bin:/bin",
                HOME=str(home),
                TMPDIR=str(tmp_path),
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
            assert "stage preseed: installing uv 0.9.22" in result.stdout, (
                "the absent-uv preseed branch must run the pinned install; "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

            prov_dir = str(_SCRIPT.parent / "src" / "provisioning")
            req = str(_SCRIPT.parent / "src" / "provisioning" / "ansible" / "requirements.yml")
            expected = [
                "podman info",
                f"uv run --directory {prov_dir} ansible-galaxy collection install -r {req}",
                f"ansible-galaxy collection install -r {req}",
                f"uv run --directory {prov_dir} dotfiles-provision bootstrap",
                "dotfiles-provision bootstrap",
                f"uv run --directory {prov_dir} dotfiles-provision verify",
                "dotfiles-provision verify",
            ]
            actual = [line for line in log.read_text().splitlines() if line.strip()]
            assert actual == expected, (
                "after the uv preseed, the stages must run in order "
                "collections → bootstrap → verify; got:\n" + "\n".join(actual)
            )

    def test_fails_loud_when_running_as_root(self) -> None:
        """P5 (confirmation CR 2026-08-15): a root/EUID-0 invocation must abort
        loud BEFORE anything runs — provisioning as root would write the wrong
        home and verify could pass green against it."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()

            _make_stub(bin_dir / "id", '#!/bin/sh\nif [ "$1" = "-u" ]; then echo 0; fi\n')
            _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))

            env = _scrubbed_env(
                PATH=f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
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
            assert result.returncode != 0, "script must fail loud when running as root"
            output = result.stdout + result.stderr
            assert "running as root" in output, output
            log_lines = log.read_text().splitlines() if log.exists() else []
            assert log_lines == [], (
                "no engine probe or stage may run before the root abort; "
                "got:\n" + "\n".join(log_lines)
            )

    def test_fails_loud_when_home_unset(self) -> None:
        """P5 (confirmation CR 2026-08-15): a $HOME-unset context (cron/systemd/
        sudo -H) must abort loud with a helpful message — no cryptic set -u
        error, no `/.local/bin` PATH pollution."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()

            _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))

            env = _scrubbed_env(
                PATH=f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                HOME="",
                BOOTSTRAP_TEST_LOG=str(log),
            )
            result = subprocess.run(
                [bash, str(_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode != 0, "script must fail loud when $HOME is unset"
            output = result.stdout + result.stderr
            assert "HOME is unset" in output, output
            log_lines = log.read_text().splitlines() if log.exists() else []
            assert log_lines == [], (
                "no engine probe or stage may run before the HOME abort; "
                "got:\n" + "\n".join(log_lines)
            )

    def test_failing_sudo_probe_aborts_loud_without_terminal(self) -> None:
        """A host without passwordless escalation running non-interactively
        (stdin DEVNULL — no terminal to prompt on) must abort with exit 2
        naming the cause AFTER collections but BEFORE the bootstrap stage —
        never hang on a prompt and never fail deep in the aggregate."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home = tmp_path / "home"
            log = tmp_path / "invocations.log"
            bin_dir.mkdir()
            home.mkdir()

            _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))
            _make_stub(bin_dir / "uv", _uv_passthrough_stub())
            _make_stub(
                bin_dir / "ansible-galaxy",
                '#!/bin/sh\necho "ansible-galaxy $*" >> "$BOOTSTRAP_TEST_LOG"\n'
                'mkdir -p "$HOME/.ansible/collections/ansible_collections"\n'
                'touch "$HOME/.ansible/collections/ansible_collections/.stub"\n'
                "exit 0\n",
            )
            # Failing sudo stub: simulates a host where escalation needs a
            # password. Silent (no logging) so the stage log stays exact.
            _make_stub(bin_dir / "sudo", "#!/bin/sh\nexit 1\n")
            _make_stub(bin_dir / "dotfiles-provision", _echo_stub("dotfiles-provision", "exit 0"))

            env = _scrubbed_env(
                PATH=f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                HOME=str(home),
                BOOTSTRAP_TEST_LOG=str(log),
            )
            result = subprocess.run(
                [bash, str(_SCRIPT)],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                env=env,
                timeout=120,
            )
            assert result.returncode == 2, (
                "the non-terminal escalation abort must exit 2; "
                f"got {result.returncode}"
            )
            output = result.stdout + result.stderr
            assert "stdin is not a terminal" in output, output
            log_lines = log.read_text().splitlines()
            assert any(line.startswith("ansible-galaxy") for line in log_lines), (
                "collections must run before the escalation abort; got:\n"
                + "\n".join(log_lines)
            )
            assert not any(
                line.startswith("dotfiles-provision bootstrap") for line in log_lines
            ), (
                "no bootstrap stage may run after the escalation abort; got:\n"
                + "\n".join(log_lines)
            )


def _stubbed_provision_env(
    tmp_path: Path, *, sudo_stub: str = "#!/bin/sh\nexit 0\n"
) -> tuple[Path, Path, dict[str, str]]:
    """Shared hermetic env for the session-signal tests: stubbed podman/sudo
    (passwordless host), uv passthrough, collections, provisioner and
    hyprctl (no Hyprland IPC, so the session signal stays silent). Returns
    (bin_dir, log, env)."""
    import os as _os

    bin_dir = tmp_path / "bin"
    home = tmp_path / "home"
    log = tmp_path / "invocations.log"
    state = tmp_path / "state"
    bin_dir.mkdir()
    home.mkdir()
    state.mkdir()

    _make_stub(bin_dir / "podman", _echo_stub("podman", "exit 0"))
    _make_stub(bin_dir / "sudo", sudo_stub)
    _make_stub(bin_dir / "uv", _uv_passthrough_stub())
    _make_stub(
        bin_dir / "ansible-galaxy",
        '#!/bin/sh\necho "ansible-galaxy $*" >> "$BOOTSTRAP_TEST_LOG"\n'
        'mkdir -p "$HOME/.ansible/collections/ansible_collections"\n'
        'touch "$HOME/.ansible/collections/ansible_collections/.stub"\n'
        "exit 0\n",
    )
    _make_stub(bin_dir / "dotfiles-provision", _echo_stub("dotfiles-provision", "exit 0"))
    _make_stub(bin_dir / "hyprctl", _echo_stub("hyprctl", "exit 1"))

    env = _scrubbed_env(
        PATH=f"{bin_dir}:{_os.environ.get('PATH', '/usr/bin:/bin')}",
        HOME=str(home),
        BOOTSTRAP_TEST_LOG=str(log),
        BOOTSTRAP_TEST_TMP=str(state),
    )
    return bin_dir, log, env


class TestGloviewSessionSignalFile:
    def test_signal_probes_reports_without_sync_stage(self) -> None:
        """The post-verify session signal probes via PATH-resolved
        `hyprctl plugin list`, reports loaded vs DEGRADED, and names the
        login activator — with no sync stage anywhere: no `hyprpm`
        invocation, no aggregate re-run, all without hardcoded system paths."""
        assert "hyprctl plugin list" in _TEXT, "the session signal must probe the loaded plugins"
        assert "DEGRADED" in _TEXT, "a loaded-but-absent plugin must be named DEGRADED"
        assert "gloview-activate" in _TEXT, "recovery must name the login activator"
        assert "hyprpm update" not in _TEXT, "no foreground hyprpm sync may remain"
        assert "hyprpm list" not in _TEXT, "no hyprpm probe may remain"
        assert "gloview retry" not in _TEXT, "the aggregate must never re-run for GloView"
        assert "gloview-sync" not in _TEXT, "the sync stage must be gone entirely"

    def test_signal_never_fails_the_run(self) -> None:
        """The session signal is report-only: the post-verify block must not
        call stage_failed — a TTY provision stays green with the plugin
        loading at first login."""
        signal_block = _TEXT.split("Post-verify GloView session signal", 1)[1]
        assert "stage_failed" not in signal_block, (
            "the session signal must report, never fail the run"
        )

    def test_single_password_entry_with_timestamp_keepalive(self) -> None:
        """Stage 3 prompts once and reuses the secret: `sudo -Sv` validation
        (three attempts), ANSIBLE_SUDO_PASS export for the aggregate, and a
        timestamp keepalive (killed on exit) for late sudo calls."""
        assert "sudo -Sv" in _TEXT, "the entered secret must be validated up front"
        assert "ANSIBLE_SUDO_PASS" in _TEXT, "the secret must be exported for reuse"
        assert "_sudo_keepalive_pid" in _TEXT, "the keepalive pid must be tracked"
        assert 'kill "$_sudo_keepalive_pid"' in _TEXT, (
            "the exit trap must kill the keepalive so no refresh loop outlives the run"
        )


class TestGloviewSessionSignalRuntime:
    def test_single_aggregate_run_no_sync_stage(self) -> None:
        """No sync stage exists anymore: one aggregate run, one verify,
        exit 0, no hyprpm invocation in the log."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            _, log, env = _stubbed_provision_env(Path(tmp))
            result = subprocess.run(
                [bash, str(_SCRIPT)],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            lines = log.read_text().splitlines()
            assert sum(1 for l in lines if l == "dotfiles-provision bootstrap") == 1
            assert sum(1 for l in lines if l == "dotfiles-provision verify") == 1
            assert not any(l.startswith("hyprpm") for l in lines), (
                "no hyprpm invocation may remain; got:\n" + "\n".join(lines)
            )

    def test_session_signal_silent_without_ipc(self) -> None:
        """No Hyprland IPC (stubbed hyprctl fails) → the session signal stays
        silent: no DEGRADED, still exit 0 with the Bootstrap complete line."""
        bash = _require_bash()
        with tempfile.TemporaryDirectory() as tmp:
            _, _, env = _stubbed_provision_env(Path(tmp))
            result = subprocess.run(
                [bash, str(_SCRIPT)],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            output = result.stdout + result.stderr
            assert "DEGRADED" not in output, output
            assert "Bootstrap complete" in output, output

    def _sudo_tty_only_stub(self) -> str:
        """A sudo stub modeling a password host where terminal sudo works but
        detached sudo never does (the live 2026-09-29 finding: a warm terminal
        ticket is invisible to piped sudo). `sudo -Sv` (password validation
        over a pipe) always succeeds; ticket checks (`-n`, attached or not)
        succeed only on a tty."""
        return (
            "#!/bin/sh\n"
            'echo "sudo $*" >> "$BOOTSTRAP_TEST_LOG"\n'
            'if [ "$1" = "-Sv" ]; then exit 0; fi\n'
            "if [ -t 0 ]; then exit 0; else exit 1; fi\n"
        )

    def _run_under_pty(
        self, env: dict[str, str], stdin_text: str = ""
    ) -> subprocess.CompletedProcess[str]:
        """Run the script with terminal stdin via a python pty (deterministic:
        waits for the BECOME prompt, answers with `stdin_text`, drains to
        exit). `script(1)` cannot drive this — it never delivers piped stdin
        to the child, so `read` blocks forever under it."""
        bash = _require_bash()
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [bash, str(_SCRIPT)],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
        )
        os.close(slave)
        chunks: list[bytes] = []
        seen = b""
        password_lines = stdin_text.splitlines()
        sent = 0
        deadline = time.monotonic() + 150
        try:
            os.set_blocking(master, False)
            while True:
                if proc.poll() is not None:
                    try:
                        while True:
                            chunk = os.read(master, 65536)
                            if not chunk:
                                break
                            chunks.append(chunk)
                    except OSError:
                        pass
                    break
                ready, _, _ = select.select([master], [], [], 1.0)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    chunks.append(chunk)
                    seen += chunk
                    prompts = seen.count(b"BECOME password:")
                    while sent < prompts and sent < len(password_lines):
                        os.write(master, (password_lines[sent] + "\n").encode())
                        sent += 1
                if time.monotonic() > deadline:
                    proc.kill()
                    proc.wait()
                    text = (
                        b"".join(chunks).decode("utf-8", errors="replace").replace("\r\n", "\n")
                    )
                    pytest.fail(f"pty run exceeded deadline; output:\n{text}")
        finally:
            os.close(master)
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        text = b"".join(chunks).decode("utf-8", errors="replace").replace("\r\n", "\n")
        return subprocess.CompletedProcess(
            args=[bash, str(_SCRIPT)],
            returncode=proc.returncode,
            stdout=text,
            stderr="",
        )

    def test_password_asked_once_up_front_on_tty(self) -> None:
        """Password host + terminal: the single hidden prompt reads one line,
        the secret validates once (`sudo -Sv`), and no --ask-become-pass
        appears on the aggregate invocation — the full fresh-machine flow
        (aggregate, verify) exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            _, log, env = _stubbed_provision_env(
                Path(tmp),
                sudo_stub=self._sudo_tty_only_stub(),
            )
            result = self._run_under_pty(env, stdin_text="testpass\ntestpass\ntestpass\n")
            assert result.returncode == 0, result.stdout + result.stderr
            lines = log.read_text().splitlines()
            assert lines.count("sudo -Sv") == 1, (
                "the entered secret must validate exactly once up front; got:\n"
                + "\n".join(lines)
            )
            assert not any("ask-become-pass" in l for l in lines), (
                "no per-invocation become prompt may survive the single prompt; got:\n"
                + "\n".join(lines)
            )
            assert lines.count("dotfiles-provision bootstrap") == 1, (
                "fresh machine must run the aggregate exactly once; got:\n"
                + "\n".join(lines)
            )

    def test_warm_terminal_ticket_still_prompts_on_tty(self) -> None:
        """Regression (live 2026-09-29 failure): a warm terminal ticket must
        NOT skip the prompt — detached sudo stays failing, so the detached
        probe fails and the single prompt runs. The stub grants every
        terminal-attached sudo (warm from the start) yet denies detached ones;
        the script must still validate once via `sudo -Sv`."""
        with tempfile.TemporaryDirectory() as tmp:
            _, log, env = _stubbed_provision_env(
                Path(tmp),
                sudo_stub=self._sudo_tty_only_stub(),
            )
            result = self._run_under_pty(env, stdin_text="testpass\ntestpass\ntestpass\n")
            assert result.returncode == 0, result.stdout + result.stderr
            lines = log.read_text().splitlines()
            assert lines.count("sudo -Sv") == 1, (
                "a warm terminal ticket must still prompt+validate once; got:\n"
                + "\n".join(lines)
            )
            assert not any("ask-become-pass" in l for l in lines), (
                "no per-invocation become prompt may appear; got:\n" + "\n".join(lines)
            )
