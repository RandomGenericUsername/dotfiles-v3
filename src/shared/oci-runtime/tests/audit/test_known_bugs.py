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
import json
from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.domain.prune_parsing import (
    parse_prune_result as domain_parse_prune_result,
)
from oci_runtime.domain.size_parsing import parse_size_to_bytes
from oci_runtime.adapters.parser.docker import DockerContainerParser
from oci_runtime.domain.json_parsing import parse_json_item
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
    ContainerInfo,
    ImageInfo,
    NetworkInfo,
    PortMapping,
    PruneResult,
    RawExecResult,
    RunConfig,
    VolumeInfo,
)
from oci_runtime.domain.enums import ContainerState
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.domain.exceptions import (
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    ParsingError,
)
from oci_runtime.domain.result_checking import check_cli_result
from tests.helpers.factory_helpers import (
    image_mgr as _image_mgr,
    container_mgr as _container_mgr,
    volume_mgr as _volume_mgr,
    network_mgr as _network_mgr,
)
from tests.helpers.mock_transport import (
    RecordingStreamingTransport,
    RecordingTransport,
)

# ─── Helpers ───

_CAPS = RuntimeCapabilities(
    supports_log_drivers=True,
    tar_entry_name="Dockerfile",
    default_build_flags=("--quiet",),
)


class _NoOpContainerParser(ContainerParser):
    def parse_inspect(self, raw):
        return ContainerInfo(
            id="",
            name="",
            image="",
            state=ContainerState.CREATED,
            status="",
        )

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
        return ImageInfo(id="")

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
        return VolumeInfo(name="", driver="")

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
        return NetworkInfo(id="", name="", driver="", scope="")

    def parse_list(self, raw):
        return []

    def parse_prune(self, raw):
        return PruneResult()

    def is_not_found_error(self, stderr):
        return False

    def is_auth_error(self, stderr):
        return False


# ─── B1: prune capital D (Docker's capitalized Deleted:) ───


class TestB01PruneCapitalD:
    def test_capitalized_deleted_counted(self):
        result = domain_parse_prune_result(
            "Deleted: sha256:abc123def456abc123def456\n"
            "Deleted: sha256:def456abc123def456abc123\n"
        )
        assert result.deleted == 2

    def test_lowercase_deleted_counted(self):
        result = domain_parse_prune_result(
            "deleted: sha256:abc123def456abc123def456\n"
            "deleted: sha256:def456abc123def456abc123\n"
        )
        assert result.deleted == 2


# ─── B2: auth_error context (command/exit_code/stderr) ───


class TestB02AuthErrorContext:
    def test_auth_error_has_context(self):
        try:
            check_cli_result(
                RawExecResult(1, b"", b"pull access denied for img"),
                cmd=["docker", "pull", "img"],
                entity="img",
                not_found_error=ImageNotFoundError,
                generic_error=ImageRuntimeError,
                auth_error=ImagePullAccessDeniedError,
                is_auth=lambda s: True,
                is_not_found=lambda s: False,
            )
        except ImagePullAccessDeniedError as e:
            assert e.command == ["docker", "pull", "img"]
            assert e.exit_code == 1
            assert e.stderr == "pull access denied for img"
        else:
            pytest.fail("Expected ImagePullAccessDeniedError")


# ─── PortMapping validation ───


class TestPortMappingValidation:
    def test_valid_mapping(self):
        PortMapping(container_port=80, host_ip=None)

    def test_container_port_zero_rejected(self):
        with pytest.raises(ValueError):
            PortMapping(container_port=0, host_ip=None)

    def test_container_port_negative_rejected(self):
        with pytest.raises(ValueError):
            PortMapping(container_port=-1, host_ip=None)

    def test_container_port_over_65535_rejected(self):
        with pytest.raises(ValueError):
            PortMapping(container_port=65536, host_ip=None)

    def test_host_port_zero_rejected(self):
        with pytest.raises(ValueError):
            PortMapping(container_port=80, host_port=0, host_ip=None)

    def test_host_port_over_65535_rejected(self):
        with pytest.raises(ValueError):
            PortMapping(container_port=80, host_port=65536, host_ip=None)

    def test_host_port_none_accepted(self):
        PortMapping(container_port=80, host_port=None, host_ip=None)

    def test_invalid_protocol_rejected(self):
        with pytest.raises(ValueError):
            PortMapping(container_port=80, host_ip=None, protocol="http")

    def test_valid_protocols_accepted(self):
        for proto in ("tcp", "udp", "sctp"):
            PortMapping(container_port=80, host_ip=None, protocol=proto)


# ─── B4: _freeze_mapping alias (source dict mutation should not leak) ───


class TestB04FreezeMappingNoAlias:
    def test_source_dict_mutation_does_not_leak(self):
        from oci_runtime.domain.types import ImageInfo

        labels = {"key": "original"}
        info = ImageInfo(id="abc", labels=labels)
        labels["key"] = "mutated"
        assert info.labels["key"] == "original"


