from unittest.mock import patch

import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
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
from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser,
    PodmanImageParser,
    PodmanNetworkParser,
    PodmanVolumeParser,
)
from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    NetworkNotFoundError,
    RuntimeNotAvailableError,
    VolumeNotFoundError,
)
from oci_runtime.domain.types import RunConfig
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.factory import RuntimeFactory
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.domain.types import ExecResult
from tests.helpers.mock_transport import RecordingTransport


@pytest.fixture
def caps():
    return RuntimeCapabilities()


@pytest.fixture
def transport():
    return RecordingTransport("docker")


class TestTransportErrors:
    def test_missing_binary_raises_runtime_not_available(self):
        with patch("shutil.which", return_value=None):
            t = CliTransport("nonexistent-runtime")
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent-runtime"):
                t.execute(["nonexistent-runtime", "ps"])

    def test_get_runtime_binary_missing_raises(self):
        with patch("shutil.which", return_value=None):
            t = CliTransport("nonexistent-runtime")
            with pytest.raises(RuntimeNotAvailableError):
                t.get_runtime_binary()


class TestManagerErrorPropagation:
    def test_image_not_found_from_stderr(self, transport, caps):
        transport._responses = {"docker image inspect --format json alpine": ExecResult(returncode=1, stdout=b"", stderr=b"No such image: alpine")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        with pytest.raises(ImageNotFoundError, match="alpine"):
            mgr.inspect("alpine")

    def test_container_not_found_from_stderr(self, transport, caps):
        transport._responses = {"docker container inspect --format json ctr1": ExecResult(returncode=1, stdout=b"", stderr=b"No such container: ctr1")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps)
        with pytest.raises(ContainerNotFoundError, match="ctr1"):
            mgr.inspect("ctr1")

    def test_volume_not_found_from_stderr(self, transport, caps):
        transport._responses = {"docker volume inspect --format json myvol": ExecResult(returncode=1, stdout=b"", stderr=b"No such volume: myvol")}
        mgr = CliVolumeManager(transport, DockerVolumeParser(), caps)
        with pytest.raises(VolumeNotFoundError, match="myvol"):
            mgr.inspect("myvol")

    def test_network_not_found_from_stderr(self, transport, caps):
        transport._responses = {"docker network inspect --format json mynet": ExecResult(returncode=1, stdout=b"", stderr=b"No such network: mynet")}
        mgr = CliNetworkManager(transport, DockerNetworkParser(), caps)
        with pytest.raises(NetworkNotFoundError, match="mynet"):
            mgr.inspect("mynet")

    def test_generic_error_raises_container_runtime_error(self, transport, caps):
        transport._responses = {"docker run -d alpine": ExecResult(returncode=125, stdout=b"", stderr=b"Error response from daemon: something went wrong")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps)
        config = RunConfig(image="alpine")
        with pytest.raises(ContainerRuntimeError) as exc_info:
            mgr.run(config)
        assert exc_info.value.exit_code == 125
        assert "something went wrong" in exc_info.value.stderr

    def test_non_zero_without_stderr(self, transport, caps):
        transport._responses = {"docker container inspect --format json ctr1": ExecResult(returncode=1, stdout=b"", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps)
        with pytest.raises(ContainerRuntimeError):
            mgr.inspect("ctr1")

    def test_not_found_error_for_stop(self, transport, caps):
        transport._responses = {"docker stop -t 10 ctr1": ExecResult(returncode=1, stdout=b"", stderr=b"No such container: ctr1")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps)
        with pytest.raises(ContainerNotFoundError, match="ctr1"):
            mgr.stop("ctr1")

    def test_not_found_error_for_remove(self, transport, caps):
        transport._responses = {"docker rm ctr1": ExecResult(returncode=1, stdout=b"", stderr=b"No such container: ctr1")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps)
        with pytest.raises(ContainerNotFoundError, match="ctr1"):
            mgr.remove("ctr1")


class TestParserNotFoundDetection:
    def test_docker_container_not_found_pattern(self):
        p = DockerContainerParser()
        assert p.is_not_found_error("No such container: abc")
        assert not p.is_not_found_error("Error response from daemon")
        assert not p.is_not_found_error("")

    def test_docker_image_not_found_pattern(self):
        p = DockerImageParser()
        assert p.is_not_found_error("No such image: alpine")
        assert p.is_not_found_error("pull access denied")
        assert not p.is_not_found_error("something else")

    def test_docker_volume_not_found_pattern(self):
        p = DockerVolumeParser()
        assert p.is_not_found_error("No such volume: myvol")
        assert not p.is_not_found_error("something else")

    def test_docker_network_not_found_pattern(self):
        p = DockerNetworkParser()
        assert p.is_not_found_error("No such network: mynet")
        assert not p.is_not_found_error("something else")

    def test_podman_container_not_found_pattern(self):
        p = PodmanContainerParser()
        assert p.is_not_found_error("No such container: abc")
        assert not p.is_not_found_error("something else")

    def test_podman_image_not_found_pattern(self):
        p = PodmanImageParser()
        assert p.is_not_found_error("image not found")
        assert not p.is_not_found_error("No such image")

    def test_podman_volume_not_found_pattern(self):
        p = PodmanVolumeParser()
        assert p.is_not_found_error("No such volume: myvol")
        assert not p.is_not_found_error("something else")

    def test_podman_network_not_found_pattern(self):
        p = PodmanNetworkParser()
        assert p.is_not_found_error("No such network: mynet")
        assert not p.is_not_found_error("something else")


class TestFactoryErrorConditions:
    def test_create_unavailable_engine_raises(self):
        bogus = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
        with pytest.raises(RuntimeNotAvailableError):
            RuntimeFactory().create(bogus)

    def test_factory_create_wrong_binary_raises(self):
        with patch("shutil.which", return_value="/usr/bin/which"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stdout = b""
                mock_run.return_value.stderr = b""
                pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="/usr/bin/which")
                with pytest.raises(RuntimeNotAvailableError):
                    RuntimeFactory().create(pref)
