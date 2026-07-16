from __future__ import annotations

from color_scheme_generator.domain.models import Color
from color_scheme_generator.domain.services import ColorAdjustmentService, HexValidationService, PaletteNormalizationService


class TestHexValidationService:
    def test_canonicalize_preserves_case(self) -> None:
        assert HexValidationService.canonicalize("#FF0000") == "#FF0000"
        assert HexValidationService.canonicalize("#ff0000") == "#ff0000"

    def test_validate_wrong_length(self) -> None:
        assert HexValidationService.validate("#abc") is False

    def test_validate_missing_hash(self) -> None:
        assert HexValidationService.validate("ff0000") is False

    def test_validate_invalid_chars(self) -> None:
        assert HexValidationService.validate("#GG0000") is False

    def test_validate_valid(self) -> None:
        assert HexValidationService.validate("#ff0000") is True
        assert HexValidationService.validate("#FF0000") is True
        assert HexValidationService.validate("#aBcDeF") is True


class TestColorAdjustmentService:
    def test_adjust_saturation_pure(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        result = ColorAdjustmentService.adjust_saturation(c, 0.5)
        assert isinstance(result, Color)
        assert result is not c

    def test_original_unmodified(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        original_rgb = c.rgb
        ColorAdjustmentService.adjust_saturation(c, 0.5)
        assert c.rgb == original_rgb

    def test_factor_one_returns_same(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        result = ColorAdjustmentService.adjust_saturation(c, 1.0)
        assert result.rgb == c.rgb


class TestPaletteNormalizationService:
    def test_pad_when_fewer_than_16(self) -> None:
        colors = [Color("#ff0000", (255, 0, 0)), Color("#00ff00", (0, 255, 0))]
        result = PaletteNormalizationService.normalize(colors)
        assert len(result) == 16
        assert result[0] == colors[0]
        assert result[1] == colors[1]
        for i in range(2, 16):
            assert result[i] == colors[-1]

    def test_truncate_when_more_than_16(self) -> None:
        colors = [Color("#000000", (i * 16, 0, 0)) for i in range(20)]
        result = PaletteNormalizationService.normalize(colors)
        assert len(result) == 16
        assert list(result) == colors[:16]

    def test_passthrough_when_exactly_16(self) -> None:
        colors = [Color("#000000", (i * 16, 0, 0)) for i in range(16)]
        result = PaletteNormalizationService.normalize(colors)
        assert len(result) == 16
        assert list(result) == colors

    def test_sort_by_brightness(self) -> None:
        colors = [
            Color("#000000", (100, 100, 100)),
            Color("#000000", (10, 10, 10)),
            Color("#000000", (200, 200, 200)),
        ]
        result = PaletteNormalizationService.sort_by_brightness(colors)
        assert result == [colors[1], colors[0], colors[2]]

    def test_sort_by_brightness_ascending(self) -> None:
        colors = [
            Color("#000000", (50, 50, 50)),
            Color("#000000", (0, 0, 0)),
            Color("#000000", (255, 255, 255)),
        ]
        result = PaletteNormalizationService.sort_by_brightness(colors)
        brightnesses = [sum(c.rgb) for c in result]
        assert brightnesses == sorted(brightnesses)
