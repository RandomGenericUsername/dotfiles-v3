from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from color_scheme_generator.domain.models import GenerationRequest, GenerationResult

if TYPE_CHECKING:
    from color_scheme_generator.domain.models import AppSettings


@runtime_checkable
class ColorSchemeProcessorPort(Protocol):
    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult: ...

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult: ...
