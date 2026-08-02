from __future__ import annotations

from cli_output.domain.enums import OutputFormat

from icon_templates_renderer.adapters.output.base import OutputAdapterBase


class JsonOutput(OutputAdapterBase):
    _default_format = OutputFormat.JSON
