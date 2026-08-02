from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import AppSettings


@runtime_checkable
class ConfigResolverPort(Protocol):
    def resolve(
        self,
        *,
        cli_overrides: dict[str, str] | None = None,
        explicit_path: str | None = None,
    ) -> AppSettings: ...
    def get_resolved_path(self) -> Path | None: ...
