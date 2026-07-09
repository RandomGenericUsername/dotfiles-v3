from __future__ import annotations

from typing import Protocol, runtime_checkable

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


@runtime_checkable
class OutputPort(Protocol):
    def process_result(self, result: ProcessingResult) -> None: ...

    def batch_result(self, result: BatchResult) -> None: ...

    def catalog_list(self, catalog: EffectsCatalog, query: CatalogQuery) -> None: ...

    def config_info(
        self,
        settings: AppSettings,
        catalog: EffectsCatalog,
        sources: list[str],
    ) -> None: ...

    def dump_config(
        self,
        settings: AppSettings,
        sources: list[str],
    ) -> None: ...

    def error(self, exc: Exception) -> None: ...

    def message(self, msg: str) -> None: ...
