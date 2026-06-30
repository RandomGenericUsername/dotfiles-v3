import pytest

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
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    NetworkNotFoundError,
    NetworkRuntimeError,
    VolumeNotFoundError,
    VolumeRuntimeError,
)
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.types import BuildContext
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.domain.types import RawExecResult
from oci_runtime.adapters._cancellation import ThreadCancellationToken
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
        from tests.helpers.mock_transport import FakeTtyDetector

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


class TestMalformedInspect:
    def test_inspect_malformed_json_raises_parsing_error(
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
            ): RawExecResult(returncode=0, stdout=b"not json", stderr=b"")
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        with pytest.raises(ParsingError, match="Invalid JSON"):
            mgr.inspect("ctr1")

    def test_inspect_malformed_json_image(self, transport, caps):
        transport._responses = {
            ("docker", "image", "inspect", "--format", "json", "alpine"): RawExecResult(
                returncode=0, stdout=b"not json", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        with pytest.raises(ParsingError, match="Invalid JSON"):
            mgr.inspect("alpine")

    def test_inspect_malformed_json_volume(self, transport, caps):
        transport._responses = {
            ("docker", "volume", "inspect", "--format", "json", "myvol"): RawExecResult(
                returncode=0, stdout=b"not json", stderr=b""
            )
        }
        mgr = _volume_mgr(transport, DockerVolumeParser(), caps)
        with pytest.raises(ParsingError, match="Invalid JSON"):
            mgr.inspect("myvol")

    def test_inspect_malformed_json_network(self, transport, caps):
        transport._responses = {
            (
                "docker",
                "network",
                "inspect",
                "--format",
                "json",
                "mynet",
            ): RawExecResult(returncode=0, stdout=b"not json", stderr=b"")
        }
        mgr = _network_mgr(transport, DockerNetworkParser(), caps)
        with pytest.raises(ParsingError, match="Invalid JSON"):
            mgr.inspect("mynet")

    def test_inspect_truncated_json_container(self, transport, streaming, caps):
        transport._responses = {
            (
                "docker",
                "container",
                "inspect",
                "--format",
                "json",
                "ctr1",
            ): RawExecResult(returncode=0, stdout=b'{"Id": "abc', stderr=b"")
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        with pytest.raises(ParsingError):
            mgr.inspect("ctr1")

    def test_inspect_wrong_structure(self, transport, streaming, caps):
        transport._responses = {
            (
                "docker",
                "container",
                "inspect",
                "--format",
                "json",
                "ctr1",
            ): RawExecResult(returncode=0, stdout=b'{"not": "expected"}', stderr=b"")
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        result = mgr.inspect("ctr1")
        assert result.id == ""


class TestMalformedList:
    def test_list_malformed_json_containers(self, transport, streaming, caps):
        transport._responses = {
            ("docker", "container", "list"): RawExecResult(
                returncode=0, stdout=b"not json", stderr=b""
            )
        }
        mgr = _container_mgr(
            transport, DockerContainerParser(), caps, streaming=streaming
        )
        with pytest.raises(ParsingError, match="Invalid JSON on line"):
            mgr.list()

    def test_list_malformed_json_images(self, transport, caps):
        transport._responses = {
            ("docker", "image", "list"): RawExecResult(
                returncode=0, stdout=b"not json", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        with pytest.raises(ParsingError, match="Invalid JSON on line"):
            mgr.list()

    def test_list_malformed_json_volumes(self, transport, caps):
        transport._responses = {
            ("docker", "volume", "list"): RawExecResult(
                returncode=0, stdout=b"not json", stderr=b""
            )
        }
        mgr = _volume_mgr(transport, DockerVolumeParser(), caps)
        with pytest.raises(ParsingError, match="Invalid JSON on line"):
            mgr.list()

    def test_list_malformed_json_networks(self, transport, caps):
        transport._responses = {
            ("docker", "network", "list"): RawExecResult(
                returncode=0, stdout=b"not json", stderr=b""
            )
        }
        mgr = _network_mgr(transport, DockerNetworkParser(), caps)
        with pytest.raises(ParsingError, match="Invalid JSON on line"):
            mgr.list()


class TestMalformedBuildOutput:
    def test_build_output_empty(self, transport, caps):
        caps = RuntimeCapabilities(default_build_flags=("--quiet",))
        transport._responses = {
            ("docker", "build", "-t", "myimg", "--quiet", "-"): RawExecResult(
                returncode=0, stdout=b"", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        ctx = BuildContext(build_file_content="FROM alpine")
        with pytest.raises(ImageError):
            mgr.build(ctx, "myimg", timeout=30)

    def test_build_output_whitespace_only(self, transport, caps):
        caps = RuntimeCapabilities(default_build_flags=("--quiet",))
        transport._responses = {
            ("docker", "build", "-t", "myimg", "--quiet", "-"): RawExecResult(
                returncode=0, stdout=b"  \n  ", stderr=b""
            )
        }
        mgr = _image_mgr(transport, DockerImageParser(), caps)
        ctx = BuildContext(build_file_content="FROM alpine")
        with pytest.raises(ImageError):
            mgr.build(ctx, "myimg", timeout=30)
