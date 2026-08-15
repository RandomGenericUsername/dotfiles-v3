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

            prov_dir = str(_SCRIPT.parent.parent / "src" / "provisioning")
            req = str(
                _SCRIPT.parent.parent / "src" / "provisioning" / "ansible" / "requirements.yml"
            )
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

            prov_dir = str(_SCRIPT.parent.parent / "src" / "provisioning")
            req = str(
                _SCRIPT.parent.parent / "src" / "provisioning" / "ansible" / "requirements.yml"
            )
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
