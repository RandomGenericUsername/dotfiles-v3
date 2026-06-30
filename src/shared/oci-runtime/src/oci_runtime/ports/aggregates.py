from dataclasses import dataclass

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
