from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.domain.models import EffectsCatalog
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort


class CatalogCache:
    def __init__(self, loader: EffectLoaderPort) -> None:
        self._loader = loader
        self._cache: EffectsCatalog | None = None
        self._cached_path: str | None = None

    def get(self, path: str | None = None) -> EffectsCatalog:
        if self._cache is None or path != self._cached_path:
            self._cache = self._loader.load(path=Path(path) if path else None)
            self._cached_path = path
        return self._cache

    def invalidate(self) -> None:
        self._cache = None
        self._cached_path = None
