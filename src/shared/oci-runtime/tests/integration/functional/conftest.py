import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.capabilities import RuntimeCapabilities
from tests.helpers.mock_parsers import (
    MockContainerParser,
    MockImageParser,
    MockNetworkParser,
    MockVolumeParser,
)
from tests.helpers.mock_transport import RecordingTransport, RecordingStreamingTransport, FakeTtyDetector


@pytest.fixture
def docker_pref():
    return RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")


@pytest.fixture
def docker_caps(docker_pref):
    return RuntimeCapabilities(
        supports_log_drivers=True,
        tar_entry_name="Dockerfile",
        default_build_flags=["--quiet"],
    )


@pytest.fixture
def docker_parsers():
    return (
        MockContainerParser(),
        MockImageParser(),
        MockVolumeParser(),
        MockNetworkParser(),
    )


@pytest.fixture
def empty_transport():
    return RecordingTransport("docker")


@pytest.fixture
def empty_streaming():
    return RecordingStreamingTransport("docker")


@pytest.fixture
def docker_engine(empty_transport, empty_streaming, docker_caps, docker_parsers):
    cp, ip, vp, np = docker_parsers
    return CliRuntime(
        transport=empty_transport,
        image_manager=CliImageManager(empty_transport, ip, docker_caps),
        container_manager=CliContainerManager(empty_transport, cp, docker_caps, streaming=empty_streaming, tty_detector=FakeTtyDetector()),
        volume_manager=CliVolumeManager(empty_transport, vp, docker_caps),
        network_manager=CliNetworkManager(empty_transport, np, docker_caps),
        caps=docker_caps,
    )
