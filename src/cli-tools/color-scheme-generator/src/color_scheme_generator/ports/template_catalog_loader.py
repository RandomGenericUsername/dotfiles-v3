from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from color_scheme_generator.domain.models import TemplateCatalog


@runtime_checkable
class TemplateCatalogLoaderPort(Protocol):
    def load(self, explicit_dir: Path | None = None) -> TemplateCatalog: ...

    def get_resolved_path(self) -> Path | None: ...
