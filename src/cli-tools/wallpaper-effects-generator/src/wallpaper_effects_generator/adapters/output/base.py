from __future__ import annotations

import sys

from cli_output.adapters.factory import create_renderer
from cli_output.domain.enums import OutputFormat
from cli_output.ports.renderer import Renderer
from rich.console import Console

from wallpaper_effects_generator.adapters.output import projectors
from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


class OutputAdapterBase:
    _default_format: OutputFormat

    def __init__(
        self,
        renderer: Renderer | None = None,
        console: Console | None = None,
    ) -> None:
        self._renderer = renderer or create_renderer(self._default_format, console=console)

    def process_result(self, result: ProcessingResult) -> None:
        self._renderer.result(projectors.project_result(result))

    def batch_result(self, result: BatchResult) -> None:
        self._renderer.custom(projectors.project_batch(result))

    def catalog_list(self, catalog: EffectsCatalog, query: CatalogQuery) -> None:
        self._renderer.custom(projectors.project_catalog(catalog, query))

    def config_info(
        self,
        settings: AppSettings,
        catalog: EffectsCatalog,
        sources: list[str],
    ) -> None:
        self._renderer.custom(projectors.project_config_info(settings, catalog, sources))

    def dump_config_template(self, content: str) -> None:
        sys.stdout.write(content)

    def dump_effects_template(self, content: str) -> None:
        sys.stdout.write(content)

    def error(self, exc: Exception) -> None:
        self._renderer.error(projectors.project_error(exc))

    def message(self, msg: str) -> None:
        self._renderer.message(projectors.project_message(msg))
