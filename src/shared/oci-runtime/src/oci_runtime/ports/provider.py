from abc import ABC, abstractmethod

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers


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
