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
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ImageNotFoundError,
    NetworkNotFoundError,
    VolumeNotFoundError,
)
from oci_runtime.domain.types import BuildContext, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.domain.types import ExecResult
from tests.helpers.mock_transport import RecordingTransport, RecordingStreamingTransport, FakeTtyDetector


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
    def test_container_inspect_empty_json_raises_parsing_error(self, transport, streaming, caps):
        transport._responses = {"docker container inspect --format json ctr1": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        with pytest.raises(ParsingError):
            mgr.inspect("ctr1")

    def test_image_inspect_empty_json_raises_parsing_error(self, transport, caps):
        transport._responses = {"docker image inspect --format json alpine": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        with pytest.raises(ParsingError):
            mgr.inspect("alpine")

    def test_volume_inspect_empty_json_raises_parsing_error(self, transport, caps):
        transport._responses = {"docker volume inspect --format json myvol": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliVolumeManager(transport, DockerVolumeParser(), caps)
        with pytest.raises(ParsingError):
            mgr.inspect("myvol")

    def test_network_inspect_empty_json_raises_parsing_error(self, transport, caps):
        transport._responses = {"docker network inspect --format json mynet": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliNetworkManager(transport, DockerNetworkParser(), caps)
        with pytest.raises(ParsingError):
            mgr.inspect("mynet")


class TestEmptyList:
    def test_list_containers_empty(self, transport, streaming, caps):
        transport._responses = {"docker container list": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        with pytest.raises(ParsingError, match="Empty response"):
            mgr.list()

    def test_list_images_empty(self, transport, caps):
        transport._responses = {"docker image list": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        with pytest.raises(ParsingError, match="Empty response"):
            mgr.list()

    def test_list_volumes_empty(self, transport, caps):
        transport._responses = {"docker volume list": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliVolumeManager(transport, DockerVolumeParser(), caps)
        with pytest.raises(ParsingError, match="Empty response"):
            mgr.list()

    def test_list_networks_empty(self, transport, caps):
        transport._responses = {"docker network list": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliNetworkManager(transport, DockerNetworkParser(), caps)
        with pytest.raises(ParsingError, match="Empty response"):
            mgr.list()


class TestEmptyOutput:
    def test_logs_empty(self, transport, streaming, caps):
        transport._responses = {"docker logs ctr1": ExecResult(returncode=0, stdout=b"", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        assert "".join(mgr.logs("ctr1")) == ""

    def test_exec_empty_output(self, transport, streaming, caps):
        transport._responses = {"docker exec ctr1 ls": ExecResult(returncode=0, stdout=b"", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        result = mgr.exec_container("ctr1", ["ls"])
        assert result.returncode == 0
        assert result.stdout == ""

    def test_run_empty_stdout(self, transport, streaming, caps):
        streaming._responses = {"docker run -d alpine": ExecResult(returncode=0, stdout=b"", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        config = RunConfig(image="alpine")
        result = mgr.run(config)
        assert result == ""

    def test_build_empty_output(self, transport, caps):
        transport._responses = {"docker build -t myimg -": ExecResult(returncode=0, stdout=b"", stderr=b"")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        ctx = BuildContext(build_file_content="FROM alpine")
        result = mgr.build(ctx, "myimg", timeout=30)
        assert result == "sha256:"

    def test_pull_empty_stdout(self, transport, caps):
        transport._responses = {"docker pull alpine": ExecResult(returncode=0, stdout=b"", stderr=b"")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        result = mgr.pull("alpine", timeout=30)
        assert result == ""


class TestEmptyExists:
    def test_container_exists_false_on_empty_inspect(self, transport, streaming, caps):
        transport._responses = {"docker container inspect --format json nonexistent": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        assert mgr.exists("nonexistent") is False

    def test_image_exists_false_on_empty_inspect(self, transport, caps):
        transport._responses = {"docker image inspect --format json nonexistent": ExecResult(returncode=0, stdout=b"[]", stderr=b"")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        assert mgr.exists("nonexistent") is False
