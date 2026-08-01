from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
    ColorSchemeError,
    ConfigResolutionError,
    InvalidImageError,
    OutputWriteError,
    PaletteGenerationError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from color_scheme_generator.domain.models import Color, ColorScheme, GenerationResult


class TestPlainOutput:
    def _make_color_scheme(self) -> ColorScheme:
        black = Color("#000000", (0, 0, 0))
        white = Color("#ffffff", (255, 255, 255))
        red = Color("#ff0000", (255, 0, 0))
        colors = tuple(
            Color(f"#{i * 17:02x}{i * 17:02x}{i * 17:02x}", (i * 17, i * 17, i * 17))
            for i in range(16)
        )
        return ColorScheme(
            background=black,
            foreground=white,
            cursor=red,
            colors=colors,
            source_image=Path("/test/wallpaper.jpg"),
            backend=Backend.CUSTOM,
            generated_at=datetime(2026, 7, 15, 12, 0, 0),
        )

    def _make_result(self, scheme: ColorScheme | None = None) -> GenerationResult:
        if scheme is None:
            scheme = self._make_color_scheme()
        return GenerationResult(
            success=True,
            color_scheme=scheme,
            output_files=(Path("/out/colors.json"), Path("/out/scheme.json")),
            backend=Backend.CUSTOM,
            stderr="",
            return_code=0,
            duration=1.5,
        )

    def test_process_result_outputs_plain_text(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        output = PlainOutput()
        result = self._make_result()
        output.process_result(result)
        captured = capsys.readouterr().out

        assert "Success" in captured
        assert "Backend: custom" in captured
        assert "Duration: 1.50s" in captured
        assert "/out/colors.json" in captured

    def test_error_outputs_plain_text_error(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        exc = InvalidImageError(image_path=Path("/bad.jpg"), reason="corrupt header")
        output = PlainOutput()
        output.error(exc)
        captured = capsys.readouterr().err

        assert "error: InvalidImageError" in captured
        assert "corrupt header" in captured
        assert "image_path: /bad.jpg" in captured
        assert "reason: corrupt header" in captured

    def test_palette_display_outputs_hex_values(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        scheme = self._make_color_scheme()
        output = PlainOutput()
        output.palette_display(scheme)
        captured = capsys.readouterr().out

        assert "Background: #000000" in captured
        assert "Foreground: #ffffff" in captured
        assert "Cursor: #ff0000" in captured
        assert "Colors: " in captured

    def test_no_color_codes_in_output(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        output = PlainOutput()
        result = self._make_result()
        output.process_result(result)

        scheme = self._make_color_scheme()
        output.palette_display(scheme)

        exc = InvalidImageError(Path("/bad.jpg"), "corrupt")
        output.error(exc)

        captured = capsys.readouterr().out

        assert "\x1b[" not in captured
        assert "\033[" not in captured

    def test_structural_subtyping(self):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput
        from color_scheme_generator.ports.output import OutputPort

        assert isinstance(PlainOutput(), OutputPort)

    def test_config_info_renders_settings_sources_templates_backends(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput
        from color_scheme_generator.domain.enums import ColorFormat, RuntimeMode
        from color_scheme_generator.domain.models import (
            AppSettings,
            ColorSchemeTemplate,
            ContainerSettings,
            GenerationSettings,
            OutputSettings,
            RuntimeSettings,
            TemplateCatalog,
        )

        settings = AppSettings(
            output=OutputSettings(
                directory=Path("/tmp/csg-out"),
                default_formats=(ColorFormat.JSON,),
                overwrite=True,
            ),
            generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
            runtime=RuntimeSettings(mode=RuntimeMode.LOCAL),
            container=ContainerSettings(engine="docker"),
        )
        backends = {"custom": {"available": True, "description": "Custom extractor"}}
        sources = ["/cfg/settings.toml"]
        templates = TemplateCatalog(
            templates=(ColorSchemeTemplate(name="colors.json", format=ColorFormat.JSON),)
        )

        output = PlainOutput()
        output.config_info(settings, backends, sources, templates)
        captured = capsys.readouterr().out

        assert "output.directory: /tmp/csg-out" in captured
        assert "output.overwrite: True" in captured
        assert "generation.backend: Backend.CUSTOM" in captured
        assert "runtime.mode: RuntimeMode.LOCAL" in captured
        assert "Sources:" in captured
        assert "/cfg/settings.toml" in captured
        assert "Templates:" in captured
        assert "count: 1" in captured
        assert "formats: json" in captured
        assert "Backends:" in captured
        assert "custom: available" in captured
        assert "description: Custom extractor" in captured

    def test_config_info_without_settings_or_templates(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        output = PlainOutput()
        output.config_info(None, {"custom": {"available": False}}, [], None)
        captured = capsys.readouterr().out

        assert "Sources:" not in captured
        assert "count: 0" in captured
        assert "custom: not available" in captured

    def test_plain_output_never_raises(self):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        output = PlainOutput()

        errors: list[ColorSchemeError] = [
            InvalidImageError(Path("/x.jpg"), "bad"),
            ColorExtractionError(Backend.CUSTOM, "fail"),
            BackendNotAvailableError(Backend.CUSTOM, "install it"),
            OutputWriteError(Path("/x"), "denied"),
            ConfigResolutionError("key", "not found"),
            PaletteGenerationError("fail", Backend.CUSTOM),
            PaletteGenerationError("fail"),
            TemplateNotFoundError("test.j2", (Path("/templates"),)),
            TemplateRenderError("test.j2", "syntax error"),
        ]

        for exc in errors:
            try:
                output.error(exc)
            except Exception:
                pytest.fail(f"error() raised for {type(exc).__name__}")

    def test_plain_output_format_matches_expected_pattern(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        output = PlainOutput()
        result = self._make_result()
        output.process_result(result)
        captured = capsys.readouterr().out

        lines = [line for line in captured.split("\n") if line.strip()]
        assert lines[0] == "Success"
        assert lines[1] == "Backend: custom"
        assert lines[2] == "Duration: 1.50s"

    def test_error_handles_unexpected_exception_type(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        class UnexpectedError(ColorSchemeError):
            def __init__(self) -> None:
                super().__init__()

        output = PlainOutput()
        output.error(UnexpectedError())
        captured = capsys.readouterr().err

        assert "error: UnexpectedError" in captured

    def test_error_with_color_extraction_error(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        exc = ColorExtractionError(
            backend=Backend.PYWAL,
            message="failed to extract",
            stderr="kmeans error",
        )
        output = PlainOutput()
        output.error(exc)
        captured = capsys.readouterr().err

        assert "error: ColorExtractionError" in captured
        assert "stderr: kmeans error" in captured

    def test_error_with_backend_not_available_error(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        exc = BackendNotAvailableError(
            backend=Backend.WALLUST,
            hint="install wallust",
        )
        output = PlainOutput()
        output.error(exc)
        captured = capsys.readouterr().err

        assert "error: BackendNotAvailableError" in captured
        assert "hint: install wallust" in captured

    def test_error_with_output_write_error(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        exc = OutputWriteError(path=Path("/out/file.json"), reason="permission denied")
        output = PlainOutput()
        output.error(exc)
        captured = capsys.readouterr().err

        assert "error: OutputWriteError" in captured
        assert "path: /out/file.json" in captured
        assert "reason: permission denied" in captured

    def test_error_with_palette_generation_error(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        exc = PaletteGenerationError(message="oom", backend=Backend.CUSTOM)
        output = PlainOutput()
        output.error(exc)
        captured = capsys.readouterr().err

        assert "error: PaletteGenerationError" in captured

    def test_palette_display_hex_only_no_ansi(self, capsys):
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        scheme = self._make_color_scheme()
        output = PlainOutput()
        output.palette_display(scheme)
        captured = capsys.readouterr().out

        assert "\x1b" not in captured
        for c in scheme.colors:
            assert c.hex in captured
