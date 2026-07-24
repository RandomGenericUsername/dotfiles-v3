from __future__ import annotations

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
from color_scheme_generator.domain.enums import Verbosity
from color_scheme_generator.domain.models import ColorScheme, GenerationResult


class PlainOutput:
    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL) -> None:
        self._verbosity = verbosity

    def process_result(self, result: GenerationResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        print("Success")
        print(f"Backend: {result.backend.value}")
        print(f"Duration: {result.duration:.2f}s")
        if result.output_files:
            print("Output files:")
            for path in result.output_files:
                print(f"  {path}")
        print()

    def error(self, exc: ColorSchemeError) -> None:
        error_type = type(exc).__name__
        print(f"Error: {error_type}")
        print(f"Message: {exc}")

        details = self._format_error_details(exc)
        for key, value in details.items():
            print(f"{key}: {value}")
        print()

    def config_info(
        self,
        settings: object,
        backends: dict,
        sources: list[str],
        catalog: object,
    ) -> None:
        if settings:
            for section, fields in settings.__dataclass_fields__.items():
                section_val = getattr(settings, section)
                if hasattr(section_val, "__dataclass_fields__"):
                    for field in section_val.__dataclass_fields__:
                        val = getattr(section_val, field)
                        print(f"{section}.{field}: {val}")
        print()
        if sources:
            print("Sources:")
            for s in sources:
                print(f"  {s}")
        print()
        print("Backends:")
        for name, info in backends.items():
            avail = "available" if info.get("available") else "not available"
            desc = info.get("description", "")
            print(f"  {name}: {avail}")
            if desc:
                print(f"    description: {desc}")

    def palette_display(self, scheme: ColorScheme) -> None:
        print(f"Background: {scheme.background.hex}")
        print(f"Foreground: {scheme.foreground.hex}")
        print(f"Cursor: {scheme.cursor.hex}")
        hex_values = " ".join(c.hex for c in scheme.colors)
        print(f"Colors: {hex_values}")
        print()

    def _format_error_details(self, exc: ColorSchemeError) -> dict[str, str]:
        details: dict[str, str] = {}

        if isinstance(exc, InvalidImageError):
            details["Image path"] = str(exc.image_path)
            details["Reason"] = exc.reason
        elif isinstance(exc, ColorExtractionError):
            details["Backend"] = exc.backend.value
            details["Stderr"] = exc.stderr
        elif isinstance(exc, BackendNotAvailableError):
            details["Backend"] = exc.backend.value
            details["Hint"] = exc.hint
        elif isinstance(exc, OutputWriteError):
            details["Path"] = str(exc.path)
            details["Reason"] = exc.reason
        elif isinstance(exc, ConfigResolutionError):
            details["Key"] = exc.key
            details["Reason"] = exc.reason
        elif isinstance(exc, PaletteGenerationError):
            if exc.backend is not None:
                details["Backend"] = exc.backend.value
        elif isinstance(exc, TemplateNotFoundError):
            details["Template"] = exc.template_name
            details["Searched"] = ", ".join(str(p) for p in exc.searched_paths)
        elif isinstance(exc, TemplateRenderError):
            details["Template"] = exc.template_name
            details["Reason"] = exc.reason

        return details
