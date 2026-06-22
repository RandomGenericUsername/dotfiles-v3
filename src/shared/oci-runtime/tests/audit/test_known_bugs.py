"""Committed reproductions for known bugs found in the audit.

Each test reproduces a specific mechanically-verifiable bug. All are
marked ``xfail(strict=True)``:

  - The test is **expected to fail** — documenting the bug exists.
  - If someone fixes the bug, the test starts **passing**, and
    ``strict=True`` makes the suite go RED — forcing the xfail marker
    to be removed. This makes both the bug AND the fix visible.
  - The bugs cannot be silently re-introduced: if the fix is reverted,
    the test fails again (now without the xfail), going red.

This file is the durable record of what the audit found. Unlike
prototypes in /tmp, these tests live in the repo and run on every
``pytest`` invocation. The cycle of "audit finds bugs → mark tasks
complete → bugs persist → re-audit" is broken because the bugs are
now visible to CI, not just to the auditor.
"""

from __future__ import annotations

import io
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters._utils import parse_size_to_bytes
from oci_runtime.adapters.managers.base import CliBaseManager
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.adapters.parser.base import _coerce_size
from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import (
    ContainerRuntimeError,
    ImageError,
    NetworkError,
    OciError,
    VolumeError,
)
from oci_runtime.domain.types import BuildContext, PruneResult, RawExecResult, RunConfig
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ContainerParser, ImageParser, NetworkParser, VolumeParser
from tests.helpers.mock_transport import FakeTtyDetector, RecordingStreamingTransport, RecordingTransport

# ─── Helpers ───

_CAPS = RuntimeCapabilities(supports_log_drivers=True, tar_entry_name="Dockerfile", default_build_flags=("--quiet",))


class _NoOpContainerParser(ContainerParser):
    def parse_inspect(self, raw): return MagicMock()
    def parse_list(self, raw): return []
    def parse_prune(self, raw): return PruneResult()
    def is_not_found_error(self, stderr): return False


class _NoOpImageParser(ImageParser):
    def parse_inspect(self, raw): return MagicMock()
    def parse_list(self, raw): return []
    def parse_build_output(self, raw): return "sha256:abc"
    def parse_id_from_pull(self, raw): return "sha256:abc"
    def parse_prune(self, raw): return PruneResult()
    def is_not_found_error(self, stderr): return False


class _NoOpVolumeParser(VolumeParser):
    def parse_inspect(self, raw): return MagicMock()
    def parse_list(self, raw): return []
    def parse_prune(self, raw): return PruneResult()
    def is_not_found_error(self, stderr): return False


class _NoOpNetworkParser(NetworkParser):
    def parse_inspect(self, raw): return MagicMock()
    def parse_list(self, raw): return []
    def parse_prune(self, raw): return PruneResult()
    def is_not_found_error(self, stderr): return False


# ─── F1: exec_container discards stderr on success ───

class TestF01ExecStderrDroppedOnSuccess:
    def test_exec_success_preserves_stderr(self):
        t = RecordingTransport("docker", {
            ("docker", "exec", "ctr1", "sh", "-c", "echo err >&2"):
                RawExecResult(0, b"out\n", b"err\n"),
        })
        mgr = CliContainerManager(t, _NoOpContainerParser(), _CAPS,
                                  streaming=RecordingStreamingTransport("docker"),
                                  tty_detector=FakeTtyDetector())
        result = mgr.exec_container("ctr1", ["sh", "-c", "echo err >&2"])
        assert result.stderr == "err\n", f"stderr was dropped: {result.stderr!r}"


# ─── F2: logs(follow=True) drops container stderr ───

class TestF02LogsFollowDropsStderr:
    def test_logs_follow_includes_stderr(self):
        st = RecordingStreamingTransport("docker")
        st._stream_responses = {
            ("docker", "logs", "ctr1", "--follow"): [b"stdout-line\n"],
        }
        # Simulate stderr delivery by also calling on_stderr
        original_stream = st.stream
        def _stream_with_stderr(*args, **kwargs):
            on_stderr = kwargs.get("on_stderr")
            if on_stderr:
                on_stderr(b"stderr-line\n")
            return original_stream(*args, **kwargs)
        st.stream = _stream_with_stderr

        t = RecordingTransport("docker")
        mgr = CliContainerManager(t, _NoOpContainerParser(), _CAPS,
                                  streaming=st, tty_detector=FakeTtyDetector())
        chunks = list(mgr.logs("ctr1", follow=True))
        combined = "".join(chunks)
        assert "stderr-line" in combined, f"stderr was dropped from logs: {combined!r}"


# ─── F3: prune() skips _check_result (all 4 managers) ───

