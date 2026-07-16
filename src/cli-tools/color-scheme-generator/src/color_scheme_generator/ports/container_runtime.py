from __future__ import annotations

from typing import Protocol, runtime_checkable

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
