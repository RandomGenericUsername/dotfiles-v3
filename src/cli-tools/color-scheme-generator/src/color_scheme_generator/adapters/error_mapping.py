from __future__ import annotations

from typing import Any

from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    OciError,
    OperationTimeoutError,
    ProviderNotRegisteredError,
    RuntimeNotAvailableError,
)

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    ColorSchemeError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ContainerTimeoutError,
    ImagePullAccessError,
)


def map_oci_error(error: Exception, **context: Any) -> ColorSchemeError:
    if isinstance(error, RuntimeNotAvailableError):
        return ContainerRuntimeUnavailableError(runtime=error.runtime)
    if isinstance(error, ImageNotFoundError):
        backend = context.get("backend", Backend.CUSTOM)
        return ContainerImageNotFoundError(
            image=error.image_name,
            backend=backend,
        )
    if isinstance(error, ImagePullAccessDeniedError):
        return ImagePullAccessError(image=error.image_name, registry=error.registry)
    if isinstance(error, OperationTimeoutError):
        return ContainerTimeoutError()
    if isinstance(error, (ContainerNotFoundError, ContainerRuntimeError)):
        return ContainerRuntimeUnavailableError(runtime=error.message)
    if isinstance(error, ProviderNotRegisteredError):
        return ContainerRuntimeUnavailableError(runtime=str(error.kind))
    if isinstance(error, ImageRuntimeError):
        return ColorSchemeError(str(error))
    if isinstance(error, OciError):
        return ColorSchemeError(str(error))
    return ColorSchemeError(str(error))
