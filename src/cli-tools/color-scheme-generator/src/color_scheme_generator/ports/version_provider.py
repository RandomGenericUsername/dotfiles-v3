from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VersionProviderPort(Protocol):
    def get_version(self) -> str:
        ...
