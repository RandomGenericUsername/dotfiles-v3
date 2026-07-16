from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from color_scheme_generator.domain.models import ColorScheme


@runtime_checkable
class TemplateRendererPort(Protocol):
    def render(self, template_name: str, scheme: ColorScheme, output_path: Path) -> None:
        ...
