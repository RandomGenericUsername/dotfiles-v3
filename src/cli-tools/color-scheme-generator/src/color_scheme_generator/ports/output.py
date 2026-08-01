from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import ColorScheme, GenerationResult

if TYPE_CHECKING:
    from color_scheme_generator.domain.models import TemplateCatalog


@runtime_checkable
class OutputPort(Protocol):
    def process_result(self, result: GenerationResult) -> None: ...

    def error(self, exc: ColorSchemeError) -> None: ...

    def palette_display(self, scheme: ColorScheme) -> None: ...

    def message(self, msg: str) -> None: ...

    def config_info(
        self,
        settings: object,
        backends: dict,
        sources: list[str],
        templates: TemplateCatalog | None = None,
    ) -> None: ...

    def install_result(self, results: list[dict]) -> None: ...

    def uninstall_result(self, results: list[dict]) -> None: ...

    def version_info(self, version: str) -> None: ...

    def backends_catalog(self, backends: list[dict], hint: str = "") -> None: ...
