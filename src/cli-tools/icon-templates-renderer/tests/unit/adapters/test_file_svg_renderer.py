from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.file_svg_renderer import FileSvgRenderer
from icon_templates_renderer.domain.exceptions import TemplateNotFoundError
from icon_templates_renderer.domain.models import ColorScheme, Variant


def _variant(tmp_path: Path, template_name: str = "icon.svg") -> Variant:
    template = tmp_path / "templates" / template_name
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text('<path fill="{{background}}"/>')
    return Variant(
        name="icon",
        template=template,
        output=tmp_path / "out" / "deep" / "icon.svg",
    )


class TestFileSvgRenderer:
    def setup_method(self) -> None:
        self.renderer = FileSvgRenderer()
        self.scheme = ColorScheme.from_dict({"background": "#1a1a2e"})

    def test_missing_template_raises(self, tmp_path: Path) -> None:
        variant = Variant(
            name="icon",
            template=tmp_path / "missing.svg",
            output=tmp_path / "out.svg",
        )
        with pytest.raises(TemplateNotFoundError) as excinfo:
            self.renderer.render_variant(variant, self.scheme, False, {"background": "background"})
        assert f"Template not found: {variant.template}" in str(excinfo.value)

    def test_output_dir_created_and_file_written(self, tmp_path: Path) -> None:
        variant = _variant(tmp_path)
        out = self.renderer.render_variant(
            variant, self.scheme, False, {"background": "background"}
        )
        assert out.exists()
        assert out.read_text() == '<path fill="#1a1a2e"/>'

    def test_render_string_delegates(self) -> None:
        out = self.renderer.render_string(
            "{{background}}", self.scheme, False, {"background": "background"}
        )
        assert out == "#1a1a2e"
