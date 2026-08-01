from __future__ import annotations

from rich.console import Console

from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer
from cli_output.domain.enums import OutputFormat
from cli_output.ports.renderer import Renderer


def create_renderer(fmt: OutputFormat, console: Console | None = None) -> Renderer:
    if fmt is OutputFormat.JSON:
        return JsonRenderer()
    if fmt is OutputFormat.PLAIN:
        return PlainRenderer()
    if fmt is OutputFormat.RICH:
        return RichRenderer(console or Console())
    raise ValueError(f"Unsupported output format: {fmt}")
