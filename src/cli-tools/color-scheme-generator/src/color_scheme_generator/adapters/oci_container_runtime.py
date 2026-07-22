from __future__ import annotations

from typing import TYPE_CHECKING

from color_scheme_generator.domain.enums import Backend

if TYPE_CHECKING:
    from oci_runtime.domain.types import BuildContext
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
        from color_scheme_generator.adapters.error_mapping import map_oci_error

        container_id = None
        try:
            container_id = self._engine.containers.run(config)
            result = self._engine.containers.exec_container(
                container=container_id,
                command=list(command),
                timeout=float(timeout),
            )
        except Exception as exc:
            raise map_oci_error(exc) from exc
        finally:
            if container_id is not None:
                self._engine.containers.remove(container_id)

        from color_scheme_generator.domain.models import ContainerResult

        return ContainerResult(
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration=0.0,
        )

    def image_exists(self, image: str) -> bool:
        from color_scheme_generator.adapters.error_mapping import map_oci_error

        try:
            return self._engine.images.exists(image)
        except Exception as exc:
            raise map_oci_error(exc) from exc

    def pull_image(self, image: str) -> None:
        from color_scheme_generator.adapters.error_mapping import map_oci_error

        try:
            self._engine.images.pull(image)
        except Exception as exc:
            raise map_oci_error(exc) from exc

    def build_image(
        self,
        context: BuildContext,
        image_name: str,
        timeout: int | None = 600,
        backend: Backend | None = None,
    ) -> str:
        from oci_runtime.domain.exceptions import ImageError

        from color_scheme_generator.domain.exceptions import ImageBuildError

        if timeout is not None and timeout <= 0:
            raise ImageBuildError(image=image_name, reason=f"Invalid timeout: {timeout}", backend=backend)
        try:
            return self._engine.images.build(context, image_name, timeout)
        except ImageError as exc:
            raise ImageBuildError(
                image=image_name,
                reason=str(exc),
                backend=backend,
            ) from exc

    def remove_image(self, image: str, force: bool = False, backend: Backend | None = None) -> None:
        from oci_runtime.domain.exceptions import ImageError

        from color_scheme_generator.domain.exceptions import ImageRemoveError

        try:
            self._engine.images.remove(image, force=force)
        except ImageError as exc:
            raise ImageRemoveError(
                image=image,
                reason=str(exc),
                backend=backend,
            ) from exc
