from __future__ import annotations

from cli_output.domain.enums import OutputFormat

from wallpaper_effects_generator.adapters.output.base import OutputAdapterBase


class PlainOutputAdapter(OutputAdapterBase):
    _default_format = OutputFormat.PLAIN
