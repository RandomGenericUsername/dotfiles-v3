from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ColorSchemeResolverPort(Protocol):
    def resolve(self) -> Path | None: ...
