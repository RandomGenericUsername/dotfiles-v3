from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.file_template_writer import FileTemplateWriter
from icon_templates_renderer.domain.enums import TemplateMode
from icon_templates_renderer.domain.exceptions import (
    InvalidPlaceholderNameError,
    TemplateNotFoundError,
    TemplatePaintAttributeError,
    UnknownTemplateShapeError,
)
from icon_templates_renderer.domain.models import TemplateSetPlaceholderRequest
from icon_templates_renderer.domain.services import TemplateAnalysisService
from icon_templates_renderer.ports.template_writer import TemplateWriterPort

SIBLINGS = (
    '<svg width="24" height="24" fill="none">\n'
    '<path d="M0 0L1 1" stroke="{{COLOR_FOREGROUND}}"/>\n'
    '<path d="M2 2L3 3" stroke="{{COLOR_FOREGROUND}}"/>\n'
    '<path d="M4 4L5 5" stroke="{{COLOR_FOREGROUND}}"/>\n'
    "</svg>"
)

BARE_HEX = (
    '<svg width="24" height="24">\n'
    '<path fill="#c2c2c5" d="M0 0L1 1"/>\n'
    '<rect fill="#ffffff" x="0" y="0" width="4" height="4"/>\n'
    "</svg>"
)


@pytest.fixture
def siblings_path(tmp_path: Path) -> Path:
    path = tmp_path / "siblings.svg"
    path.write_text(SIBLINGS, encoding="utf-8")
    return path


@pytest.fixture
def bare_path(tmp_path: Path) -> Path:
    path = tmp_path / "bare.svg"
    path.write_text(BARE_HEX, encoding="utf-8")
    return path


class TestPortSatisfaction:
    def test_writer_satisfies_port(self) -> None:
        assert isinstance(FileTemplateWriter(), TemplateWriterPort)


class TestSetPlaceholder:
    def test_replace_one_of_three_sibling_shapes(self, siblings_path: Path) -> None:
        before = siblings_path.read_bytes()
        writer = FileTemplateWriter()
        result = writer.set_placeholder(
            TemplateSetPlaceholderRequest(path=siblings_path, shape_id=2, name="COLOR_COUNTOUR")
        )
        after = siblings_path.read_bytes()
        assert after != before
        # Exactly one shape's value changed: shape 2 -> COLOR_COUNTOUR.
        shapes = result.shapes
        assert [s.placeholder for s in shapes] == [
            "COLOR_FOREGROUND",
            "COLOR_COUNTOUR",
            "COLOR_FOREGROUND",
        ]
        # Byte diff is confined to shape 2's stroke value.
        expected = SIBLINGS.replace(
            '<path d="M2 2L3 3" stroke="{{COLOR_FOREGROUND}}"/>',
            '<path d="M2 2L3 3" stroke="{{COLOR_COUNTOUR}}"/>',
            1,
        )
        assert after.decode("utf-8") == expected
        # Everything else byte-identical.
        assert "#" not in after.decode("utf-8")

    def test_bare_hex_becomes_placeholder(self, bare_path: Path) -> None:
        writer = FileTemplateWriter()
        result = writer.set_placeholder(
            TemplateSetPlaceholderRequest(path=bare_path, shape_id=1, name="COLOR_FOREGROUND")
        )
        assert result.mode is TemplateMode.TEMPLATED
        assert result.shapes[0].placeholder == "COLOR_FOREGROUND"
        assert result.shapes[0].literal is None
        assert result.shapes[1].literal == "#ffffff"
        text = bare_path.read_text(encoding="utf-8")
        assert 'fill="{{COLOR_FOREGROUND}}"' in text
        assert 'fill="#ffffff"' in text

    def test_stroke_painted_shape(self, siblings_path: Path) -> None:
        writer = FileTemplateWriter()
        result = writer.set_placeholder(
            TemplateSetPlaceholderRequest(path=siblings_path, shape_id=1, name="COLOR_COUNTOUR")
        )
        assert result.shapes[0].paint_attr == "stroke"
        assert result.shapes[0].placeholder == "COLOR_COUNTOUR"
        assert 'stroke="{{COLOR_COUNTOUR}}"' in siblings_path.read_text(encoding="utf-8")

    def test_invalid_name_errors_without_write(self, siblings_path: Path) -> None:
        before = siblings_path.read_bytes()
        with pytest.raises(InvalidPlaceholderNameError):
            FileTemplateWriter().set_placeholder(
                TemplateSetPlaceholderRequest(path=siblings_path, shape_id=1, name="color contour")
            )
        assert siblings_path.read_bytes() == before

    def test_unknown_shape_errors_without_write(self, siblings_path: Path) -> None:
        before = siblings_path.read_bytes()
        with pytest.raises(UnknownTemplateShapeError):
            FileTemplateWriter().set_placeholder(
                TemplateSetPlaceholderRequest(path=siblings_path, shape_id=99, name="COLOR_TEST")
            )
        assert siblings_path.read_bytes() == before

    def test_inherited_paint_attr_errors_without_write(self, tmp_path: Path) -> None:
        # Shape paints via root-inherited fill, but carries no own attribute.
        path = tmp_path / "inherited.svg"
        path.write_text(
            '<svg width="24" height="24" fill="#c2c2c5">\n<path d="M0 0L1 1"/>\n</svg>',
            encoding="utf-8",
        )
        before = path.read_bytes()
        with pytest.raises(TemplatePaintAttributeError):
            FileTemplateWriter().set_placeholder(
                TemplateSetPlaceholderRequest(path=path, shape_id=1, name="COLOR_TEST")
            )
        assert path.read_bytes() == before

    def test_missing_file_raises_template_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(TemplateNotFoundError):
            FileTemplateWriter().analyze(tmp_path / "absent.svg")

    def test_atomic_write_content_complete_and_temp_cleaned(self, tmp_path: Path) -> None:
        path = tmp_path / "atomic.svg"
        path.write_text(BARE_HEX, encoding="utf-8")
        writer = FileTemplateWriter()
        writer.set_placeholder(
            TemplateSetPlaceholderRequest(path=path, shape_id=1, name="COLOR_FOREGROUND")
        )
        # Content is complete and well-formed after the write.
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<svg")
        assert text.endswith("</svg>")
        assert 'fill="{{COLOR_FOREGROUND}}"' in text
        # No leftover temp files in the parent directory.
        leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []

    def test_analyze_reports_mode(self, bare_path: Path) -> None:
        result = FileTemplateWriter().analyze(bare_path)
        assert result.mode is TemplateMode.BARE
        assert [s.literal for s in result.shapes] == ["#c2c2c5", "#ffffff"]


class TestExtractionParity:
    def test_service_and_writer_number_shapes_identically(self, siblings_path: Path) -> None:
        service = TemplateAnalysisService()
        pairs = service.extract_with_elements(siblings_path.read_text(encoding="utf-8"))
        shapes = [s.shape_id for s, _ in pairs]
        assert shapes == [1, 2, 3]
