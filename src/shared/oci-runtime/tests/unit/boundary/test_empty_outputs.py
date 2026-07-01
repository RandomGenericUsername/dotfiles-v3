import pytest

from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.domain.exceptions import (
    ImageError,
    ImageRuntimeError,
)
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.types import BuildContext, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.domain.types import RawExecResult
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


@pytest.fixture
def caps():
    return RuntimeCapabilities()


@pytest.fixture
def transport():
    return RecordingTransport("docker")


@pytest.fixture
def streaming():
    return RecordingStreamingTransport("docker")


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
        from oci_runtime.domain.exceptions import ImageError

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
