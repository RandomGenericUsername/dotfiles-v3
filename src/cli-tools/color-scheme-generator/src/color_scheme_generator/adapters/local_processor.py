from __future__ import annotations

import time
from typing import TYPE_CHECKING

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    BackendNotRegisteredError,
)
from color_scheme_generator.domain.models import GenerationResult
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort

if TYPE_CHECKING:
    from color_scheme_generator.domain.models import AppSettings, GenerationRequest


class LocalProcessor:
    def __init__(
        self, backend_registry: dict[Backend, PaletteGeneratorPort]
    ) -> None:
        self._backend_registry = backend_registry

    def _get_backend_generator(self, backend: Backend) -> PaletteGeneratorPort:
        try:
            return self._backend_registry[backend]
        except KeyError:
            raise BackendNotRegisteredError(backend) from None

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        generator = self._get_backend_generator(request.config.backend)

        if not generator.is_available():
            raise BackendNotAvailableError(
                request.config.backend, request.config.backend.install_hint
            )

        start = time.monotonic()
        color_scheme = generator.generate(request.image_path, request.config)
        duration = time.monotonic() - start

        return GenerationResult(
            success=True,
            color_scheme=color_scheme,
            output_files=(),
            backend=request.config.backend,
            stderr="",
            return_code=0,
            duration=duration,
        )

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        return self.process_generate(request, settings)