# ─── B3: memory limit two-letter units (2GB, 512MB, 1.5gb) ───


class TestB03MemoryLimitTwoLetterUnits:
    def test_two_gb_accepted(self):
        RunConfig(image="alpine", memory_limit="2GB")

    def test_512_mb_accepted(self):
        RunConfig(image="alpine", memory_limit="512MB")

    def test_one_dot_five_gb_lowercase_accepted(self):
        RunConfig(image="alpine", memory_limit="1.5gb")

    def test_single_letter_still_accepted(self):
        RunConfig(image="alpine", memory_limit="512m")
        RunConfig(image="alpine", memory_limit="2g")

    def test_abc_rejected(self):
        with pytest.raises(ValueError):
            RunConfig(image="alpine", memory_limit="abc")

    def test_unitless_bytes_accepted(self):
        RunConfig(image="alpine", memory_limit="1024")
        RunConfig(image="alpine", memory_limit="4096")


# ─── M7: _read_fd narrows OSError to EIO ───


class TestM07ReadFdNonEioPropagates:
    def test_non_eio_oserror_propagates(self):
        from oci_runtime.adapters.transport.pipe_reader import ProcessPipeReader

        reader = ProcessPipeReader(99, 100)
        with pytest.raises(OSError):
            reader._read_fd(9999)

    def test_eio_returns_empty(self):
        import errno
        import os
        from oci_runtime.adapters.transport.pipe_reader import ProcessPipeReader

        reader = ProcessPipeReader(99, 100)
        with patch.object(
            os, "read", side_effect=OSError(errno.EIO, "Input/output error")
        ):
            result = reader._read_fd(99)
            assert result == b""


# ─── M6: from_process validates both streams ───


class TestM06FromProcessStderrNone:
    def test_stderr_none_raises_type_error(self):
        from oci_runtime.adapters.transport.pipe_reader import ProcessPipeReader

        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stdout.fileno.return_value = 3
        proc.stderr = None
        with pytest.raises(TypeError):
            ProcessPipeReader.from_process(proc)

    def test_stderr_no_fileno_raises_type_error(self):
        from oci_runtime.adapters.transport.pipe_reader import ProcessPipeReader

        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stdout.fileno.return_value = 3
        proc.stderr = MagicMock()
        del proc.stderr.fileno
        with pytest.raises(TypeError):
            ProcessPipeReader.from_process(proc)


# ─── H5: PipeReader substitutable (no kwargs shim) ───


class TestH05PipeReaderSubstitutable:
    def test_no_shim_test_double_works(self):
        from oci_runtime.ports.pipe_reader import PipeReader

        class ShimlessReader(PipeReader):
            def read(self, on_stdout=None, on_stderr=None, cancel_token=None):
                if on_stdout:
                    on_stdout(b"out")
                if on_stderr:
                    on_stderr(b"err")
                return ([b"out"], [b"err"])

        out_calls = []
        err_calls = []
        reader = ShimlessReader()
        reader.read(
            on_stdout=lambda d: out_calls.append(d),
            on_stderr=lambda d: err_calls.append(d),
        )
        assert out_calls == [b"out"]
        assert err_calls == [b"err"]


# ─── B5: Docker list Ports as string ───


class TestB05DockerListPortsAsString:
    def test_ports_as_string_parsed(self):
        parser = DockerContainerParser()
        raw = json.dumps(
            [
                {
                    "Id": "abc",
                    "Names": ["/ctr1"],
                    "Image": "nginx",
                    "State": "running",
                    "Status": "Up",
                    "Created": "2024-01-01",
                    "Ports": "0.0.0.0:8080->80/tcp, 0.0.0.0:443->443/tcp",
                    "Labels": {},
                }
            ]
        )
        result = parser.parse_list(raw)
        assert len(result) == 1
        assert len(result[0].ports) == 2
        assert result[0].ports[0].container_port == 80
        assert result[0].ports[0].host_port == 8080
        assert result[0].ports[0].protocol == "tcp"
        assert result[0].ports[1].container_port == 443

    def test_ports_as_string_bare_proto(self):
        parser = DockerContainerParser()
        raw = json.dumps(
            [
                {
                    "Id": "def",
                    "Names": ["/ctr2"],
                    "Image": "alpine",
                    "State": "running",
                    "Status": "Up",
                    "Created": "2024-01-01",
                    "Ports": "80/tcp",
                    "Labels": {},
                }
            ]
        )
        result = parser.parse_list(raw)
        assert len(result[0].ports) == 1
        assert result[0].ports[0].container_port == 80
        assert result[0].ports[0].host_port is None


# ─── M4: Podman "no such object" pattern parity ───


class TestM04PodmanNotFoundParity:
    def test_no_such_object_detected(self):
        from oci_runtime.adapters.parser.podman import PodmanContainerParser

        parser = PodmanContainerParser()
        assert parser.is_not_found_error("Error: no such object")


# ─── H2: Podman HostIp-only binding preserved ───


