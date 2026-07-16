from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class TemplateDirResolverPort(Protocol):
    def resolve(self) -> Path:
        ...
