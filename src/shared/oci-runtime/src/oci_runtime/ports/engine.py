from abc import ABC, abstractmethod

from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)


class ContainerEngine(ABC):
    @property
    @abstractmethod
    def images(self) -> ImageManager: ...

    @property
    @abstractmethod
    def containers(self) -> ContainerManager: ...

    @property
    @abstractmethod
    def volumes(self) -> VolumeManager: ...

    @property
    @abstractmethod
    def networks(self) -> NetworkManager: ...

    @property
    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def version(self) -> str: ...



