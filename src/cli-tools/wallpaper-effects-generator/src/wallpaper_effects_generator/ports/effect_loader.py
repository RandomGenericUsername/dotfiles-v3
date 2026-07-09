from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from wallpaper_effects_generator.domain.models import EffectsCatalog


@runtime_checkable
class EffectLoaderPort(Protocol):
    def load(self, path: Path | None = None) -> EffectsCatalog: ...

    def get_default_path(self) -> Path: ...

    def get_resolved_path(self) -> Path | None: ...
