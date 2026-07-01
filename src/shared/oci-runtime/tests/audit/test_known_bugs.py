"""Regression tests for bugs found in the audit.

These tests WERE marked xfail(strict=True) to document known bugs.
All bugs were fixed in commit 15f6238 (guardrail remediation).
The xfail markers were removed, and these tests now PASS as
regression guards — if a bug is reintroduced, the test fails.

The cycle of "audit finds bugs → mark tasks complete → bugs persist
→ re-audit" is broken because these tests run on every pytest
invocation, not just during audits.
"""

from __future__ import annotations

import io
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters._utils import parse_size_to_bytes
from oci_runtime.adapters.parser.docker import DockerContainerParser
from oci_runtime.domain.json_parsing import parse_json_item
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.domain.size_parsing import coerce_size
from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import (
    ContainerRuntimeError,
    ImageError,
    NetworkError,
    OciError,
    VolumeError,
)
from oci_runtime.domain.types import (
    BuildContext,
    PortMapping,
    PruneResult,
    RawExecResult,
    RunConfig,
)
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    NetworkNotFoundError,
    NetworkRuntimeError,
    ParsingError,
    VolumeNotFoundError,
    VolumeRuntimeError,
)
from oci_runtime.ports.cancellation import ThreadCancellationToken
from tests.helpers.mock_transport import (
    FakeTtyDetector,
    MockPtyTransport,
    MockResultChecker,
    MockListExecutor,
    RecordingStreamingTransport,
    RecordingTransport,
)

# ─── Helpers ───

_CAPS = RuntimeCapabilities(
    supports_log_drivers=True,
    tar_entry_name="Dockerfile",
    default_build_flags=("--quiet",),
)


def _image_mgr(transport, parser, caps):
    chk = CliResultChecker(
        generic_error=ImageRuntimeError,
        not_found_error=ImageNotFoundError,
        is_not_found=parser.is_not_found_error,
        auth_error=ImagePullAccessDeniedError,
        is_auth=parser.is_auth_error,
    )
    return CliImageManager(
        transport,
        parser,
        caps,
        result_checker=chk,
        list_executor=CliListExecutor(
            transport, caps, chk, parse_list=parser.parse_list
        ),
    )


def _container_mgr(transport, parser, caps, streaming, **extra):
    chk = CliResultChecker(
        generic_error=ContainerRuntimeError,
        not_found_error=ContainerNotFoundError,
        is_not_found=parser.is_not_found_error,
    )
    return CliContainerManager(
        transport,
        parser,
        caps,
        streaming=streaming,
        tty_detector=FakeTtyDetector(),
        pty_transport=MockPtyTransport(),
        cancellation_factory=lambda: ThreadCancellationToken(),
        result_checker=chk,
        list_executor=CliListExecutor(
            transport, caps, chk, parse_list=parser.parse_list
        ),
        **extra,
    )


def _volume_mgr(transport, parser, caps):
    chk = CliResultChecker(
        generic_error=VolumeRuntimeError,
        not_found_error=VolumeNotFoundError,
        is_not_found=parser.is_not_found_error,
    )
    return CliVolumeManager(
        transport,
        parser,
        caps,
        result_checker=chk,
        list_executor=CliListExecutor(
            transport, caps, chk, parse_list=parser.parse_list
        ),
    )


def _network_mgr(transport, parser, caps):
    chk = CliResultChecker(
        generic_error=NetworkRuntimeError,
        not_found_error=NetworkNotFoundError,
        is_not_found=parser.is_not_found_error,
    )
    return CliNetworkManager(
        transport,
        parser,
        caps,
        result_checker=chk,
        list_executor=CliListExecutor(
            transport, caps, chk, parse_list=parser.parse_list
        ),
    )


class _NoOpContainerParser(ContainerParser):
    def parse_inspect(self, raw):
        return MagicMock()

    def parse_list(self, raw):
        return []

    def parse_prune(self, raw):
        return PruneResult()

    def is_not_found_error(self, stderr):
        return False

    def is_auth_error(self, stderr):
        return False


