from abc import ABC, abstractmethod
from typing import Iterator

from oci_runtime.domain.types import (
    BuildContext,
    ContainerInfo,
    ExecOutput,
    ImageInfo,
    NetworkInfo,
    RunConfig,
    VolumeInfo,
)

class ImageManager(ABC):
    @abstractmethod
    def build(self, context: BuildContext, image_name: str, timeout: int = 600) -> str: ...

    @abstractmethod
    def tag(self, image: str, tag: str) -> None: ...

    @abstractmethod
    def push(self, image: str, timeout: int = 300) -> None: ...

    @abstractmethod
    def pull(self, image: str, timeout: int = 300) -> str: ...

    @abstractmethod
    def remove(self, image: str, force: bool = False) -> None: ...

    @abstractmethod
    def exists(self, image: str) -> bool: ...

    @abstractmethod
    def inspect(self, image: str) -> ImageInfo: ...

    @abstractmethod
    def list(self, filters: dict[str, str] | None = None) -> list[ImageInfo]: ...

    @abstractmethod
    def prune(self, show_all: bool = False) -> dict[str, int]: ...


class ContainerManager(ABC):
    @abstractmethod
    def run(self, config: RunConfig) -> str: ...

    @abstractmethod
    def start(self, container: str) -> None: ...

    @abstractmethod
    def stop(self, container: str, timeout: int = 10) -> None: ...

    @abstractmethod
    def restart(self, container: str, timeout: int = 10) -> None: ...

    @abstractmethod
    def remove(self, container: str, force: bool = False, volumes: bool = False) -> None: ...

    @abstractmethod
    def exists(self, container: str) -> bool: ...

    @abstractmethod
    def inspect(self, container: str) -> ContainerInfo: ...

    @abstractmethod
    def list(self, show_all: bool = False, filters: dict[str, str] | None = None) -> list[ContainerInfo]: ...

    @abstractmethod
    def logs(self, container: str, follow: bool = False, tail: int | None = None) -> Iterator[str]: ...

    @abstractmethod
    def exec_container(self, container: str, command: list[str], detach: bool = False, user: str | None = None) -> ExecOutput: ...

    @abstractmethod
    def prune(self) -> dict[str, int]: ...


class VolumeManager(ABC):
    @abstractmethod
    def create(self, name: str, driver: str = "local", labels: dict[str, str] | None = None) -> str: ...

    @abstractmethod
    def remove(self, name: str, force: bool = False) -> None: ...

    @abstractmethod
    def exists(self, name: str) -> bool: ...

    @abstractmethod
    def inspect(self, name: str) -> VolumeInfo: ...

    @abstractmethod
    def list(self, filters: dict[str, str] | None = None) -> list[VolumeInfo]: ...

    @abstractmethod
    def prune(self) -> dict[str, int]: ...


class NetworkManager(ABC):
    @abstractmethod
    def create(self, name: str, driver: str = "bridge", labels: dict[str, str] | None = None) -> str: ...

    @abstractmethod
    def remove(self, name: str) -> None: ...

    @abstractmethod
    def connect(self, network: str, container: str) -> None: ...

    @abstractmethod
    def disconnect(self, network: str, container: str, force: bool = False) -> None: ...

    @abstractmethod
    def exists(self, name: str) -> bool: ...

    @abstractmethod
    def inspect(self, name: str) -> NetworkInfo: ...

    @abstractmethod
    def list(self, filters: dict[str, str] | None = None) -> list[NetworkInfo]: ...

    @abstractmethod
    def prune(self) -> dict[str, int]: ...
