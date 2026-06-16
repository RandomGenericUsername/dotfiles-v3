from dataclasses import dataclass
from typing import Callable

from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.engine import ContainerEngine
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
from oci_runtime.ports.transport import Transport


@dataclass(frozen=True)
class Parsers:
    """Typed container for parser instances (replaces bare tuple)."""
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


@dataclass(frozen=True)
class RuntimeFactoryConfig:
    """Composition root configuration.

    This is the ONLY place where adapter implementations are wired.
    Allows injection of mock implementations for testing.
    All fields default to None — the factory resolves them to production
    implementations on first use (lazy loading).

    Parsers are owned by RuntimeProvider — the factory delegates to
    providers for parser resolution, not to a separate callback.
    """
    transport_factory: Callable[[str], Transport] | None = None
    runtime_cls: type[ContainerEngine] | None = None
    discovery_factory: Callable[[Callable[[str], Transport]], "RuntimeDiscovery"] | None = None