class _NoOpImageParser(ImageParser):
    def parse_inspect(self, raw):
        return MagicMock()

    def parse_list(self, raw):
        return []

    def parse_build_output(self, raw):
        return "sha256:abc"

    def parse_digest_from_pull(self, raw):
        return "sha256:abc"

    def parse_prune(self, raw):
        return PruneResult()

    def is_not_found_error(self, stderr):
        return False

    def is_auth_error(self, stderr):
        return False


class _NoOpVolumeParser(VolumeParser):
    def parse_inspect(self, raw):
        return MagicMock()

    def parse_list(self, raw):
        return []

    def parse_prune(self, raw):
        return PruneResult()

    def is_not_found_error(self, stderr):
        return False

    def is_auth_error(self, stderr):
        return False


class _NoOpNetworkParser(NetworkParser):
    def parse_inspect(self, raw):
        return MagicMock()

    def parse_list(self, raw):
        return []

    def parse_prune(self, raw):
        return PruneResult()

    def is_not_found_error(self, stderr):
        return False

    def is_auth_error(self, stderr):
        return False


# ─── F1: exec_container discards stderr on success ───


class TestF01ExecStderrDroppedOnSuccess:
    def test_exec_success_preserves_stderr(self):
        t = RecordingTransport(
            "docker",
            {
                ("docker", "exec", "ctr1", "sh", "-c", "echo err >&2"): RawExecResult(
                    0, b"out\n", b"err\n"
                ),
            },
        )
        mgr = _container_mgr(
            t,
            _NoOpContainerParser(),
            _CAPS,
            streaming=RecordingStreamingTransport("docker"),
        )
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
        mgr = _container_mgr(t, _NoOpContainerParser(), _CAPS, streaming=st)
        chunks = list(mgr.logs("ctr1", follow=True))
        combined = "".join(chunks)
        assert "stderr-line" in combined, f"stderr was dropped from logs: {combined!r}"


# ─── F3: prune() skips _check_result (all 4 managers) ───


class TestF03PruneSkipsCheckResult:
    def test_container_prune_raises_on_error(self):
        t = RecordingTransport(
            "docker",
            {
                ("docker", "container", "prune", "--force"): RawExecResult(
                    1, b"", b"Error: daemon is down"
                ),
            },
        )
        mgr = _container_mgr(
            t,
            _NoOpContainerParser(),
            _CAPS,
            streaming=RecordingStreamingTransport("docker"),
        )
        with pytest.raises(OciError):
            mgr.prune()

    def test_image_prune_raises_on_error(self):
        t = RecordingTransport(
            "docker",
            {
                ("docker", "image", "prune", "--force"): RawExecResult(
                    1, b"", b"Error: daemon is down"
                ),
            },
        )
        mgr = _image_mgr(t, _NoOpImageParser(), _CAPS)
        with pytest.raises(OciError):
            mgr.prune()

    def test_volume_prune_raises_on_error(self):
        t = RecordingTransport(
            "docker",
            {
                ("docker", "volume", "prune", "--force"): RawExecResult(
                    1, b"", b"Error: daemon is down"
                ),
            },
        )
        mgr = _volume_mgr(t, _NoOpVolumeParser(), _CAPS)
        with pytest.raises(OciError):
            mgr.prune()

    def test_network_prune_raises_on_error(self):
        t = RecordingTransport(
            "docker",
            {
                ("docker", "network", "prune", "--force"): RawExecResult(
                    1, b"", b"Error: daemon is down"
                ),
            },
        )
        mgr = _network_mgr(t, _NoOpNetworkParser(), _CAPS)
        with pytest.raises(OciError):
            mgr.prune()


# ─── F4: build() ignores 6 BuildContext fields ───


