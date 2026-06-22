from abc import ABC, abstractmethod

from oci_runtime.domain.types import RuntimePreference


class RuntimeDiscovery(ABC):
    @abstractmethod
    def available(self) -> list[RuntimePreference]: ...
