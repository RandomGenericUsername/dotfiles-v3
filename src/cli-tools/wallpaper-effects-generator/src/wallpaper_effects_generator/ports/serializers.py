from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from wallpaper_effects_generator.domain.models import AppSettings, EffectsCatalog


@runtime_checkable
class SettingsSerializerPort(Protocol):
    def serialize(self, settings: AppSettings, path: Path) -> None: ...

    def deserialize(self, path: Path) -> AppSettings: ...


@runtime_checkable
class EffectsSerializerPort(Protocol):
    def serialize(self, catalog: EffectsCatalog, path: Path) -> None: ...

    def deserialize(self, path: Path) -> EffectsCatalog: ...