class TestF04BuildIgnoresContextFields:
    def test_build_emits_build_args(self):
        t = RecordingTransport("docker")
        mgr = _image_mgr(t, _NoOpImageParser(), _CAPS)
        ctx = BuildContext(
            build_file_content="FROM alpine", build_args={"HTTP_PROXY": "http://proxy"}
        )
        mgr.build(ctx, "myimg")
        cmd = t.calls[0].command
        assert "--build-arg" in cmd and "HTTP_PROXY=http://proxy" in cmd

    def test_build_emits_labels(self):
        t = RecordingTransport("docker")
        mgr = _image_mgr(t, _NoOpImageParser(), _CAPS)
        ctx = BuildContext(
            build_file_content="FROM alpine", labels={"maintainer": "team"}
        )
        mgr.build(ctx, "myimg")
        cmd = t.calls[0].command
        assert "--label" in cmd

    def test_build_emits_pull(self):
        t = RecordingTransport("docker")
        mgr = _image_mgr(t, _NoOpImageParser(), _CAPS)
        ctx = BuildContext(build_file_content="FROM alpine", pull=True)
        mgr.build(ctx, "myimg")
        cmd = t.calls[0].command
        assert "--pull" in cmd


# ─── F7: _check_result raises ContainerRuntimeError for all managers ───


class TestF07WrongExceptionTypeForNonContainerManagers:
    def test_image_generic_error_is_image_error(self):
        t = RecordingTransport(
            "docker",
            {
                (
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "json",
                    "alpine",
                ): RawExecResult(1, b"", b"Error: something broke"),
            },
        )
        mgr = _image_mgr(t, _NoOpImageParser(), _CAPS)
        with pytest.raises(ImageError):
            mgr.inspect("alpine")

    def test_volume_generic_error_is_volume_error(self):
        t = RecordingTransport(
            "docker",
            {
                (
                    "docker",
                    "volume",
                    "inspect",
                    "--format",
                    "json",
                    "myvol",
                ): RawExecResult(1, b"", b"Error: something broke"),
            },
        )
        mgr = _volume_mgr(t, _NoOpVolumeParser(), _CAPS)
        with pytest.raises(VolumeError):
            mgr.inspect("myvol")

    def test_network_generic_error_is_network_error(self):
        t = RecordingTransport(
            "docker",
            {
                (
                    "docker",
                    "network",
                    "inspect",
                    "--format",
                    "json",
                    "mynet",
                ): RawExecResult(1, b"", b"Error: something broke"),
            },
        )
        mgr = _network_mgr(t, _NoOpNetworkParser(), _CAPS)
        with pytest.raises(NetworkError):
            mgr.inspect("mynet")


# ─── F8: _coerce_size returns float for float input ───


class TestF08CoerceSizeReturnsFloat:
    def test_coerce_size_float_returns_int(self):
        result = coerce_size(5000.0)
        assert isinstance(result, int), (
            f"expected int, got {type(result).__name__}: {result!r}"
        )


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
        from oci_runtime.adapters.binary import CliBinaryResolver
        with patch("shutil.which", return_value="/usr/local/bin/docker"):
            t = CliTransport("docker", binary_resolver=CliBinaryResolver())
            resolved = t.get_runtime_binary()
            assert resolved == "/usr/local/bin/docker", (
                f"expected resolved path, got {resolved!r}"
            )


# ─── F14: TimeoutExpired escapes OciError hierarchy ───


class TestF14TimeoutEscapesOciError:
    def test_stream_timeout_is_oci_error(self):
        """B2: deadline timeout in streaming transport raises OperationTimeoutError (OciError),
        not subprocess.TimeoutExpired (which was the pre-fix leak)."""
        from oci_runtime.adapters.transport.streaming import CliStreamingTransport

        with patch(
            "oci_runtime.adapters.transport.streaming.DeadlineCancellationToken"
        ) as mock_deadline:
            mock_deadline.return_value.is_cancelled = True
            st = CliStreamingTransport("docker", binary_resolver=MagicMock())
            with patch("shutil.which", return_value="/usr/bin/docker"):
                with patch("subprocess.Popen") as mock_popen:
                    proc = MagicMock()
                    proc.stdout = MagicMock()
                    proc.stderr = MagicMock()
                    proc.stdin = None
                    proc.poll.return_value = None
                    proc.wait.return_value = -1
                    mock_popen.return_value = proc
                    with patch(
                        "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
                    ) as mock_reader:
                        mock_reader.from_process.return_value.read.return_value = (
                            [],
                            [],
                        )
                        with pytest.raises(OciError):
                            st.stream(["docker", "ps"], timeout=0.01)


