from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from wallpaper_effects_generator.domain.models import AppSettings, EffectsCatalog


@dataclass(frozen=True)
class ContextValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class ContextValidatorPort(Protocol):
    def validate(
        self,
        input_path: Path | None,
        settings: AppSettings,
        catalog: EffectsCatalog,
        output_dir: Path | None = None,
    ) -> ContextValidationResult: ...
