from __future__ import annotations

from pathlib import Path

from icon_templates_renderer.domain.exceptions import TemplateNotFoundError
from icon_templates_renderer.domain.models import ColorScheme, Variant
from icon_templates_renderer.domain.services import PlaceholderSubstitutionService


class FileSvgRenderer:
    def __init__(self, substitution_service: PlaceholderSubstitutionService | None = None) -> None:
        self._substitution = substitution_service or PlaceholderSubstitutionService()

    def render_variant(
        self,
        variant: Variant,
        scheme: ColorScheme,
        unsafe: bool,
        color_mappings: dict[str, str],
    ) -> Path:
        """Render a single variant to its output path. Returns the output path."""
        if not variant.template.exists():
            raise TemplateNotFoundError(variant.template)

        svg = variant.template.read_text(encoding="utf-8")
        rendered = self.render_string(svg, scheme, unsafe, color_mappings)

        variant.output.parent.mkdir(parents=True, exist_ok=True)
        variant.output.write_text(rendered, encoding="utf-8")
        return variant.output

    def render_string(
        self,
        svg_body: str,
        scheme: ColorScheme,
        unsafe: bool,
        color_mappings: dict[str, str],
    ) -> str:
        """Replace all {{placeholder}} occurrences via color_mappings + color scheme."""
        return self._substitution.substitute(svg_body, scheme, unsafe, color_mappings)
