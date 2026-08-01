from __future__ import annotations

from cli_output.domain.enums import OutputFormat
from cli_output.ports.renderer import Renderer
from rich.console import Console

from wallpaper_effects_generator.adapters.output.base import OutputAdapterBase


class RichOutputAdapter(OutputAdapterBase):
    _default_format = OutputFormat.RICH

    def __init__(
        self,
        console: Console | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        super().__init__(renderer=renderer, console=console)
