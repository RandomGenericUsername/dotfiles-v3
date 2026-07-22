from __future__ import annotations

from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
    ColorSchemeError,
    ConfigResolutionError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ContainerTimeoutError,
    ImageBuildError,
    ImagePullAccessError,
    ImageRemoveError,
    InvalidImageError,
    OutputWriteError,
    PaletteGenerationError,
    TemplateNotFoundError,
    TemplateRenderError,
)

__all__ = [
    "ColorSchemeError",
    "InvalidImageError",
    "ColorExtractionError",
    "BackendNotAvailableError",
    "OutputWriteError",
    "ConfigResolutionError",
    "PaletteGenerationError",
    "TemplateNotFoundError",
    "TemplateRenderError",
    "ContainerImageNotFoundError",
    "ContainerRuntimeUnavailableError",
    "ContainerTimeoutError",
    "ImageBuildError",
    "ImagePullAccessError",
    "ImageRemoveError",
]
