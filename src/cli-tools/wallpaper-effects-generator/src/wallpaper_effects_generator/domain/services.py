from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import ConfigResolutionError
from wallpaper_effects_generator.domain.models import (
    EffectsCatalog,
    ParameterDefinition,
    ProcessingRequest,
)


class CommandSanitizer:
    def split(self, command: str) -> list[str]:
        return shlex.split(command)

    def quote(self, value: str) -> str:
        return shlex.quote(value)


class CommandSubstitutionService:
    def __init__(self, sanitizer: CommandSanitizer | None = None) -> None:
        self._sanitizer = sanitizer or CommandSanitizer()

    def substitute(self, template: str, params: dict[str, Any], request: ProcessingRequest) -> str:
        result = template
        q = self._sanitizer.quote
        result = result.replace("{{input}}", q(str(request.input_path)))
        result = result.replace("{{output}}", q(str(request.output_path)))
        for key, value in params.items():
            result = result.replace("{{" + key + "}}", q(str(value)))
        return result


class ParameterResolutionService:
    def resolve(
        self,
        definition: ParameterDefinition,
        overrides: dict[str, Any] | None = None,
    ) -> Any:
        if overrides and definition.key in overrides:
            return overrides[definition.key]
        if definition.required:
            raise ConfigResolutionError(f"Required parameter '{definition.key}' has no value")
        return definition.default

    def resolve_all(
        self,
        parameters: tuple[ParameterDefinition, ...],
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for param in parameters:
            resolved[param.key] = self.resolve(param, overrides)
        return resolved


class OutputPathService:
    def resolve(
        self,
        input_path: Path,
        output_dir: Path,
        item_type: ItemType,
        flat: bool = False,
        explicit_output: bool = False,
    ) -> Path:
        filename = input_path.resolve().name
        if explicit_output or flat:
            return output_dir / filename
        return output_dir / item_type.subdir_name / filename

    def batch_output_dir(
        self,
        input_path: Path,
        output_dir: Path,
        flat: bool,
        explicit_output: bool,
    ) -> Path:
        if explicit_output or flat:
            return output_dir
        return output_dir / "all"


class CatalogValidationService:
    def validate(self, catalog: EffectsCatalog) -> list[str]:
        errors: list[str] = []
        effect_names = [e.name for e in catalog.effects]
        if len(effect_names) != len(set(effect_names)):
            seen: set[str] = set()
            for name in effect_names:
                if name in seen:
                    errors.append(f"Duplicate effect name: '{name}'")
                seen.add(name)
        effect_name_set = set(effect_names)
        for composite in catalog.composites:
            for step in composite.steps:
                if step.effect_name not in effect_names:
                    errors.append(
                        f"Composite '{composite.name}' references unknown effect "
                        f"'{step.effect_name}'"
                    )
        for preset in catalog.presets:
            for effect_name in preset.effects:
                if effect_name not in effect_name_set:
                    errors.append(
                        f"Preset '{preset.name}' references unknown effect '{effect_name}'"
                    )
        return errors
