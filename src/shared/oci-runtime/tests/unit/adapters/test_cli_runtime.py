import pytest
from unittest.mock import MagicMock

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.exceptions import OciError
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


class TestCliRuntime:
    def test_stores_managers(self):
        transport = _mock_transport()
        caps = RuntimeCapabilities()
        images = MagicMock(spec=ImageManager)
        containers = MagicMock(spec=ContainerManager)
        volumes = MagicMock(spec=VolumeManager)
        networks = MagicMock(spec=NetworkManager)

        runtime = CliRuntime(
            transport=transport,
            image_manager=images,
            container_manager=containers,
            volume_manager=volumes,
            network_manager=networks,
            caps=caps,
        )

        assert runtime.images is images
        assert runtime.containers is containers
        assert runtime.volumes is volumes
        assert runtime.networks is networks
        assert runtime.capabilities is caps

    def test_is_available_true_when_transport_succeeds(self):
        transport = MagicMock(spec=Transport)
        transport.probe.return_value = True
        runtime = CliRuntime(
            transport=transport,
            image_manager=MagicMock(spec=ImageManager),
            container_manager=MagicMock(spec=ContainerManager),
            volume_manager=MagicMock(spec=VolumeManager),
            network_manager=MagicMock(spec=NetworkManager),
            caps=RuntimeCapabilities(),
        )
        assert runtime.is_available() is True

    def test_is_available_false_when_probe_returns_false(self):
        transport = MagicMock(spec=Transport)
        transport.probe.return_value = False
        runtime = CliRuntime(
            transport=transport,
            image_manager=MagicMock(spec=ImageManager),
            container_manager=MagicMock(spec=ContainerManager),
            volume_manager=MagicMock(spec=VolumeManager),
            network_manager=MagicMock(spec=NetworkManager),
            caps=RuntimeCapabilities(),
        )
        assert runtime.is_available() is False

    def test_is_available_propagates_unexpected_exception(self):
        transport = MagicMock(spec=Transport)
        transport.probe.side_effect = Exception("unexpected")
        runtime = CliRuntime(
            transport=transport,
            image_manager=MagicMock(spec=ImageManager),
            container_manager=MagicMock(spec=ContainerManager),
            volume_manager=MagicMock(spec=VolumeManager),
            network_manager=MagicMock(spec=NetworkManager),
            caps=RuntimeCapabilities(),
        )
        with pytest.raises(Exception):
            runtime.is_available()

    def test_version_raises_on_non_zero_exit(self):
        transport = MagicMock(spec=Transport)
        transport.get_runtime_binary.return_value = "docker"
        transport.execute.return_value = RawExecResult(
            returncode=1, stdout=b"", stderr=b"error"
        )
        runtime = CliRuntime(
            transport=transport,
            image_manager=MagicMock(spec=ImageManager),
            container_manager=MagicMock(spec=ContainerManager),
            volume_manager=MagicMock(spec=VolumeManager),
            network_manager=MagicMock(spec=NetworkManager),
            caps=RuntimeCapabilities(),
        )
        with pytest.raises(OciError, match="docker"):
            runtime.version()

    def test_version_returns_string_on_success(self):
        transport = MagicMock(spec=Transport)
        transport.get_runtime_binary.return_value = "docker"
        transport.execute.return_value = RawExecResult(
            returncode=0, stdout=b"Docker version 24.0.0\n", stderr=b""
        )
        runtime = CliRuntime(
            transport=transport,
            image_manager=MagicMock(spec=ImageManager),
            container_manager=MagicMock(spec=ContainerManager),
            volume_manager=MagicMock(spec=VolumeManager),
            network_manager=MagicMock(spec=NetworkManager),
            caps=RuntimeCapabilities(),
        )
        assert runtime.version() == "Docker version 24.0.0"


def _mock_transport(result: RawExecResult | None = None) -> MagicMock:
    transport = MagicMock(spec=Transport)
    if result:
        transport.execute.return_value = result
    return transport
