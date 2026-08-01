from __future__ import annotations

from cli_output.adapters.factory import create_renderer
from cli_output.domain.enums import OutputFormat
from cli_output.ports.renderer import Renderer

from color_scheme_generator.adapters.output import projectors
from color_scheme_generator.domain.enums import Verbosity
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import ColorScheme, GenerationResult


class OutputAdapterBase:
    _default_format: OutputFormat

    def __init__(
        self,
        verbosity: Verbosity = Verbosity.NORMAL,
        renderer: Renderer | None = None,
    ) -> None:
        self._verbosity = verbosity
        self._renderer = renderer or create_renderer(self._default_format)

    def process_result(self, result: GenerationResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        self._renderer.custom(projectors.project_result(result))

    def error(self, exc: ColorSchemeError) -> None:
        self._renderer.error(projectors.project_error(exc))

    def palette_display(self, scheme: ColorScheme) -> None:
        self._renderer.custom(projectors.project_palette(scheme))

    def message(self, msg: str) -> None:
        self._renderer.message(projectors.project_message(msg))

    def config_info(
        self,
        settings: object,
        backends: dict,
        sources: list[str],
        templates: object = None,
    ) -> None:
        self._renderer.custom(
            projectors.project_config_info(settings, backends, sources, templates)
        )

    def install_result(self, results: list[dict]) -> None:
        self._renderer.custom(projectors.project_install(results))

    def uninstall_result(self, results: list[dict]) -> None:
        self._renderer.custom(projectors.project_uninstall(results))

    def version_info(self, version: str) -> None:
        self._renderer.custom(projectors.project_version(version))

    def backends_catalog(self, backends: list[dict], hint: str = "") -> None:
        self._renderer.custom(projectors.project_backends(backends, hint))
