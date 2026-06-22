from abc import ABC, abstractmethod

from oci_runtime.domain.exceptions import ParsingError
from oci_runtime.domain.types import ContainerInfo, ImageInfo, NetworkInfo, PruneResult, VolumeInfo


__all__ = [
    "ParsingError",
    "ContainerParser",
    "ImageParser",
    "VolumeParser",
    "NetworkParser",
]


class ContainerParser(ABC):
    @abstractmethod
    def parse_inspect(self, raw: str) -> ContainerInfo: ...

    @abstractmethod
    def parse_list(self, raw: str) -> list[ContainerInfo]: ...

    @abstractmethod
    def parse_prune(self, raw: str) -> PruneResult: ...

    @abstractmethod
    def is_not_found_error(self, stderr: str) -> bool: ...


class ImageParser(ABC):
    @abstractmethod
    def parse_inspect(self, raw: str) -> ImageInfo: ...

    @abstractmethod
    def parse_list(self, raw: str) -> list[ImageInfo]: ...

    @abstractmethod
    def parse_build_output(self, raw: str) -> str: ...

    @abstractmethod
    def parse_id_from_pull(self, raw: str) -> str: ...

    @abstractmethod
    def parse_prune(self, raw: str) -> PruneResult: ...

    @abstractmethod
    def is_not_found_error(self, stderr: str) -> bool: ...


class VolumeParser(ABC):
    @abstractmethod
    def parse_inspect(self, raw: str) -> VolumeInfo: ...

    @abstractmethod
    def parse_list(self, raw: str) -> list[VolumeInfo]: ...

    @abstractmethod
    def parse_prune(self, raw: str) -> PruneResult: ...

    @abstractmethod
    def is_not_found_error(self, stderr: str) -> bool: ...


class NetworkParser(ABC):
    @abstractmethod
    def parse_inspect(self, raw: str) -> NetworkInfo: ...

    @abstractmethod
    def parse_list(self, raw: str) -> list[NetworkInfo]: ...

    @abstractmethod
    def parse_prune(self, raw: str) -> PruneResult: ...

    @abstractmethod
    def is_not_found_error(self, stderr: str) -> bool: ...
