from abc import ABC, abstractmethod

from oci_runtime.ports.capabilities import RuntimePreference


class RuntimeDiscovery(ABC):
    @abstractmethod
    def available(self) -> list[RuntimePreference]:
        ...
