from abc import ABC, abstractmethod

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.aggregates import Managers, Parsers
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport


class RuntimeProvider(ABC):
    """Port: encapsulates all runtime-specific knowledge.

    Pure abstraction — no I/O, no side effects, no adapter imports.
    The factory depends on this port, not on concrete registries.
    """

    @property
    @abstractmethod
    def kind(self) -> RuntimeKind:
        """Return the RuntimeKind enum member for this runtime."""

    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """Return the capabilities for this runtime."""

    @abstractmethod
    def create_parsers(self) -> Parsers:
        """Create and return parser instances for this runtime."""

    @abstractmethod
    def create_managers(
        self,
        transport: Transport,
        streaming_transport: StreamingTransport,
        caps: RuntimeCapabilities,
    ) -> Managers:
        """Create and return manager instances for this runtime."""