# ─── A1: HostIp loopback binding ───


class TestA01HostIpLoopbackBinding:
    def test_empty_host_ip_maps_to_none(self):
        parser = DockerContainerParser()
        raw = '{"NetworkSettings": {"Ports": {"80/tcp": [{"HostIp": "", "HostPort": "8080"}]}}}'
        info = parser.parse_inspect(raw)
        assert info.ports == (
            PortMapping(container_port=80, host_port=8080, host_ip=None),
        )

    def test_zero_host_ip_preserved(self):
        parser = DockerContainerParser()
        raw = '{"NetworkSettings": {"Ports": {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}}}'
        info = parser.parse_inspect(raw)
        assert info.ports == (
            PortMapping(container_port=80, host_port=8080, host_ip="0.0.0.0"),
        )

    def test_specific_host_ip_preserved(self):
        parser = DockerContainerParser()
        raw = '{"NetworkSettings": {"Ports": {"80/tcp": [{"HostIp": "192.168.1.1", "HostPort": "8080"}]}}}'
        info = parser.parse_inspect(raw)
        assert info.ports == (
            PortMapping(container_port=80, host_port=8080, host_ip="192.168.1.1"),
        )

    def test_port_flag_host_ip_and_host_port(self):
        transport = RecordingTransport()
        streaming = RecordingStreamingTransport()
        mgr = _container_mgr(transport, DockerContainerParser(), _CAPS, streaming=streaming)
        config = RunConfig(
            image="alpine",
            ports=[PortMapping(container_port=80, host_port=8080, host_ip="127.0.0.1")],
        )
        mgr.run(config)
        cmd = streaming.calls[0].command
        idx_p = cmd.index("-p")
        assert cmd[idx_p + 1] == "127.0.0.1:8080:80/tcp"

    def test_port_flag_host_ip_only(self):
        transport = RecordingTransport()
        streaming = RecordingStreamingTransport()
        mgr = _container_mgr(transport, DockerContainerParser(), _CAPS, streaming=streaming)
        config = RunConfig(
            image="alpine",
            ports=[PortMapping(container_port=80, host_ip="127.0.0.1")],
        )
        mgr.run(config)
        cmd = streaming.calls[0].command
        idx_p = cmd.index("-p")
        assert cmd[idx_p + 1] == "127.0.0.1::80/tcp"

    def test_port_flag_host_port_only(self):
        transport = RecordingTransport()
        streaming = RecordingStreamingTransport()
        mgr = _container_mgr(transport, DockerContainerParser(), _CAPS, streaming=streaming)
        config = RunConfig(
            image="alpine",
            ports=[PortMapping(container_port=80, host_port=8080, host_ip=None)],
        )
        mgr.run(config)
        cmd = streaming.calls[0].command
        idx_p = cmd.index("-p")
        assert cmd[idx_p + 1] == "8080:80/tcp"

    def test_port_flag_neither(self):
        transport = RecordingTransport()
        streaming = RecordingStreamingTransport()
        mgr = _container_mgr(transport, DockerContainerParser(), _CAPS, streaming=streaming)
        config = RunConfig(
            image="alpine",
            ports=[PortMapping(container_port=80, host_ip=None)],
        )
        mgr.run(config)
        cmd = streaming.calls[0].command
        idx_p = cmd.index("-p")
        assert cmd[idx_p + 1] == "80"


# ─── A2: parse_json_item scalar guard ───


