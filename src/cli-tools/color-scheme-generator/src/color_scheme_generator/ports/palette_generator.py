from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from color_scheme_generator.domain.models import ColorScheme, GeneratorConfig


@runtime_checkable
class PaletteGeneratorPort(Protocol):
    def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
        ...

    def is_available(self) -> bool:
        ...
