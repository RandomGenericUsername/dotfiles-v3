from __future__ import annotations

from typing import Protocol, runtime_checkable

from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import ColorScheme, GenerationResult


@runtime_checkable
class OutputPort(Protocol):
    def process_result(self, result: GenerationResult) -> None:
        ...

    def error(self, exc: ColorSchemeError) -> None:
        ...

    def palette_display(self, scheme: ColorScheme) -> None:
        ...
