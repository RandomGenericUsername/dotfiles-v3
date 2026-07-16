from __future__ import annotations

from pathlib import Path

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


class TestColorSchemeError:
    def test_is_base_exception(self) -> None:
        assert issubclass(ColorSchemeError, Exception)


class TestInvalidImageError:
    def test_fields_and_message(self) -> None:
        err = InvalidImageError(image_path=Path("/nonexistent.jpg"), reason="File not found")
        assert err.image_path == Path("/nonexistent.jpg")
        assert err.reason == "File not found"
        assert str(err) == "Invalid image /nonexistent.jpg: File not found"
        assert isinstance(err, ColorSchemeError)


class TestColorExtractionError:
    def test_fields_and_message(self) -> None:
        err = ColorExtractionError(backend=Backend.PYWAL, message="wal exited with code 1")
        assert err.backend == Backend.PYWAL
        assert err.message == "wal exited with code 1"
        assert err.stderr == ""
        assert str(err) == "Color extraction failed for pywal: wal exited with code 1"
        assert isinstance(err, ColorSchemeError)

    def test_with_stderr(self) -> None:
        err = ColorExtractionError(backend=Backend.PYWAL, message="wal exited with code 1", stderr="error output")
        assert err.stderr == "error output"


class TestBackendNotAvailableError:
    def test_fields_and_message(self) -> None:
        err = BackendNotAvailableError(backend=Backend.CUSTOM, hint="pip install color-scheme-generator[custom]")
        assert err.backend == Backend.CUSTOM
        assert err.hint == "pip install color-scheme-generator[custom]"
        assert str(err) == "Backend custom is not available. Hint: pip install color-scheme-generator[custom]"
        assert isinstance(err, ColorSchemeError)


class TestOutputWriteError:
    def test_fields_and_isinstance(self) -> None:
        err = OutputWriteError(path=Path("/tmp/output.txt"), reason="Permission denied")
        assert err.path == Path("/tmp/output.txt")
        assert err.reason == "Permission denied"
        assert isinstance(err, ColorSchemeError)


class TestConfigResolutionError:
    def test_fields_and_isinstance(self) -> None:
        err = ConfigResolutionError(key="backend", reason="Unknown backend")
        assert err.key == "backend"
        assert err.reason == "Unknown backend"
        assert isinstance(err, ColorSchemeError)


class TestPaletteGenerationError:
    def test_fields_and_isinstance(self) -> None:
        err = PaletteGenerationError(message="Generation failed")
        assert err.message == "Generation failed"
        assert err.backend is None
        assert isinstance(err, ColorSchemeError)

    def test_with_backend(self) -> None:
        err = PaletteGenerationError(message="Generation failed", backend=Backend.PYWAL)
        assert err.backend == Backend.PYWAL
        assert str(err) == "[pywal] Palette generation failed: Generation failed"