class TestH02PodmanHostIpOnlyBinding:
    def test_host_ip_only_bound(self):
        from oci_runtime.adapters.parser.podman import PodmanContainerParser

        parser = PodmanContainerParser()
        raw = json.dumps(
            {
                "Id": "abc",
                "Name": "/ctr1",
                "Config": {"Image": "nginx"},
                "State": {"Status": "running"},
                "NetworkSettings": {
                    "Ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]}
                },
            }
        )
        info = parser.parse_inspect(raw)
        assert len(info.ports) == 1
        assert info.ports[0].container_port == 80
        assert info.ports[0].host_port is None
        assert info.ports[0].host_ip == "127.0.0.1"


# ─── H4: manager output_stream guard ───


class TestH04ManagerNoneOutputStream:
    def test_none_output_stream_raises(self):
        t = RecordingTransport("docker")
        st = RecordingStreamingTransport("docker")
        from oci_runtime.domain.exceptions import OciError

        mgr = _container_mgr(t, _NoOpContainerParser(), _CAPS, streaming=st)
        config = RunConfig(image="alpine", tty=True, detach=False)
        with pytest.raises(OciError, match="output_stream required"):
            mgr.run(config)


# ─── B6: PtyTransport output_stream required ───


class TestB06PtyPortOutputStreamRequired:
    def test_output_stream_has_no_default(self):
        import inspect
        from oci_runtime.ports.pty_transport import PtyTransport

        sig = inspect.signature(PtyTransport.execute_pty)
        param = sig.parameters["output_stream"]
        assert param.default is inspect.Parameter.empty, (
            f"output_stream should be required, but has default={param.default!r}"
        )


# ─── H1: matches_any_pattern case insensitivity ───


class TestH01MatchesAnyPatternCase:
    def test_uppercase_pattern_matches_lowercase_text(self):
        from oci_runtime.domain.error_matching import matches_any_pattern

        assert matches_any_pattern("no such container", ("No Such Container",))

    def test_lowercase_pattern_matches_uppercase_text(self):
        from oci_runtime.domain.error_matching import matches_any_pattern

        assert matches_any_pattern("NO SUCH CONTAINER", ("no such container",))

    def test_non_match_returns_false(self):
        from oci_runtime.domain.error_matching import matches_any_pattern

        assert not matches_any_pattern("everything is fine", ("no such container",))


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
        t = RecordingTransport("docker")
        mgr = _container_mgr(t, _NoOpContainerParser(), _CAPS, streaming=MagicMock())
        with (
            patch(
                "oci_runtime.adapters.managers.container._SubprocessRunner"
            ) as MockRunner,
            patch(
                "oci_runtime.adapters.managers.container._AsyncStreamReader"
            ) as MockReader,
        ):
            mock_process = MagicMock()
            mock_process.stdout.fileno.return_value = 3
            mock_process.stderr.fileno.return_value = 5
            mock_runner = MockRunner.return_value
            mock_runner.process = mock_process

            mock_reader = MockReader.return_value

            def _mock_read(on_stdout=None, on_stderr=None, **kwargs):
                if on_stdout:
                    on_stdout(b"stdout-line\n")
                if on_stderr:
                    on_stderr(b"stderr-line\n")
                return ([b"stdout-line\n"], [b"stderr-line\n"])

            mock_reader.read.side_effect = _mock_read

            chunks = list(mgr.logs("ctr1", follow=True))
            combined = "".join(chunks)
            assert "stderr-line" in combined, (
                f"stderr was dropped from logs: {combined!r}"
            )


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
                        "oci_runtime.adapters.transport.streaming._AsyncStreamReader"
                    ) as mock_reader:
                        mock_reader.return_value.read.return_value = (
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
        mgr = _container_mgr(
            transport, DockerContainerParser(), _CAPS, streaming=streaming
        )
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
        mgr = _container_mgr(
            transport, DockerContainerParser(), _CAPS, streaming=streaming
        )
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
        mgr = _container_mgr(
            transport, DockerContainerParser(), _CAPS, streaming=streaming
        )
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
        mgr = _container_mgr(
            transport, DockerContainerParser(), _CAPS, streaming=streaming
        )
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
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [b"output"],
                                [b""],
                            )

                            def _mock_read(
                                on_stdout=None,
                                on_stderr=None,
                                cancel_ctx=None,
                                timeout=None,
                            ):
                                if on_stdout:
                                    on_stdout(b"output")
                                return ([b"output"], [b""])

                            mock_reader.return_value.read.side_effect = _mock_read
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
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as mock_reader:
                    mock_reader.return_value.read.return_value = (
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
                    "oci_runtime.adapters.transport.streaming._AsyncStreamReader"
                ) as mock_reader:
                    mock_reader.return_value.read.return_value = (
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

        mgr = _container_mgr(
            transport, DockerContainerParser(), _CAPS, streaming=streaming
        )
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

        mgr = _container_mgr(
            transport, DockerContainerParser(), _CAPS, streaming=streaming
        )
        result = mgr.exec_container("ctr1", ["ls"])
        assert result.returncode == 1
