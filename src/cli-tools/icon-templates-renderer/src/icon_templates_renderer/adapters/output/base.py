from __future__ import annotations

import sys

from cli_output.adapters.factory import create_renderer
from cli_output.domain.enums import OutputFormat
from cli_output.ports.renderer import Renderer

from icon_templates_renderer.adapters.output import projectors
from icon_templates_renderer.domain.enums import Verbosity
from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import (
    ListResult,
    MappingSetDefaultResult,
    MappingSetResult,
    MappingShowResult,
    RenderResult,
    ValidateResult,
)


class OutputAdapterBase:
    _default_format: OutputFormat

    def __init__(
        self,
        verbosity: Verbosity = Verbosity.NORMAL,
        renderer: Renderer | None = None,
    ) -> None:
        self._verbosity = verbosity
        self._renderer = renderer or create_renderer(self._default_format)

    def render_result(self, result: RenderResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_render_result(result))

    def list_result(self, result: ListResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_list_result(result))

    def validate_result(self, result: ValidateResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_validate_result(result))

    def mapping_show_result(self, result: MappingShowResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_mapping_show_result(result))

    def mapping_set_result(self, result: MappingSetResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_mapping_set_result(result))

    def mapping_set_default_result(self, result: MappingSetDefaultResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_mapping_set_default_result(result))

    def error(self, exc: IconRendererError) -> None:
        # Preserve v2's exact "Error: <message>" on stderr across all formats.
        sys.stderr.write(f"Error: {exc}\n")

    def message(self, msg: str) -> None:
        self._renderer.message(projectors.project_message(msg))
