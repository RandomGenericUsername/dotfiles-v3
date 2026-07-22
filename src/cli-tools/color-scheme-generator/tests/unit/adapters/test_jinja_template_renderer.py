from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import TemplateNotFoundError, TemplateRenderError
from color_scheme_generator.domain.models import Color, ColorScheme
from color_scheme_generator.ports.template_renderer import TemplateRendererPort


def _make_scheme() -> ColorScheme:
    return ColorScheme(
        background=Color("#1a1b26", (26, 27, 38)),
        foreground=Color("#c0caf5", (192, 202, 245)),
        cursor=Color("#f7768e", (247, 118, 142)),
        colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=datetime(2024, 1, 1),
    )


class TestJinjaTemplateRenderer:
    def test_render_calls_resolve_and_writes_output(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "output" / "colors.json"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.json.j2").write_text('{"bg": "{{ background.hex }}"}')
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)
        renderer.render("colors.json.j2", scheme, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert scheme.background.hex in content

    def test_render_context_contains_required_fields(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.json"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.json.j2").write_text(
            "{{ source_image }}|{{ backend }}|{{ generated_at }}|"
            "{{ background.hex }}|{{ foreground.hex }}|{{ cursor.hex }}|"
            "{% for c in colors %}{{ c.hex }},{% endfor %}"
        )
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)
        renderer.render("colors.json.j2", scheme, output_path)

        content = output_path.read_text()
        assert str(scheme.source_image) in content
        assert scheme.backend.value in content
        assert scheme.generated_at.isoformat() in content
        assert scheme.background.hex in content
        assert scheme.foreground.hex in content
        assert scheme.cursor.hex in content
        for c in scheme.colors:
            assert c.hex in content

    def test_render_uses_strict_undefined(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.json"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.json.j2").write_text("{{ undefined_var }}")
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)

        with pytest.raises(TemplateRenderError):
            renderer.render("colors.json.j2", scheme, output_path)

    def test_render_creates_parent_directories(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "deep" / "nested" / "dir" / "colors.json"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.json.j2").write_text("ok")
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)
        renderer.render("colors.json.j2", scheme, output_path)

        assert output_path.exists()

    def test_render_raises_template_not_found(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.json"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)

        with pytest.raises(TemplateNotFoundError) as exc_info:
            renderer.render("nonexistent.j2", scheme, output_path)

        assert exc_info.value.template_name == "nonexistent.j2"
        assert isinstance(exc_info.value.searched_paths, tuple)

    def test_render_raises_template_render_error_on_failure(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.json"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.json.j2").write_text("{{ bad syntax")
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)

        with pytest.raises(TemplateRenderError) as exc_info:
            renderer.render("colors.json.j2", scheme, output_path)

        assert exc_info.value.template_name == "colors.json.j2"

    def test_sequences_post_processing(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.sequences"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.sequences.j2").write_text("]10;{{ background.hex }}\\")
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)
        renderer.render("colors.sequences.j2", scheme, output_path)

        content = output_path.read_bytes()
        assert b"\x1b]" in content
        assert b"\x1b\\" in content
        assert scheme.background.hex.encode() in content

    def test_sequences_output_bytes(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.sequences"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.sequences.j2").write_text("]10;{{ background.hex }}\\")
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)
        renderer.render("colors.sequences.j2", scheme, output_path)

        content = output_path.read_bytes()
        assert isinstance(content, bytes)

    def test_sequences_osc_escapes(self, tmp_path: Path) -> None:
        scheme = _make_scheme()
        output_path = tmp_path / "colors.sequences"

        resolver = MagicMock()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "colors.sequences.j2").write_text("]10;{{ background.hex }}\\")
        resolver.resolve.return_value = templates_dir

        renderer = JinjaTemplateRenderer(resolver)
        renderer.render("colors.sequences.j2", scheme, output_path)

        content = output_path.read_bytes()
        assert b"\x1b]" in content
        assert b"\x1b\\" in content

    def test_structural_subtyping(self) -> None:
        resolver = MagicMock()
        renderer = JinjaTemplateRenderer(resolver)

        assert isinstance(renderer, TemplateRendererPort)
