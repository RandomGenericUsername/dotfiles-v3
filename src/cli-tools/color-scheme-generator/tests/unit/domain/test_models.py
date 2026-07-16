from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.models import Color, ColorScheme, GenerationRequest, GenerationResult, GeneratorConfig


class TestColor:
    def test_valid_hex_case_preserved(self) -> None:
        c = Color("#FF0000", (255, 0, 0))
        assert c.hex == "#FF0000"

    def test_missing_hash_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("ff0000", (255, 0, 0))

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("#ff00", (255, 0, 0))

    def test_invalid_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("#GG0000", (255, 0, 0))

    def test_lowercase_hex_preserved(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        assert c.hex == "#ff0000"

    def test_rgb_clamped_above(self) -> None:
        c = Color("#ff0000", (300, 0, 0))
        assert c.rgb == (255, 0, 0)

    def test_rgb_clamped_below(self) -> None:
        c = Color("#ff0000", (-10, 0, 0))
        assert c.rgb == (0, 0, 0)

    def test_adjust_saturation_reduces(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        result = c.adjust_saturation(0.5)
        assert isinstance(result, Color)
        assert result.rgb != c.rgb
        assert result.hex != c.hex
        assert result.hex == f"#{result.rgb[0]:02x}{result.rgb[1]:02x}{result.rgb[2]:02x}"

    def test_adjust_saturation_immutable(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        original_rgb = c.rgb
        c.adjust_saturation(0.5)
        assert c.rgb == original_rgb

    def test_rgb_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="rgb must be a 3-tuple"):
            Color("#ff0000", (255, 0, 0, 0))
        with pytest.raises(ValueError, match="rgb must be a 3-tuple"):
            Color("#ff0000", (255, 0))

    def test_rgb_clamped_recomputes_hex(self) -> None:
        c = Color("#00ff00", (300, 0, 0))
        assert c.rgb == (255, 0, 0)
        assert c.hex == "#ff0000"

    def test_float_rgb_coerced_to_int(self) -> None:
        c = Color("#ff0000", (127.5, 0, 0))
        assert isinstance(c.rgb[0], int)

    def test_trailing_newline_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("#ff0000\n", (255, 0, 0))


class TestColorScheme:
    def test_fields(self) -> None:
        bg = Color("#000000", (0, 0, 0))
        fg = Color("#ffffff", (255, 255, 255))
        cursor = Color("#00ff00", (0, 255, 0))
        colors = tuple(Color("#000000", (0, 0, 0)) for _ in range(16))
        scheme = ColorScheme(
            background=bg,
            foreground=fg,
            cursor=cursor,
            colors=colors,
            source_image=Path("/tmp/wallpaper.png"),
            backend=Backend.CUSTOM,
            generated_at=datetime(2024, 1, 1),
        )
        assert scheme.background == bg
        assert scheme.foreground == fg
        assert scheme.cursor == cursor
        assert len(scheme.colors) == 16
        assert scheme.source_image == Path("/tmp/wallpaper.png")
        assert scheme.backend == Backend.CUSTOM
        assert scheme.generated_at == datetime(2024, 1, 1)

    def test_wrong_color_count_raises(self) -> None:
        bg = Color("#000000", (0, 0, 0))
        fg = Color("#ffffff", (255, 255, 255))
        cursor = Color("#00ff00", (0, 255, 0))
        with pytest.raises(ValueError, match="exactly 16 colors"):
            ColorScheme(
                background=bg,
                foreground=fg,
                cursor=cursor,
                colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(15)),
                source_image=Path("/tmp/wallpaper.png"),
                backend=Backend.CUSTOM,
                generated_at=datetime(2024, 1, 1),
            )


class TestGeneratorConfig:
    def test_fields(self) -> None:
        config = GeneratorConfig(
            backend=Backend.PYWAL,
            params={},
            formats=(ColorFormat.JSON,),
            output_dir=Path("/tmp/output"),
        )
        assert config.backend == Backend.PYWAL
        assert config.params == {}
        assert config.formats == (ColorFormat.JSON,)
        assert config.output_dir == Path("/tmp/output")


class TestGenerationRequest:
    def test_fields(self) -> None:
        config = GeneratorConfig(
            backend=Backend.PYWAL,
            params={},
            formats=(ColorFormat.JSON,),
            output_dir=Path("/tmp/output"),
        )
        req = GenerationRequest(
            image_path=Path("/tmp/wallpaper.png"),
            config=config,
        )
        assert req.image_path == Path("/tmp/wallpaper.png")
        assert req.config == config


class TestGenerationResult:
    def test_fields(self) -> None:
        bg = Color("#000000", (0, 0, 0))
        scheme = ColorScheme(
            background=bg,
            foreground=Color("#ffffff", (255, 255, 255)),
            cursor=Color("#00ff00", (0, 255, 0)),
            colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
            source_image=Path("/tmp/wallpaper.png"),
            backend=Backend.CUSTOM,
            generated_at=datetime(2024, 1, 1),
        )
        result = GenerationResult(
            success=True,
            color_scheme=scheme,
            output_files=(Path("/tmp/output/colors.json"),),
            backend=Backend.CUSTOM,
            stderr="",
            return_code=0,
            duration=0.5,
        )
        assert result.success is True
        assert result.color_scheme == scheme
        assert result.output_files == (Path("/tmp/output/colors.json"),)
        assert result.backend == Backend.CUSTOM
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.duration == 0.5