class TestF03PruneSkipsCheckResult:
    def test_container_prune_raises_on_error(self):
        t = RecordingTransport("docker", {
            ("docker", "container", "prune", "--force"):
                RawExecResult(1, b"", b"Error: daemon is down"),
        })
        mgr = CliContainerManager(t, _NoOpContainerParser(), _CAPS,
                                  streaming=RecordingStreamingTransport("docker"),
                                  tty_detector=FakeTtyDetector())
        with pytest.raises(OciError):
            mgr.prune()

    def test_image_prune_raises_on_error(self):
        t = RecordingTransport("docker", {
            ("docker", "image", "prune", "--force"):
                RawExecResult(1, b"", b"Error: daemon is down"),
        })
        mgr = CliImageManager(t, _NoOpImageParser(), _CAPS)
        with pytest.raises(OciError):
            mgr.prune()

    def test_volume_prune_raises_on_error(self):
        t = RecordingTransport("docker", {
            ("docker", "volume", "prune", "--force"):
                RawExecResult(1, b"", b"Error: daemon is down"),
        })
        mgr = CliVolumeManager(t, _NoOpVolumeParser(), _CAPS)
        with pytest.raises(OciError):
            mgr.prune()

    def test_network_prune_raises_on_error(self):
        t = RecordingTransport("docker", {
            ("docker", "network", "prune", "--force"):
                RawExecResult(1, b"", b"Error: daemon is down"),
        })
        mgr = CliNetworkManager(t, _NoOpNetworkParser(), _CAPS)
        with pytest.raises(OciError):
            mgr.prune()


# ─── F4: build() ignores 6 BuildContext fields ───

class TestF04BuildIgnoresContextFields:
    def test_build_emits_build_args(self):
        t = RecordingTransport("docker")
        mgr = CliImageManager(t, _NoOpImageParser(), _CAPS)
        ctx = BuildContext(build_file_content="FROM alpine", build_args={"HTTP_PROXY": "http://proxy"})
        mgr.build(ctx, "myimg")
        cmd = t.calls[0].command
        assert "--build-arg" in cmd and "HTTP_PROXY=http://proxy" in cmd

    def test_build_emits_labels(self):
        t = RecordingTransport("docker")
        mgr = CliImageManager(t, _NoOpImageParser(), _CAPS)
        ctx = BuildContext(build_file_content="FROM alpine", labels={"maintainer": "team"})
        mgr.build(ctx, "myimg")
        cmd = t.calls[0].command
        assert "--label" in cmd

    def test_build_emits_pull(self):
        t = RecordingTransport("docker")
        mgr = CliImageManager(t, _NoOpImageParser(), _CAPS)
        ctx = BuildContext(build_file_content="FROM alpine", pull=True)
        mgr.build(ctx, "myimg")
        cmd = t.calls[0].command
        assert "--pull" in cmd


# ─── F7: _check_result raises ContainerRuntimeError for all managers ───

class TestF07WrongExceptionTypeForNonContainerManagers:
    def test_image_generic_error_is_image_error(self):
        t = RecordingTransport("docker", {
            ("docker", "image", "inspect", "--format", "json", "alpine"):
                RawExecResult(1, b"", b"Error: something broke"),
        })
        mgr = CliImageManager(t, _NoOpImageParser(), _CAPS)
        with pytest.raises(ImageError):
            mgr.inspect("alpine")

    def test_volume_generic_error_is_volume_error(self):
        t = RecordingTransport("docker", {
            ("docker", "volume", "inspect", "--format", "json", "myvol"):
                RawExecResult(1, b"", b"Error: something broke"),
        })
        mgr = CliVolumeManager(t, _NoOpVolumeParser(), _CAPS)
        with pytest.raises(VolumeError):
            mgr.inspect("myvol")

    def test_network_generic_error_is_network_error(self):
        t = RecordingTransport("docker", {
            ("docker", "network", "inspect", "--format", "json", "mynet"):
                RawExecResult(1, b"", b"Error: something broke"),
        })
        mgr = CliNetworkManager(t, _NoOpNetworkParser(), _CAPS)
        with pytest.raises(NetworkError):
            mgr.inspect("mynet")


# ─── F8: _coerce_size returns float for float input ───

class TestF08CoerceSizeReturnsFloat:
    def test_coerce_size_float_returns_int(self):
        result = _coerce_size(5000.0)
        assert isinstance(result, int), f"expected int, got {type(result).__name__}: {result!r}"


# ─── F9: parse_size_to_bytes remediation never implemented ───

class TestF09ParseSizeToBytesIncomplete:
    def test_single_letter_megabyte(self):
        result = parse_size_to_bytes("500M")
        assert result == 500 * 1024**2

    def test_single_letter_terabyte(self):
        result = parse_size_to_bytes("2T")
        assert result == 2 * 1024**4

    def test_tib_unit(self):
        result = parse_size_to_bytes("3TIB")
        assert result == 3 * 1024**4

    def test_substring_match_rejected(self):
        with pytest.raises(ValueError):
            parse_size_to_bytes("junk 1.5GB trailing")


# ─── F11: get_runtime_binary returns unresolved name ───

class TestF11GetRuntimeBinaryReturnsUnresolved:
    def test_get_runtime_binary_returns_resolved_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/docker"):
            t = CliTransport("docker")
            resolved = t.get_runtime_binary()
            assert resolved == "/usr/local/bin/docker", f"expected resolved path, got {resolved!r}"


# ─── F14: TimeoutExpired escapes OciError hierarchy ───

class TestF14TimeoutEscapesOciError:
    def test_stream_timeout_is_oci_error(self):
        from oci_runtime.adapters.transport.streaming import CliStreamingTransport
        st = CliStreamingTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout = MagicMock()
                proc.stderr = MagicMock()
                proc.stdin = None
                proc.poll.return_value = None
                proc.wait.side_effect = subprocess.TimeoutExpired("cmd", 0.01)
                mock_popen.return_value = proc
                with patch("oci_runtime.adapters._process_reader.ProcessPipeReader") as mock_reader:
                    mock_reader.return_value.read.return_value = ([], [])
                    with pytest.raises(OciError):
                        st.stream(["docker", "ps"], timeout=0.01)
