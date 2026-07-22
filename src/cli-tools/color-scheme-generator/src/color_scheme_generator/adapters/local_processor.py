from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    BackendNotRegisteredError,
    ColorSchemeError,
)
from color_scheme_generator.domain.models import ColorScheme, GenerationResult
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort

if TYPE_CHECKING:
    from color_scheme_generator.domain.models import AppSettings, GenerationRequest
    from color_scheme_generator.ports.template_renderer import TemplateRendererPort


class LocalProcessor:
    def __init__(
        self,
        backend_registry: dict[Backend, PaletteGeneratorPort],
        template_renderer: TemplateRendererPort | None = None,
    ) -> None:
        self._backend_registry = backend_registry
        self._template_renderer = template_renderer

    def _get_backend_generator(self, backend: Backend) -> PaletteGeneratorPort:
        try:
            return self._backend_registry[backend]
        except KeyError:
            raise BackendNotRegisteredError(backend) from None

    def _generate_extract(
        self, request: GenerationRequest
    ) -> tuple[ColorScheme, float]:
        generator = self._get_backend_generator(request.config.backend)

        if not generator.is_available():
            if not self._backend_registry:
                raise BackendNotAvailableError(
                    request.config.backend,
                    "No backends are registered. "
                    "Run `csg install` for container-mode execution "
                    "or install a backend binary.",
                )
            unavailable = [
                b.value for b, g in self._backend_registry.items()
                if not g.is_available()
            ]
            if len(unavailable) == len(self._backend_registry):
                tried = ", ".join(unavailable)
                raise BackendNotAvailableError(
                    request.config.backend,
                    f"No backends available: {tried}. "
                    f"Run `csg install` for container-mode execution "
                    f"or install a backend binary.",
                )
            raise BackendNotAvailableError(
                request.config.backend, request.config.backend.install_hint
            )

        start = time.monotonic()
        color_scheme = generator.generate(request.image_path, request.config)
        duration = time.monotonic() - start

        return color_scheme, duration

    def _render_formats(
        self,
        color_scheme: ColorScheme,
        request: GenerationRequest,
    ) -> tuple[list[Path], str]:
        if self._template_renderer is None:
            return [], ""

        output_files: list[Path] = []
        errors: list[str] = []

        for fmt in request.config.formats:
            template_name = f"colors.{fmt.value}.j2"
            output_path = request.config.output_dir / f"colors.{fmt.value}"
            try:
                self._template_renderer.render(template_name, color_scheme, output_path)
                output_files.append(output_path)
            except ColorSchemeError as exc:
                errors.append(str(exc))

        return output_files, "; ".join(errors)

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        color_scheme, duration = self._generate_extract(request)

        output_files, stderr = self._render_formats(color_scheme, request)

        return GenerationResult(
            success=not stderr,
            color_scheme=color_scheme,
            output_files=tuple(output_files),
            backend=request.config.backend,
            stderr=stderr,
            return_code=0,
            duration=duration,
        )

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        color_scheme, duration = self._generate_extract(request)

        return GenerationResult(
            success=True,
            color_scheme=color_scheme,
            output_files=(),
            backend=request.config.backend,
            stderr="",
            return_code=0,
            duration=duration,
        )
