from __future__ import annotations

from typing import Protocol, runtime_checkable

from color_scheme_generator.domain.models import AppSettings


@runtime_checkable
class SettingsSerializerPort(Protocol):
    def serialize(self, settings: AppSettings) -> str:
        ...

    def deserialize(self, raw: str) -> AppSettings:
        ...
