from __future__ import annotations

from datetime import datetime
from pathlib import Path

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import (
    Color,
    ColorScheme,
    GenerationRequest,
    GenerationResult,
    GeneratorConfig,
)
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort

_now = datetime.now()


def _scheme(overrides: object = None) -> ColorScheme:
    return ColorScheme(
        background=Color("#000000", (0, 0, 0)),
        foreground=Color("#ffffff", (255, 255, 255)),
        cursor=Color("#00ff00", (0, 255, 0)),
        colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=_now,
    )


class TestPaletteGeneratorPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockGenerator:
            def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
                return _scheme(image_path)

            def is_available(self) -> bool:
                return True

        assert isinstance(MockGenerator(), PaletteGeneratorPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), PaletteGeneratorPort)

    def test_partial_implementation_missing_available_fails_isinstance(self) -> None:
        class MissingIsAvailable:
            def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
                return _scheme(image_path)

        assert not isinstance(MissingIsAvailable(), PaletteGeneratorPort)


class TestColorSchemeProcessorPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockProcessor:
            def process_generate(
                self, request: GenerationRequest, settings: object
            ) -> GenerationResult:
                return GenerationResult(
                    success=True,
                    color_scheme=None,
                    output_files=(),
                    backend=Backend.CUSTOM,
                    stderr="",
                    return_code=0,
                    duration=0.0,
                )

            def process_show(
                self, request: GenerationRequest, settings: object
            ) -> GenerationResult:
                return GenerationResult(
                    success=True,
                    color_scheme=None,
                    output_files=(),
                    backend=Backend.CUSTOM,
                    stderr="",
                    return_code=0,
                    duration=0.0,
                )

        assert isinstance(MockProcessor(), ColorSchemeProcessorPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), ColorSchemeProcessorPort)

    def test_partial_implementation_missing_show_fails_isinstance(self) -> None:
        class MissingProcessShow:
            def process_generate(
                self, request: GenerationRequest, settings: object
            ) -> GenerationResult:
                return GenerationResult(
                    success=True,
                    color_scheme=None,
                    output_files=(),
                    backend=Backend.CUSTOM,
                    stderr="",
                    return_code=0,
                    duration=0.0,
                )

        assert not isinstance(MissingProcessShow(), ColorSchemeProcessorPort)


class TestOutputPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockOutput:
            def process_result(self, result: GenerationResult) -> None:
                pass

            def error(self, exc: ColorSchemeError) -> None:
                pass

            def palette_display(self, scheme: ColorScheme) -> None:
                pass

        assert isinstance(MockOutput(), OutputPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), OutputPort)

    def test_partial_implementation_missing_palette_display_fails_isinstance(self) -> None:
        class MissingPaletteDisplay:
            def process_result(self, result: GenerationResult) -> None:
                pass

            def error(self, exc: ColorSchemeError) -> None:
                pass

        assert not isinstance(MissingPaletteDisplay(), OutputPort)
