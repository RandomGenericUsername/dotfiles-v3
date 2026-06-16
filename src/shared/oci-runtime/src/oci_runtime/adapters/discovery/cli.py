from typing import Callable

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.transport import Transport


class CliRuntimeDiscovery(RuntimeDiscovery):
    def __init__(self, transport_factory: Callable[[str], Transport]):
        self._transport_factory = transport_factory

    def available(self) -> list[RuntimePreference]:
        available = []
        for kind in RuntimeKind:
            pref = RuntimePreference(kind=kind, binary=kind.value)
            binary = pref.binary
            try:
                transport = self._transport_factory(binary)
                if transport.probe():
                    available.append(pref)
            except (FileNotFoundError, OSError, RuntimeNotAvailableError):
                continue
        return available
