from __future__ import annotations

from cli_output.domain.enums import OutputFormat

from icon_templates_renderer.adapters.output import projectors
from icon_templates_renderer.adapters.output.base import OutputAdapterBase
from icon_templates_renderer.domain.enums import Verbosity
from icon_templates_renderer.domain.models import TemplateAnalysis, TemplateScanEntry


class PlainOutput(OutputAdapterBase):
    _default_format = OutputFormat.PLAIN

    def template_analysis_result(self, result: TemplateAnalysis) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_template_analysis(result))

    def template_scan_result(self, result: list[TemplateScanEntry]) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_template_scan(result))
