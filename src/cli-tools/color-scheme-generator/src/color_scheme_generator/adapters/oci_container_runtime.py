from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oci_runtime.ports.engine import ContainerEngine as OciContainerEngine

    from color_scheme_generator.domain.models import ContainerMount, ContainerResult


class OciContainerRuntimeAdapter:
    def __init__(self, engine: OciContainerEngine) -> None:
        self._engine = engine

    def run(
        self,
        image: str,
        command: list[str],
        mounts: list[ContainerMount],
        timeout: int,
    ) -> ContainerResult:
        from oci_runtime.domain.enums import VolumeMountType
        from oci_runtime.domain.types import RunConfig, VolumeMount

        volumes = tuple(
            VolumeMount(
                source=str(m.source),
                target=str(m.target),
                type=VolumeMountType.BIND,
                read_only=m.read_only,
            )
            for m in mounts
        )
        config = RunConfig(
            image=image,
            command=(),
            volumes=volumes,
            timeout=float(timeout),
            detach=True,
            remove=False,
        )
        container_id = self._engine.containers.run(config)
        result = self._engine.containers.exec_container(
            container=container_id,
            command=list(command),
            timeout=float(timeout),
        )
        from color_scheme_generator.domain.models import ContainerResult

        return ContainerResult(
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration=0.0,
        )

    def image_exists(self, image: str) -> bool:
        return self._engine.images.exists(image)

    def pull_image(self, image: str) -> None:
        self._engine.images.pull(image)
