from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from wallpaper_effects_generator.domain.models import AppSettings


@runtime_checkable
class ConfigResolverPort(Protocol):
    def resolve(self, explicit_path: Path | None = None) -> AppSettings: ...

    def get_resolved_path(self) -> Path | None: ...
