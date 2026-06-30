from unittest.mock import MagicMock

import pytest

from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.parser.docker import DockerContainerParser
from oci_runtime.domain.enums import ContainerState, NetworkMode
from oci_runtime.domain.exceptions import ContainerRuntimeError, ImageNotFoundError
from oci_runtime.domain.types import ContainerInfo, PruneResult, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.adapters._cancellation import ThreadCancellationToken
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.exceptions import ContainerNotFoundError, ContainerRuntimeError
from tests.helpers.mock_transport import (
    FakeTtyDetector,
    MockPtyTransport,
    MockResultChecker,
    MockListExecutor,
    RecordingStreamingTransport,
    RecordingTransport,
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


@pytest.fixture
def transport():
    return RecordingTransport("docker")


@pytest.fixture
def streaming():
    return RecordingStreamingTransport("docker")


@pytest.fixture
def caps():
    return RuntimeCapabilities()


class _MockParser(ContainerParser):
    def parse_inspect(self, raw: str) -> ContainerInfo:
        return ContainerInfo(
            id="abc",
            name="c1",
            image="alpine",
            state=ContainerState.RUNNING,
            status="Up",
        )

    def parse_list(self, raw: str) -> list[ContainerInfo]:
        return [
            ContainerInfo(
                id="abc",
                name="c1",
                image="alpine",
                state=ContainerState.RUNNING,
                status="Up",
            )
        ]

    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()

    def is_not_found_error(self, stderr: str) -> bool:
        return "No such container" in stderr


class TestCliContainerManager:
    def setup_method(self):
        self.transport = MagicMock(spec=Transport)
        self.transport.binary = "docker"
        self.transport.execute.return_value = RawExecResult(
            returncode=0, stdout=b"abc123", stderr=b""
        )
        self.streaming = MagicMock(spec=StreamingTransport)
        self.streaming.stream.return_value = RawExecResult(
            returncode=0, stdout=b"abc123", stderr=b""
        )
        self.parser = _MockParser()
        self.caps = RuntimeCapabilities()
        self.manager = _container_mgr(
            self.transport, self.parser, self.caps, streaming=self.streaming
        )

    def test_run_calls_streaming_stream(self):
        config = RunConfig(image="alpine", command=["echo", "hi"])
        self.manager.run(config)
        self.streaming.stream.assert_called_once()

    def test_run_includes_image_and_command(self):
        config = RunConfig(image="alpine", command=["echo", "hi"])
        self.manager.run(config)
        args = self.streaming.stream.call_args[0][0]
        assert "alpine" in args
        assert "echo" in args
        assert "hi" in args

    def test_run_adds_default_run_flags_from_caps(self):
        caps = RuntimeCapabilities(default_run_flags=("--userns=keep-id",))
        manager = _container_mgr(
            self.transport, self.parser, caps, streaming=self.streaming
        )
        config = RunConfig(image="alpine")
        manager.run(config)
        args = self.streaming.stream.call_args[0][0]
        assert "--userns=keep-id" in args

    def test_check_result_raises_not_found(self):
        with pytest.raises(ImageNotFoundError, match="my-image"):
            self.manager._result_checker.check(
                RawExecResult(returncode=1, stdout=b"", stderr=b"No such container: x"),
                cmd=["docker", "run", "my-image"],
                operation="check",
                entity="my-image",
                not_found_error=ImageNotFoundError,
            )

    def test_list_calls_transport(self):
        self.manager.list()
        self.transport.execute.assert_called_once()

    def test_run_network_bridge_ignores_container_arg(self):
        config = RunConfig(
            image="alpine", network=NetworkMode.BRIDGE, network_container="nginx"
        )
        self.manager.run(config)
        args = self.streaming.stream.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "bridge"

    def test_run_network_host_adds_flag(self):
        config = RunConfig(image="alpine", network=NetworkMode.HOST)
        self.manager.run(config)
        args = self.streaming.stream.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "host"

    def test_run_network_container_requires_arg(self):
        with pytest.raises(
            ValueError, match="network=CONTAINER requires network_container"
        ):
            RunConfig(image="alpine", network=NetworkMode.CONTAINER)

    def test_run_network_container_adds_flag(self):
        config = RunConfig(
            image="alpine", network=NetworkMode.CONTAINER, network_container="nginx"
        )
        self.manager.run(config)
        args = self.streaming.stream.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "container:nginx"

    def test_run_network_none_adds_flag(self):
        config = RunConfig(image="alpine", network=NetworkMode.NONE)
        self.manager.run(config)
        args = self.streaming.stream.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "none"

    def test_exec_non_zero_returns_exec_result(self, transport, streaming, caps):
        transport._responses = {
            ("docker", "exec", "ctr1", "false"): RawExecResult(
                returncode=1, stdout=b"", stderr=b""
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        result = mgr.exec_container("ctr1", ["false"])
        assert result.returncode == 1

    def test_exec_not_found_raises_container_not_found(
        self, transport, streaming, caps
    ):
        from oci_runtime.domain.exceptions import ContainerNotFoundError

        transport._responses = {
            ("docker", "exec", "ctr1", "ls"): RawExecResult(
                returncode=1, stdout=b"", stderr=b"No such container: c1"
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        with pytest.raises(ContainerNotFoundError):
            mgr.exec_container("ctr1", ["ls"])
