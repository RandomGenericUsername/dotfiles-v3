from dataclasses import dataclass

from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)


@dataclass(frozen=True)
class Parsers:
    """Typed container for parser instances."""

    container_parser: ContainerParser
    image_parser: ImageParser
    volume_parser: VolumeParser
    network_parser: NetworkParser


@dataclass(frozen=True)
class Managers:
    """Typed container for manager instances."""

    image_manager: ImageManager
    container_manager: ContainerManager
    volume_manager: VolumeManager
    network_manager: NetworkManager
