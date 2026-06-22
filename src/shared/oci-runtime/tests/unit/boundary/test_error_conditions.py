from unittest.mock import patch

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
    ImagePullAccessDeniedError,
    NetworkNotFoundError,
    RuntimeNotAvailableError,
    VolumeNotFoundError,
)
from oci_runtime.domain.types import RunConfig
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RawExecResult
from oci_runtime.adapters._cancellation import ThreadCancellationToken
from tests.helpers.mock_transport import FakeTtyDetector, MockPtyTransport, RecordingStreamingTransport, RecordingTransport


@pytest.fixture
def caps():
    return RuntimeCapabilities()


@pytest.fixture
def transport():
    return RecordingTransport("docker")


@pytest.fixture
def streaming():
    return RecordingStreamingTransport("docker")


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
        transport._responses = {("docker", "image", "inspect", "--format", "json", "alpine"): RawExecResult(returncode=1, stdout=b"", stderr=b"No such image: alpine")}
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        with pytest.raises(ImageNotFoundError) as exc:
            mgr.inspect("alpine")
        assert "alpine" in exc.value.image_name

    def test_container_not_found_from_stderr(self, transport, streaming, caps):
        transport._responses = {("docker", "container", "inspect", "--format", "json", "ctr1"): RawExecResult(returncode=1, stdout=b"", stderr=b"No such container: ctr1")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector(),
            pty_transport=MockPtyTransport(), cancellation_factory=lambda: ThreadCancellationToken())
        with pytest.raises(ContainerNotFoundError) as exc:
            mgr.inspect("ctr1")
        assert "ctr1" in exc.value.container_id

    def test_volume_not_found_from_stderr(self, transport, caps):
        transport._responses = {("docker", "volume", "inspect", "--format", "json", "myvol"): RawExecResult(returncode=1, stdout=b"", stderr=b"No such volume: myvol")}
        mgr = CliVolumeManager(transport, DockerVolumeParser(), caps)
        with pytest.raises(VolumeNotFoundError) as exc:
            mgr.inspect("myvol")
        assert "myvol" in exc.value.volume_name

    def test_network_not_found_from_stderr(self, transport, caps):
        transport._responses = {("docker", "network", "inspect", "--format", "json", "mynet"): RawExecResult(returncode=1, stdout=b"", stderr=b"No such network: mynet")}
        mgr = CliNetworkManager(transport, DockerNetworkParser(), caps)
        with pytest.raises(NetworkNotFoundError) as exc:
            mgr.inspect("mynet")
        assert "mynet" in exc.value.network_name

    def test_generic_error_raises_container_runtime_error(self, transport, streaming, caps):
        transport._responses = {("docker", "run", "-d", "alpine"): RawExecResult(returncode=125, stdout=b"", stderr=b"Error response from daemon: something went wrong")}
        streaming._responses = {("docker", "run", "-d", "alpine"): RawExecResult(returncode=125, stdout=b"", stderr=b"Error response from daemon: something went wrong")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector(),
            pty_transport=MockPtyTransport(), cancellation_factory=lambda: ThreadCancellationToken())
        config = RunConfig(image="alpine")
        with pytest.raises(ContainerRuntimeError) as exc_info:
            mgr.run(config)
        assert exc_info.value.exit_code == 125
        assert "something went wrong" in exc_info.value.stderr

    def test_non_zero_without_stderr(self, transport, streaming, caps):
        transport._responses = {("docker", "container", "inspect", "--format", "json", "ctr1"): RawExecResult(returncode=1, stdout=b"", stderr=b"")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector(),
            pty_transport=MockPtyTransport(), cancellation_factory=lambda: ThreadCancellationToken())
        with pytest.raises(ContainerRuntimeError) as exc:
            mgr.inspect("ctr1")
        assert exc.value.exit_code == 1

    def test_not_found_error_for_stop(self, transport, streaming, caps):
        transport._responses = {("docker", "stop", "-t", "10", "ctr1"): RawExecResult(returncode=1, stdout=b"", stderr=b"No such container: ctr1")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector(),
            pty_transport=MockPtyTransport(), cancellation_factory=lambda: ThreadCancellationToken())
        with pytest.raises(ContainerNotFoundError) as exc:
            mgr.stop("ctr1")
        assert "ctr1" in exc.value.container_id

    def test_not_found_error_for_remove(self, transport, streaming, caps):
        transport._responses = {("docker", "rm", "ctr1"): RawExecResult(returncode=1, stdout=b"", stderr=b"No such container: ctr1")}
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector(),
            pty_transport=MockPtyTransport(), cancellation_factory=lambda: ThreadCancellationToken())
        with pytest.raises(ContainerNotFoundError) as exc:
            mgr.remove("ctr1")
        assert "ctr1" in exc.value.container_id

    def test_pull_unparseable_raises_image_error(self, transport, caps):
        from oci_runtime.domain.exceptions import ImageError
        transport._responses = {("docker", "pull", "alpine"): RawExecResult(returncode=0, stdout=b"random text", stderr=b"")}
        from oci_runtime.adapters.parser.docker import DockerImageParser
        from oci_runtime.adapters.managers.image import CliImageManager
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        with pytest.raises(ImageError):
            mgr.pull("alpine", timeout=30)


class TestParserNotFoundDetection:
    def test_docker_container_not_found_pattern(self):
        p = DockerContainerParser()
        assert p.is_not_found_error("No such container: abc")
        assert not p.is_not_found_error("Error response from daemon")
        assert not p.is_not_found_error("")

    def test_docker_image_not_found_pattern(self):
        p = DockerImageParser()
        assert p.is_not_found_error("No such image: alpine")
        assert not p.is_not_found_error("pull access denied")
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
    def test_create_does_not_probe_unavailable(self):
        bogus = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
        engine = RuntimeFactory().create(bogus)
        assert engine.is_available() is False

    def test_create_engine_with_wrong_binary(self):
        with patch("shutil.which", return_value=None):
            pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
            engine = RuntimeFactory().create(pref)
            assert engine.is_available() is False


class TestImagePullAuthErrors:
    def test_pull_access_denied_raises_image_pull_access_denied_error(self):
        transport = RecordingTransport("docker", {
            ("docker", "pull", "private/image"): RawExecResult(1, b"", b"pull access denied for private/image"),
        })
        mgr = CliImageManager(transport, DockerImageParser(), RuntimeCapabilities())
        with pytest.raises(ImagePullAccessDeniedError) as exc:
            mgr.pull("private/image")
        assert "private/image" in exc.value.image_name

    def test_pull_unauthorized_raises_image_pull_access_denied_error(self):
        transport = RecordingTransport("docker", {
            ("docker", "pull", "private/image"): RawExecResult(1, b"", b"unauthorized: access denied"),
        })
        mgr = CliImageManager(transport, DockerImageParser(), RuntimeCapabilities())
        with pytest.raises(ImagePullAccessDeniedError) as exc:
            mgr.pull("private/image")
        assert "private/image" in exc.value.image_name


class TestTarPathTraversal:
    def test_absolute_path_raises_value_error(self):
        from oci_runtime.adapters._tar import create_build_tar
        with pytest.raises(ValueError, match="Absolute path"):
            create_build_tar("FROM alpine", {"/etc/passwd": b"data"})

    def test_parent_path_raises_value_error(self):
        from oci_runtime.adapters._tar import create_build_tar
        with pytest.raises(ValueError, match="parent reference"):
            create_build_tar("FROM alpine", {"../outside": b"data"})
