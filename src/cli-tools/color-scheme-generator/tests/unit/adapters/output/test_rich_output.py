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


class TestRichOutput:
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

    def test_process_result_renders_rich_success(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        output = RichOutput()
        result = self._make_result()
        output.process_result(result)
        captured = capsys.readouterr().out

        assert "Success" in captured
        assert "custom" in captured
        assert "1.50s" in captured
        assert "/out/colors.json" in captured

    def test_error_formats_rich_error_message(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = InvalidImageError(image_path=Path("/bad.jpg"), reason="corrupt header")
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "Error" in captured
        assert "InvalidImageError" in captured
        assert "corrupt header" in captured

    def test_palette_display_renders_color_swatches(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        scheme = self._make_color_scheme()
        output = RichOutput()
        output.palette_display(scheme)
        captured = capsys.readouterr().out

        assert "Palette Display" in captured
        assert "Foreground" in captured
        assert "Cursor" in captured
        assert "#ffffff" in captured
        assert "#ff0000" in captured

    def test_structural_subtyping(self):
        from color_scheme_generator.adapters.output.rich_output import RichOutput
        from color_scheme_generator.ports.output import OutputPort

        assert isinstance(RichOutput(), OutputPort)

    def test_config_info_renders_settings_sources_templates_backends(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput
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
                overwrite=False,
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

        output = RichOutput()
        output.config_info(settings, backends, sources, templates)
        captured = capsys.readouterr().out

        assert "Configuration" in captured
        assert "output.directory" in captured
        assert "/tmp/csg-out" in captured
        assert "Sources" in captured
        assert "/cfg/settings.toml" in captured
        assert "Templates" in captured
        assert "json" in captured
        assert "Backends" in captured
        assert "custom" in captured
        assert "yes" in captured

    def test_config_info_without_settings_or_templates(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        output = RichOutput()
        output.config_info(None, {"custom": {"available": False}}, [], None)
        captured = capsys.readouterr().out

        assert "(none)" in captured
        assert "custom" in captured
        assert "no" in captured

    def test_process_result_with_none_color_scheme(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        output = RichOutput()
        result = self._make_result(scheme=None)
        output.process_result(result)
        captured = capsys.readouterr().out

        assert "Success" in captured
        assert "custom" in captured

    def test_all_output_goes_to_stdout(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        output = RichOutput()
        result = self._make_result()
        output.process_result(result)

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_rich_output_never_raises(self):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        output = RichOutput()

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

    def test_error_handles_unexpected_exception_type(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        class UnexpectedError(ColorSchemeError):
            def __init__(self) -> None:
                super().__init__()

        output = RichOutput()
        output.error(UnexpectedError())
        captured = capsys.readouterr().out

        assert "UnexpectedError" in captured

    def test_error_with_color_extraction_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = ColorExtractionError(
            backend=Backend.PYWAL,
            message="failed to extract",
            stderr="kmeans error",
        )
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "ColorExtractionError" in captured
        assert "kmeans error" in captured

    def test_error_with_backend_not_available_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = BackendNotAvailableError(
            backend=Backend.WALLUST,
            hint="install wallust",
        )
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "BackendNotAvailableError" in captured
        assert "install wallust" in captured

    def test_error_with_output_write_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = OutputWriteError(path=Path("/out/file.json"), reason="permission denied")
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "OutputWriteError" in captured
        assert "permission denied" in captured

    def test_error_with_config_resolution_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = ConfigResolutionError(key="backend", reason="not found")
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "ConfigResolutionError" in captured

    def test_error_with_palette_generation_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = PaletteGenerationError(message="oom", backend=Backend.CUSTOM)
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "PaletteGenerationError" in captured

    def test_error_with_template_not_found_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = TemplateNotFoundError("colors.j2", (Path("/templates"),))
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "TemplateNotFoundError" in captured

    def test_error_with_template_render_error(self, capsys):
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        exc = TemplateRenderError("colors.j2", "syntax error")
        output = RichOutput()
        output.error(exc)
        captured = capsys.readouterr().out

        assert "TemplateRenderError" in captured
