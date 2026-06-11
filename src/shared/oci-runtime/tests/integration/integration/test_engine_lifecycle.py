from unittest.mock import MagicMock

import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.ports.transport import ExecResult
from tests.helpers.mock_transport import RecordingTransport


@pytest.fixture
def caps():
    return RuntimeCapabilities()


@pytest.fixture
def mock_managers():
    return {
        "images": MagicMock(spec=ImageManager),
        "containers": MagicMock(spec=ContainerManager),
        "volumes": MagicMock(spec=VolumeManager),
        "networks": MagicMock(spec=NetworkManager),
    }


def make_runtime(transport, caps, managers, binary="docker"):
    return CliRuntime(
        transport=transport,
        image_manager=managers["images"],
        container_manager=managers["containers"],
        volume_manager=managers["volumes"],
        network_manager=managers["networks"],
        caps=caps,
        binary=binary,
    )


class TestEngineIsAvailable:
    def test_is_available_true_when_probe_succeeds(self, caps, mock_managers):
        transport = RecordingTransport("docker", {
            "docker --version": ExecResult(returncode=0, stdout=b"Docker 24.0.0", stderr=b""),
        })
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.is_available() is True

    def test_is_available_false_when_probe_returns_false(self, caps, mock_managers):
        transport = RecordingTransport("docker")
        transport._probe_result = False
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.is_available() is False

    def test_is_available_delegates_to_probe(self, caps, mock_managers):
        transport = RecordingTransport("docker", {
            "docker --version": ExecResult(returncode=0, stdout=b"Docker 24.0.0", stderr=b""),
        })
        runtime = make_runtime(transport, caps, mock_managers)
        result = runtime.is_available()
        assert isinstance(result, bool)


class TestEngineVersion:
    def test_version_returns_parsed_string(self, caps, mock_managers):
        transport = RecordingTransport("docker", {
            "docker --version": ExecResult(returncode=0, stdout=b"Docker version 24.0.0\n", stderr=b""),
        })
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.version() == "Docker version 24.0.0"

    def test_version_returns_empty_on_nonzero(self, caps, mock_managers):
        transport = RecordingTransport("docker", {
            "docker --version": ExecResult(returncode=1, stdout=b"", stderr=b""),
        })
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.version() == ""

    def test_version_returns_empty_on_exception(self, caps, mock_managers):
        transport = RecordingTransport("docker")
        transport.execute = MagicMock(side_effect=OSError("error"))
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.version() == ""


class TestEngineWiring:
    def test_managers_are_wired(self, caps, mock_managers):
        transport = RecordingTransport("docker")
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.images is mock_managers["images"]
        assert runtime.containers is mock_managers["containers"]
        assert runtime.volumes is mock_managers["volumes"]
        assert runtime.networks is mock_managers["networks"]

    def test_capabilities_stored(self, caps, mock_managers):
        transport = RecordingTransport("docker")
        runtime = make_runtime(transport, caps, mock_managers)
        assert runtime.capabilities is caps

    def test_binary_stored(self, caps, mock_managers):
        transport = RecordingTransport("/usr/bin/docker")
        runtime = CliRuntime(
            transport=transport,
            image_manager=mock_managers["images"],
            container_manager=mock_managers["containers"],
            volume_manager=mock_managers["volumes"],
            network_manager=mock_managers["networks"],
            caps=caps,
            binary="/usr/bin/docker",
        )
        assert runtime._binary == "/usr/bin/docker"
