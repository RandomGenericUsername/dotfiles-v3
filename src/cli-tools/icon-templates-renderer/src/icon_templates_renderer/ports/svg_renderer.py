from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import ColorScheme, Variant


@runtime_checkable
class SvgRendererPort(Protocol):
    def render_variant(
        self,
        variant: Variant,
        scheme: ColorScheme,
        unsafe: bool,
        color_mappings: dict[str, str],
    ) -> Path: ...
    def render_string(
        self,
        svg_body: str,
        scheme: ColorScheme,
        unsafe: bool,
        color_mappings: dict[str, str],
    ) -> str: ...
