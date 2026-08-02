from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import ColorScheme


@runtime_checkable
class ColorSchemeLoaderPort(Protocol):
    def load(self, path: Path) -> ColorScheme: ...
    def supports(self, path: Path) -> bool: ...
