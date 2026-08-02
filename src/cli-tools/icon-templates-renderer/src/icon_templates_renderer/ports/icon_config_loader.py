from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import IconConfig, IconGroup, PathOverrides


@runtime_checkable
class IconConfigLoaderPort(Protocol):
    def load(self, yaml_path: Path, overrides: PathOverrides | None = None) -> IconConfig: ...
    def load_one(
        self, yaml_path: Path, icon: str, overrides: PathOverrides | None = None
    ) -> IconGroup: ...
    def get_resolved_path(self) -> Path | None: ...
