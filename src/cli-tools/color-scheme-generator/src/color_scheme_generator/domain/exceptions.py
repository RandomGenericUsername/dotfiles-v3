from __future__ import annotations

from pathlib import Path
from typing import Any

from color_scheme_generator.domain.enums import Backend


class ColorSchemeError(Exception):
    pass


class InvalidImageError(ColorSchemeError):
    def __init__(self, image_path: Path, reason: str) -> None:
        self.image_path = image_path
        self.reason = reason
        super().__init__(f"Invalid image {image_path}: {reason}")


class ColorExtractionError(ColorSchemeError):
    def __init__(self, backend: Backend, message: str, stderr: str = "") -> None:
        self.backend = backend
        self.message = message
        self.stderr = stderr
        super().__init__(f"Color extraction failed for {backend.value}: {message}")


class BackendNotAvailableError(ColorSchemeError):
    def __init__(self, backend: Backend, hint: str) -> None:
        self.backend = backend
        self.hint = hint
        super().__init__(f"Backend {backend.value} is not available. Hint: {hint}")


class OutputWriteError(ColorSchemeError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to write output to {path}: {reason}")


class ConfigResolutionError(ColorSchemeError):
    def __init__(self, key: str, reason: str, source: Any = None) -> None:
        self.key = key
        self.reason = reason
        self.source = source
        super().__init__(f"Config resolution failed for {key}: {reason}")


class BackendNotRegisteredError(ColorSchemeError):
    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        super().__init__(
            f"Backend '{backend.value}' not found in registry"
        )


class PaletteGenerationError(ColorSchemeError):
    def __init__(self, message: str, backend: Backend | None = None) -> None:
        self.message = message
        self.backend = backend
        prefix = f"[{backend.value}] " if backend else ""
        super().__init__(f"{prefix}Palette generation failed: {message}")


class TemplateNotFoundError(ColorSchemeError):
    def __init__(self, template_name: str, searched_paths: tuple[Path, ...]) -> None:
        self.template_name = template_name
        self.searched_paths = searched_paths
        super().__init__(
            f"Template '{template_name}' not found. Searched: {searched_paths}"
        )


class TemplateRenderError(ColorSchemeError):
    def __init__(self, template_name: str, reason: str) -> None:
        self.template_name = template_name
        self.reason = reason
        super().__init__(f"Failed to render template '{template_name}': {reason}")


class ContainerImageNotFoundError(ColorSchemeError):
    def __init__(self, image: str, backend: Backend) -> None:
        self.image = image
        self.backend = backend
        super().__init__(f"Container image '{image}' not found for backend {backend.value}")


class ContainerRuntimeUnavailableError(ColorSchemeError):
    def __init__(self, runtime: str) -> None:
        self.runtime = runtime
        super().__init__(f"Container runtime '{runtime}' is not available")


class ImagePullAccessError(ColorSchemeError):
    def __init__(self, image: str, registry: str) -> None:
        self.image = image
        self.registry = registry
        super().__init__(f"Access denied pulling image '{image}' from registry '{registry}'")


class ContainerTimeoutError(ColorSchemeError):
    pass


class ImageBuildError(ColorSchemeError):
    def __init__(self, image: str, reason: str, backend: Backend | None = None) -> None:
        self.image = image
        self.reason = reason
        self.backend = backend
        prefix = f" for backend {backend.value}" if backend else ""
        super().__init__(
            f"Failed to build image '{image}'{prefix}: {reason if reason else 'unknown error'}"
        )


class ImageRemoveError(ColorSchemeError):
    def __init__(self, image: str, reason: str, backend: Backend | None = None) -> None:
        self.image = image
        self.reason = reason
        self.backend = backend
        prefix = f" for backend {backend.value}" if backend else ""
        super().__init__(
            f"Failed to remove image '{image}'{prefix}: {reason if reason else 'unknown error'}"
        )
