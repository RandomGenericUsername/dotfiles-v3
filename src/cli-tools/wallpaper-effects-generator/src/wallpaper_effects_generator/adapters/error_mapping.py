from __future__ import annotations

from oci_runtime.domain.exceptions import (
    ImageError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    RuntimeNotAvailableError,
)

from wallpaper_effects_generator.domain.exceptions import (
    CommandExecutionError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ImagePullAccessError,
    WallpaperEffectsError,
)


def map_oci_error(error: Exception) -> WallpaperEffectsError:
    if isinstance(error, RuntimeNotAvailableError):
        return ContainerRuntimeUnavailableError(runtime=error.runtime)
    if isinstance(error, ImageNotFoundError):
        return ContainerImageNotFoundError(image=error.image_name)
    if isinstance(error, ImagePullAccessDeniedError):
        return ImagePullAccessError(image=error.image_name, registry=error.registry)
    if isinstance(error, ImageError):
        return CommandExecutionError(
            command=" ".join(error.command) if error.command else "oci-runtime",
            return_code=error.exit_code if error.exit_code is not None else -1,
            stderr=error.stderr or str(error),
        )
    return CommandExecutionError(
        command="oci-runtime",
        return_code=-1,
        stderr=str(error),
    )
