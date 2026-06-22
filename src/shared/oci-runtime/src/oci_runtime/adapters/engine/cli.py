from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.ports.transport import Transport


class CliRuntime(ContainerEngine):
    def __init__(
        self,
        transport: Transport,
        image_manager: ImageManager,
        container_manager: ContainerManager,
        volume_manager: VolumeManager,
        network_manager: NetworkManager,
        caps: RuntimeCapabilities,
    ):
        self._transport = transport
        self._images = image_manager
        self._containers = container_manager
        self._volumes = volume_manager
        self._networks = network_manager
        self._caps = caps

    @property
    def images(self) -> ImageManager:
        return self._images

    @property
    def containers(self) -> ContainerManager:
        return self._containers

    @property
    def volumes(self) -> VolumeManager:
        return self._volumes

    @property
    def networks(self) -> NetworkManager:
        return self._networks

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return self._caps

    def is_available(self) -> bool:
        return self._transport.probe()

    def version(self) -> str:
        """Get the version of the container engine."""
        result = self._transport.execute(
            [self._transport.get_runtime_binary(), "--version"]
        )
        if result.returncode == 0:
            return result.stdout.decode("utf-8", errors="replace").strip()
        raise RuntimeNotAvailableError(self._transport.get_runtime_binary())
