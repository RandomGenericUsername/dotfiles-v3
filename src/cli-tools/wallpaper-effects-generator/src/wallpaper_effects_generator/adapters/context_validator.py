from __future__ import annotations

import shutil
from pathlib import Path

from wallpaper_effects_generator.domain.enums import RuntimeMode
from wallpaper_effects_generator.domain.models import AppSettings, EffectsCatalog
from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.context_validator import (
    ContextValidationResult,
    ContextValidatorPort,
)


class InputContextValidator(ContextValidatorPort):
    def __init__(
        self,
        command_runner: CommandRunnerPort | None = None,
    ) -> None:
        self._runner = command_runner

    def validate(
        self,
        input_path: Path | None,
        settings: AppSettings,
        catalog: EffectsCatalog,
        output_dir: Path | None = None,
    ) -> ContextValidationResult:
        errors: list[str] = []
        if input_path is not None and not input_path.exists():
            errors.append(f"Input not found: {input_path}")
        if self._runner is not None and not self._runner.is_available():
            errors.append(f"Binary not available: {self._runner.get_binary()}")
        if output_dir is not None and not output_dir.exists():
            errors.append(f"Output dir not found: {output_dir}")
        if settings.runtime.mode == RuntimeMode.CONTAINER:
            engine = settings.container.engine
            if shutil.which(engine) is None:
                errors.append(f"Container runtime '{engine}' not found on PATH")
        if errors:
            return ContextValidationResult(valid=False, errors=errors)
        return ContextValidationResult(valid=True)
