from __future__ import annotations

import json
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
)
from color_scheme_generator.domain.models import Color, ColorScheme, GenerationResult


class TestJsonOutput:
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

    def test_process_result_outputs_correct_json(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        output = JsonOutput()
        result = self._make_result()
        output.process_result(result)
        captured = capsys.readouterr().out
        data = json.loads(captured)

        assert data["success"] is True
        assert data["backend"] == "custom"
        assert data["duration"] == 1.5
        assert data["output_files"] == ["/out/colors.json", "/out/scheme.json"]

        cs = data["color_scheme"]
        assert cs["background"] == {"hex": "#000000", "rgb": [0, 0, 0]}
        assert cs["foreground"] == {"hex": "#ffffff", "rgb": [255, 255, 255]}
        assert cs["cursor"] == {"hex": "#ff0000", "rgb": [255, 0, 0]}
        assert len(cs["colors"]) == 16
        assert cs["colors"][0] == {"hex": "#000000", "rgb": [0, 0, 0]}
        assert cs["source_image"] == "/test/wallpaper.jpg"
        assert cs["backend"] == "custom"
        assert cs["generated_at"] == "2026-07-15T12:00:00"

    def test_process_result_datetime_iso8601(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        scheme = self._make_color_scheme()
        output = JsonOutput()
        output.process_result(self._make_result(scheme))
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["color_scheme"]["generated_at"] == "2026-07-15T12:00:00"

    def test_process_result_path_objects_serialize_as_strings(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        result = self._make_result()
        output = JsonOutput()
        output.process_result(result)
        captured = capsys.readouterr().out
        data = json.loads(captured)
        for path in data["output_files"]:
            assert isinstance(path, str)

    def test_error_with_invalid_image_error(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = InvalidImageError(image_path=Path("/bad.jpg"), reason="corrupt header")
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "InvalidImageError"
        assert data["message"] == "Invalid image /bad.jpg: corrupt header"
        assert data["details"]["image_path"] == "/bad.jpg"
        assert data["details"]["reason"] == "corrupt header"

    def test_error_with_color_extraction_error(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = ColorExtractionError(
            backend=Backend.PYWAL,
            message="failed to extract",
            stderr="kmeans error",
        )
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "ColorExtractionError"
        assert data["details"]["backend"] == "pywal"
        assert data["details"]["stderr"] == "kmeans error"

    def test_error_with_backend_not_available_error(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = BackendNotAvailableError(
            backend=Backend.WALLUST,
            hint="install wallust",
        )
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "BackendNotAvailableError"
        assert data["details"]["backend"] == "wallust"
        assert data["details"]["hint"] == "install wallust"

    def test_error_with_output_write_error(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = OutputWriteError(path=Path("/out/file.json"), reason="permission denied")
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "OutputWriteError"
        assert data["details"]["path"] == "/out/file.json"
        assert data["details"]["reason"] == "permission denied"

    def test_error_with_config_resolution_error(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = ConfigResolutionError(key="backend", reason="not found")
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "ConfigResolutionError"
        assert data["details"]["key"] == "backend"
        assert data["details"]["reason"] == "not found"

    def test_error_with_palette_generation_error(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = PaletteGenerationError(message="oom", backend=Backend.CUSTOM)
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "PaletteGenerationError"
        assert data["details"]["backend"] == "custom"

    def test_error_with_palette_generation_error_no_backend(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        exc = PaletteGenerationError(message="unknown failure")
        output = JsonOutput()
        output.error(exc)
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "PaletteGenerationError"
        assert "details" not in data

    def test_palette_display_outputs_color_scheme_as_json(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        scheme = self._make_color_scheme()
        output = JsonOutput()
        output.palette_display(scheme)
        captured = capsys.readouterr().out
        data = json.loads(captured)

        assert data["background"] == {"hex": "#000000", "rgb": [0, 0, 0]}
        assert len(data["colors"]) == 16
        assert data["source_image"] == "/test/wallpaper.jpg"
        assert data["backend"] == "custom"
        assert data["generated_at"] == "2026-07-15T12:00:00"

    def test_structural_subtyping(self):
        from color_scheme_generator.adapters.output.json_output import JsonOutput
        from color_scheme_generator.ports.output import OutputPort

        assert isinstance(JsonOutput(), OutputPort)

    def test_config_info_outputs_json(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput
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

        output = JsonOutput()
        output.config_info(settings, backends, sources, templates)
        captured = capsys.readouterr().out
        data = json.loads(captured)

        assert data["sources"] == ["/cfg/settings.toml"]
        assert data["settings"]["output"]["directory"] == "/tmp/csg-out"
        assert data["settings"]["generation"]["backend"] == "custom"
        assert data["settings"]["runtime"]["mode"] == "local"
        assert data["backends"]["custom"]["available"] is True
        assert data["templates"]["templates_count"] == 1
        assert data["templates"]["formats"] == ["json"]

    def test_config_info_without_templates_lists_zero(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput
        from color_scheme_generator.domain.enums import RuntimeMode
        from color_scheme_generator.domain.models import (
            AppSettings,
            ContainerSettings,
            GenerationSettings,
            OutputSettings,
            RuntimeSettings,
        )

        settings = AppSettings(
            output=OutputSettings(directory=Path("/tmp/out"), default_formats=(), overwrite=False),
            generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
            runtime=RuntimeSettings(mode=RuntimeMode.LOCAL),
            container=ContainerSettings(engine="docker"),
        )

        output = JsonOutput()
        output.config_info(settings, {}, [], None)
        captured = capsys.readouterr().out
        data = json.loads(captured)

        assert data["sources"] == []
        assert data["backends"] == {}
        assert data["templates"] == {"templates_count": 0, "formats": []}

    def test_all_error_outputs_have_kind(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        output = JsonOutput()

        errors: list[ColorSchemeError] = [
            InvalidImageError(Path("/x.jpg"), "bad"),
            ColorExtractionError(Backend.CUSTOM, "fail"),
            BackendNotAvailableError(Backend.CUSTOM, "install it"),
            OutputWriteError(Path("/x"), "denied"),
            ConfigResolutionError("key", "not found"),
            PaletteGenerationError("fail", Backend.CUSTOM),
            PaletteGenerationError("fail"),
        ]

        for exc in errors:
            output.error(exc)
            captured = capsys.readouterr().err
            data = json.loads(captured)
            assert data["kind"] == type(exc).__name__, f"failed for {type(exc).__name__}"

    def test_error_handles_unexpected_exception_type(self, capsys):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        class UnexpectedError(ColorSchemeError):
            def __init__(self) -> None:
                self.custom_attr = "something"
                super().__init__()

        output = JsonOutput()
        output.error(UnexpectedError())
        captured = capsys.readouterr().err
        data = json.loads(captured)

        assert data["kind"] == "UnexpectedError"

    def test_error_serialization_never_raises(self):
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        output = JsonOutput()

        errors: list[ColorSchemeError] = [
            InvalidImageError(Path("/x.jpg"), "bad"),
            ColorExtractionError(Backend.CUSTOM, "fail"),
            BackendNotAvailableError(Backend.CUSTOM, "install it"),
            OutputWriteError(Path("/x"), "denied"),
            ConfigResolutionError("key", "not found"),
            PaletteGenerationError("fail", Backend.CUSTOM),
        ]

        for exc in errors:
            try:
                output.error(exc)
            except Exception:
                pytest.fail(f"error() raised for {type(exc).__name__}")
