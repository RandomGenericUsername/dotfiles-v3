import pytest

from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageError,
    ImageNotFoundError,
    ImageRuntimeError,
    ImagePullAccessDeniedError,
    VolumeNotFoundError,
    VolumeRuntimeError,
    NetworkNotFoundError,
    NetworkRuntimeError,
)
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.types import BuildContext, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.cancellation import ThreadCancellationToken
from tests.helpers.mock_transport import (
    FakeTtyDetector,
    MockPtyTransport,
    RecordingStreamingTransport,
    RecordingTransport,
)


@pytest.fixture
def caps():
    return RuntimeCapabilities()


@pytest.fixture
def transport():
    return RecordingTransport("docker")


@pytest.fixture
def streaming():
    return RecordingStreamingTransport("docker")


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


def _container_mgr(transport, parser, caps, streaming, tty_detector=None):
    if tty_detector is None:
        tty_detector = FakeTtyDetector()
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
        tty_detector=tty_detector,
        pty_transport=MockPtyTransport(),
        cancellation_factory=lambda: ThreadCancellationToken(),
        result_checker=chk,
        list_executor=CliListExecutor(
            transport, caps, chk, parse_list=parser.parse_list
        ),
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


class TestEmptyInspect:
    def test_container_inspect_empty_json_raises_parsing_error(
        self, transport, streaming, caps
    ):
        transport._responses = {
            (
                "docker",
                "container",
                "inspect",
                "--format",
                "json",
                "ctr1",
            ): RawExecResult(returncode=0, stdout=b"[]", stderr=b"")
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        with pytest.raises(ParsingError):
            mgr.inspect("ctr1")

    def test_image_inspect_empty_json_raises_parsing_error(self, transport, caps):
        transport._responses = {
            ("docker", "image", "inspect", "--format", "json", "alpine"): RawExecResult(
                returncode=0, stdout=b"[]", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        with pytest.raises(ParsingError):
            mgr.inspect("alpine")

    def test_volume_inspect_empty_json_raises_parsing_error(self, transport, caps):
        transport._responses = {
            ("docker", "volume", "inspect", "--format", "json", "myvol"): RawExecResult(
                returncode=0, stdout=b"[]", stderr=b""
            )
        }
        mgr = _volume_mgr(transport, DockerVolumeParser(), caps)
        with pytest.raises(ParsingError):
            mgr.inspect("myvol")

    def test_network_inspect_empty_json_raises_parsing_error(self, transport, caps):
        transport._responses = {
            (
                "docker",
                "network",
                "inspect",
                "--format",
                "json",
                "mynet",
            ): RawExecResult(returncode=0, stdout=b"[]", stderr=b"")
        }
        mgr = _network_mgr(transport, DockerNetworkParser(), caps)
        with pytest.raises(ParsingError):
            mgr.inspect("mynet")


class TestEmptyList:
    def test_list_containers_empty(self, transport, streaming, caps):
        transport._responses = {
            ("docker", "container", "list"): RawExecResult(
                returncode=0, stdout=b"[]", stderr=b""
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        result = mgr.list()
        assert result == []

    def test_list_images_empty(self, transport, caps):
        transport._responses = {
            ("docker", "image", "list"): RawExecResult(
                returncode=0, stdout=b"[]", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        result = mgr.list()
        assert result == []

    def test_list_volumes_empty(self, transport, caps):
        transport._responses = {
            ("docker", "volume", "list"): RawExecResult(
                returncode=0, stdout=b"[]", stderr=b""
            )
        }
        mgr = _volume_mgr(transport, DockerVolumeParser(), caps)
        result = mgr.list()
        assert result == []

    def test_list_networks_empty(self, transport, caps):
        transport._responses = {
            ("docker", "network", "list"): RawExecResult(
                returncode=0, stdout=b"[]", stderr=b""
            )
        }
        mgr = _network_mgr(transport, DockerNetworkParser(), caps)
        result = mgr.list()
        assert result == []


class TestEmptyOutput:
    def test_logs_empty(self, transport, streaming, caps):
        transport._responses = {
            ("docker", "logs", "ctr1"): RawExecResult(
                returncode=0, stdout=b"", stderr=b""
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        assert "".join(mgr.logs("ctr1")) == ""

    def test_exec_empty_output(self, transport, streaming, caps):
        transport._responses = {
            ("docker", "exec", "ctr1", "ls"): RawExecResult(
                returncode=0, stdout=b"", stderr=b""
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        result = mgr.exec_container("ctr1", ["ls"])
        assert result.returncode == 0
        assert result.stdout == ""

    def test_run_empty_stdout(self, transport, streaming, caps):
        streaming._responses = {
            ("docker", "run", "-d", "alpine"): RawExecResult(
                returncode=0, stdout=b"", stderr=b""
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        config = RunConfig(image="alpine")
        result = mgr.run(config)
        assert result == ""

    def test_build_empty_output(self, transport, caps):
        transport._responses = {
            ("docker", "build", "-t", "myimg", "-"): RawExecResult(
                returncode=0, stdout=b"", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        ctx = BuildContext(build_file_content="FROM alpine")
        with pytest.raises(ImageError):
            mgr.build(ctx, "myimg", timeout=30)

    def test_build_invalid_hex_raises_image_error_with_cause(self, transport, caps):
        transport._responses = {
            ("docker", "build", "-t", "myimg", "-"): RawExecResult(
                returncode=0, stdout=b"not a hex string", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        ctx = BuildContext(build_file_content="FROM alpine")
        with pytest.raises(ImageRuntimeError) as exc_info:
            mgr.build(ctx, "myimg", timeout=30)
        assert isinstance(exc_info.value.__cause__, ParsingError)

    def test_pull_empty_stdout(self, transport, caps):
        from oci_runtime.domain.exceptions import ImageError, ParsingError

        transport._responses = {
            ("docker", "pull", "alpine"): RawExecResult(
                returncode=0, stdout=b"", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        with pytest.raises(ImageError):
            mgr.pull("alpine", timeout=30)


class TestEmptyExists:
    def test_container_exists_false_on_empty_inspect(self, transport, streaming, caps):
        transport._responses = {
            (
                "docker",
                "container",
                "inspect",
                "--format",
                "json",
                "nonexistent",
            ): RawExecResult(returncode=0, stdout=b"[]", stderr=b"")
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        with pytest.raises(ParsingError):
            mgr.exists("nonexistent")

    def test_image_exists_false_on_empty_inspect(self, transport, caps):
        transport._responses = {
            (
                "docker",
                "image",
                "inspect",
                "--format",
                "json",
                "nonexistent",
            ): RawExecResult(returncode=0, stdout=b"[]", stderr=b"")
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        with pytest.raises(ParsingError):
            mgr.exists("nonexistent")
