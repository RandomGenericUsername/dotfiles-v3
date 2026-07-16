from __future__ import annotations

from pathlib import Path

from color_scheme_generator.domain.models import ColorScheme, GeneratorConfig


class PywalGenerator:
    def is_available(self) -> bool:
        return False

    def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
        raise NotImplementedError("PywalGenerator will be implemented in Story 2.4")
