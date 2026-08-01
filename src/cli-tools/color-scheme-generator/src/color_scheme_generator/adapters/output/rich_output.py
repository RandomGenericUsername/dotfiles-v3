from __future__ import annotations

from cli_output.domain.enums import OutputFormat

from color_scheme_generator.adapters.output.base import OutputAdapterBase


class RichOutput(OutputAdapterBase):
    _default_format = OutputFormat.RICH
