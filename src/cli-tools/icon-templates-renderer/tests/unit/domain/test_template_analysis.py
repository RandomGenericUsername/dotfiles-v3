from __future__ import annotations

import pytest

from icon_templates_renderer.domain.enums import TemplateMode
from icon_templates_renderer.domain.exceptions import InvalidPlaceholderNameError
from icon_templates_renderer.domain.models import TemplateShape
from icon_templates_renderer.domain.services import (
    TemplateAnalysisService,
    validate_placeholder_name,
)

# Real power-menu SVG body: root fill="none", shapes paint via inherited stroke.
POWER_MENU_BODY = (
    '<svg width="800" height="800" viewBox="0 0 800 800" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">\n'
    '<path d="M400 66.668V200.001" stroke="{{COLOR_FOREGROUND}}" '
    'stroke-width="75" stroke-linecap="round"/>\n'
    '<path d="M283.333 123.535C175.602 169.052 100 275.7 100 400.003C100 476.84 '
    "128.885 546.93 176.39 600.007M516.667 123.535C624.397 169.052 700 275.7 700 "
    "400.003C700 565.69 565.687 700.003 400 700.003C364.937 700.003 331.278 693.99 "
    '300 682.934" stroke="{{COLOR_FOREGROUND}}" stroke-width="75" '
    'stroke-linecap="round"/>\n'
    "</svg>"
)


class TestTemplateAnalysisService:
    def test_battery_fill_shapes(self) -> None:
        body = (
            '<svg width="24" height="24">\n'
            '<path fill="{{COLOR_FOREGROUND}}" d="M0 0L1 1"/>\n'
            '<rect fill="#c2c2c5" x="0" y="0" width="4" height="4"/>\n'
            "</svg>"
        )
        shapes = TemplateAnalysisService().analyze(body)
        assert shapes == (
            TemplateShape(1, "path", "fill", "COLOR_FOREGROUND", None),
            TemplateShape(2, "rect", "fill", None, "#c2c2c5"),
        )

    def test_power_menu_root_inherited_stroke(self) -> None:
        shapes = TemplateAnalysisService().analyze(POWER_MENU_BODY)
        assert [s.placeholder for s in shapes] == ["COLOR_FOREGROUND", "COLOR_FOREGROUND"]
        assert all(s.paint_attr == "stroke" for s in shapes)
        assert [s.literal for s in shapes] == [None, None]
        assert [s.tag for s in shapes] == ["path", "path"]

    def test_hex_only_is_bare(self) -> None:
        body = (
            '<svg width="24" height="24">\n'
            '<path fill="#c2c2c5" d="M0 0L1 1"/>\n'
            '<rect fill="#ffffff" x="0" y="0" width="4" height="4"/>\n'
            "</svg>"
        )
        shapes = TemplateAnalysisService().analyze(body)
        assert all(s.placeholder is None for s in shapes)
        assert [s.literal for s in shapes] == ["#c2c2c5", "#ffffff"]

    def test_mixed_file_is_templated(self) -> None:
        body = (
            '<svg width="24" height="24">\n'
            '<path fill="{{COLOR_FOREGROUND}}" d="M0 0L1 1"/>\n'
            '<rect fill="#c2c2c5" x="0" y="0" width="4" height="4"/>\n'
            "</svg>"
        )
        shapes = TemplateAnalysisService().analyze(body)
        assert TemplateAnalysisService.classify(shapes) is TemplateMode.TEMPLATED

    def test_zero_shape_file_is_bare(self) -> None:
        shapes = TemplateAnalysisService().analyze('<svg width="24" height="24"></svg>')
        assert shapes == ()
        assert TemplateAnalysisService.classify(shapes) is TemplateMode.BARE

    def test_shape_ids_are_document_order_from_one(self) -> None:
        body = (
            '<svg width="24" height="24">\n'
            '<path d="M0 0L1 1" fill="#111111"/>\n'
            '<circle cx="4" cy="4" r="2" fill="#222222"/>\n'
            '<rect x="0" y="0" width="4" height="4" fill="#333333"/>\n'
            "</svg>"
        )
        shapes = TemplateAnalysisService().analyze(body)
        assert [s.shape_id for s in shapes] == [1, 2, 3]
        assert [s.tag for s in shapes] == ["path", "circle", "rect"]

    def test_literal_color_preserved(self) -> None:
        body = '<svg fill="none"><path stroke="#c2c2c5" d="M0 0L1 1"/></svg>'
        shapes = TemplateAnalysisService().analyze(body)
        assert shapes == (TemplateShape(1, "path", "stroke", None, "#c2c2c5"),)


class TestValidatePlaceholderName:
    def test_valid_names(self) -> None:
        for name in ("COLOR_FOREGROUND", "COLOR_COUNTOUR", "A", "COLOR_1", "X_Y_Z"):
            validate_placeholder_name(name)

    def test_invalid_names(self) -> None:
        for name in ("color contour", "1COLOR", "color", "COLOR-NAME", "COLOR NAME", ""):
            with pytest.raises(InvalidPlaceholderNameError):
                validate_placeholder_name(name)
