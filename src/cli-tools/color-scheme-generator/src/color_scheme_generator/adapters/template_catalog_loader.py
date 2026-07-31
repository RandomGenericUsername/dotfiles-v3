from __future__ import annotations

from pathlib import Path

from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.domain.models import TemplateCatalog
from color_scheme_generator.domain.services import TemplateCatalogService


class DirectoryTemplateCatalogLoader:
    def __init__(self, resolver: TemplateDirResolver) -> None:
        self._resolver = resolver
        self._deriver = TemplateCatalogService()
        self._cache: TemplateCatalog | None = None
        self._cached_key: str | None = None
        self._resolved_path: Path | None = None

    def load(self, explicit_dir: Path | None = None) -> TemplateCatalog:
        key = str(explicit_dir) if explicit_dir else "__resolved__"
        if self._cache is not None and key == self._cached_key:
            return self._cache
        dir_path = explicit_dir if explicit_dir else self._resolver.resolve()
        self._resolved_path = dir_path
        catalog = self._deriver.derive(dir_path)
        self._cache = catalog
        self._cached_key = key
        return catalog

    def get_resolved_path(self) -> Path | None:
        return self._resolved_path
