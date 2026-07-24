from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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


class RichOutput:
    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL) -> None:
        self._verbosity = verbosity
        self._console = Console()

    def process_result(self, result: GenerationResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._console.print()
        self._console.print(
            Text("Success", style="bold green"),
        )
        self._console.print()

        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Backend", result.backend.value)
        table.add_row("Duration", f"{result.duration:.2f}s")

        if result.color_scheme:
            table.add_row("Background", result.color_scheme.background.hex)
            table.add_row("Foreground", result.color_scheme.foreground.hex)
            table.add_row("Cursor", result.color_scheme.cursor.hex)

        self._console.print(table)
        self._console.print()

        if result.output_files:
            self._console.print(Text("Output files:", style="bold"))
            for path in result.output_files:
                self._console.print(f"  {path}")

        self._console.print()

    def error(self, exc: ColorSchemeError) -> None:
        error_type = type(exc).__name__

        details = self._format_error_details(exc)

        panel = Panel(
            Text(str(exc), style="red"),
            title=Text(f"Error: {error_type}", style="bold red"),
            border_style="red",
        )
        self._console.print()
        self._console.print(panel)
        if details:
            self._console.print()
            for key, value in details.items():
                self._console.print(f"  {key}: {value}")
        self._console.print()

    def palette_display(self, scheme: ColorScheme) -> None:
        self._console.print()
        self._console.print(
            f"[on #{scheme.background.hex[1:]}]{' ' * 20}[/] Background: {scheme.background.hex}"
        )
        self._console.print(
            f"[on #{scheme.foreground.hex[1:]}]{' ' * 20}[/] Foreground: {scheme.foreground.hex}"
        )
        self._console.print(
            f"[on #{scheme.cursor.hex[1:]}]{' ' * 20}[/] Cursor: {scheme.cursor.hex}"
        )
        self._console.print()

        for i in range(0, len(scheme.colors), 8):
            row_colors = scheme.colors[i : i + 8]
            line = "".join(
                f"[on #{c.hex[1:]}]{' ' * 10}[/] " for c in row_colors
            )
            self._console.print(line)
            labels = "  ".join(f"{c.hex:<12}" for c in row_colors)
            self._console.print(labels)
            self._console.print()

        self._console.print()

    def print_table(self, table: Table) -> None:
        self._console.print()
        self._console.print(table)
        self._console.print()

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