class TestA02ParseJsonItemScalarGuard:
    def test_boolean_raises(self):
        with pytest.raises(ParsingError):
            parse_json_item("true")

    def test_integer_raises(self):
        with pytest.raises(ParsingError):
            parse_json_item("42")

    def test_null_raises(self):
        with pytest.raises(ParsingError):
            parse_json_item("null")


# ─── T1: PTY output_stream regression test (R1) ───


class TestT01PtyOutputStream:
    def test_execute_pty_with_output_stream(self):
        from oci_runtime.adapters.transport.pty import CliPtyTransport
        from oci_runtime.adapters.binary import CliBinaryResolver

        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        buf = io.BytesIO()
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty.ProcessPipeReader"
                        ) as mock_reader:
                            mock_reader.from_fds.return_value.read.return_value = (
                                [b"output"],
                                [b""],
                            )
                            def _mock_read(
                                on_primary=None, on_secondary=None, cancel_token=None
                            ):
                                if on_primary:
                                    on_primary(b"output")
                                return ([b"output"], [b""])

                            mock_reader.from_fds.return_value.read.side_effect = (
                                _mock_read
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/true"], output_stream=buf
                            )
        assert result.stdout == b"output"
        assert result.returncode == 0
        assert buf.getvalue() == b"output"


# ─── T2: Transport binary_resolver regression test (R2) ───


class TestT02TransportBinaryResolver:
    def test_cli_transport_execute_with_binary_resolver(self):
        from oci_runtime.adapters.transport.cli import CliTransport
        from oci_runtime.adapters.binary import CliBinaryResolver

        t = CliTransport("docker", binary_resolver=CliBinaryResolver())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout.fileno.return_value = 3
                proc.stderr.fileno.return_value = 4
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch(
                    "oci_runtime.adapters.transport.cli.ProcessPipeReader"
                ) as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = (
                        [b"ok"],
                        [b""],
                    )
                    result = t.execute(["docker", "version"])
        assert isinstance(result, RawExecResult)
        assert result.returncode == 0

    def test_cli_streaming_transport_stream_with_binary_resolver(self):
        from oci_runtime.adapters.transport.streaming import CliStreamingTransport
        from oci_runtime.adapters.binary import CliBinaryResolver

        s = CliStreamingTransport("docker", binary_resolver=CliBinaryResolver())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout = MagicMock()
                proc.stderr = MagicMock()
                proc.stdin = None
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch(
                    "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
                ) as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = (
                        [b"ok"],
                        [b""],
                    )
                    result = s.stream(["docker", "ps"])
        assert isinstance(result, RawExecResult)
        assert result.returncode == 0


# ─── T3: exec_container error propagation regression test (R3) ───


class TestT03ExecContainerErrorPropagation:
    def test_exec_container_propagates_non_not_found_error(self):
        transport = RecordingTransport(
            responses={
                ("docker", "exec", "ctr1", "badcmd"): RawExecResult(
                    returncode=1, stdout=b"", stderr=b"permission denied"
                )
            }
        )
        streaming = RecordingStreamingTransport()
        from oci_runtime.adapters.parser.docker import DockerContainerParser

        mgr = _container_mgr(transport, DockerContainerParser(), _CAPS, streaming=streaming)
        with pytest.raises(ContainerRuntimeError):
            mgr.exec_container("ctr1", ["badcmd"])

    def test_exec_container_suppresses_not_found(self):
        transport = RecordingTransport(
            responses={
                ("docker", "exec", "ctr1", "ls"): RawExecResult(
                    returncode=1, stdout=b"", stderr=b"No such container: c1"
                )
            }
        )
        streaming = RecordingStreamingTransport()
        from oci_runtime.adapters.parser.docker import DockerContainerParser

        mgr = _container_mgr(transport, DockerContainerParser(), _CAPS, streaming=streaming)
        result = mgr.exec_container("ctr1", ["ls"])
        assert result.returncode == 1
