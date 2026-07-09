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
from wallpaper_effects_generator.ports.image_manager import ImageManagerPort


class InputContextValidator(ContextValidatorPort):
    def __init__(
        self,
        command_runner: CommandRunnerPort | None = None,
        image_manager: ImageManagerPort | None = None,
    ) -> None:
        self._runner = command_runner
        self._image_manager = image_manager

    def set_image_manager(self, image_manager: ImageManagerPort) -> None:
        self._image_manager = image_manager

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
                errors.append(
                    f"Container runtime '{engine}' not found on PATH"
                )
            if self._image_manager is not None:
                registry = settings.container.image_registry
                tag = settings.container.image_tag
                image = f"{registry}/weg:{tag}" if registry else f"weg:{tag}"
                if not self._image_manager.exists(image):
                    errors.append(f"Container image not found: {image}")
        if errors:
            return ContextValidationResult(valid=False, errors=errors)
        return ContextValidationResult(valid=True)
