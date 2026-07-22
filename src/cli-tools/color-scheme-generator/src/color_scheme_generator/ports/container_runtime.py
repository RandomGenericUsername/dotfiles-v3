from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from oci_runtime.domain.types import BuildContext

from color_scheme_generator.domain.models import ContainerMount, ContainerResult


@runtime_checkable
class ContainerRuntimePort(Protocol):
    def run(
        self,
        image: str,
        command: list[str],
        mounts: list[ContainerMount],
        timeout: int,
    ) -> ContainerResult:
        ...

    def image_exists(self, image: str) -> bool:
        ...

    def pull_image(self, image: str) -> None:
        ...

    def build_image(
        self,
        context: BuildContext,
        image_name: str,
        timeout: int | None = 600,
    ) -> str:
        ...

    def remove_image(self, image: str, force: bool = False) -> None:
        ...
