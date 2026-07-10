from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import (
    CompositeNotFoundError,
    EffectNotFoundError,
    PresetNotFoundError,
)
from wallpaper_effects_generator.domain.models import (
    CommandResult,
    EffectsCatalog,
    ProcessingRequest,
    ProcessingResult,
)
from wallpaper_effects_generator.domain.services import (
    CommandSubstitutionService,
    OutputPathService,
    ParameterResolutionService,
)
from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.processor import EffectProcessorPort


class LocalProcessor(EffectProcessorPort):
    def __init__(
        self,
        command_runner: CommandRunnerPort,
        catalog: EffectsCatalog,
        output_dir: Path,
        command_substitution: CommandSubstitutionService | None = None,
        parameter_resolution: ParameterResolutionService | None = None,
        output_path_service: OutputPathService | None = None,
    ) -> None:
        self._runner = command_runner
        self._catalog = catalog
        self._output_dir = output_dir
        self._subst = command_substitution or CommandSubstitutionService()
        self._param_resolver = parameter_resolution or ParameterResolutionService()
        self._output_path_svc = output_path_service or OutputPathService()

    def process_effect(
        self,
        name: str,
        request: ProcessingRequest,
        params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        effect = self._lookup_effect(name)
        resolved_params = self._param_resolver.resolve_all(effect.parameters, params)
        rendered = self._subst.substitute(effect.command, resolved_params, request)
        output_path = request.output_path or self._output_path_svc.resolve(
            request.input_path, self._output_dir, ItemType.EFFECT
        )
        cmd_result = self._runner.execute(rendered)
        return ProcessingResult(
            success=cmd_result.return_code == 0,
            command=rendered,
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            return_code=cmd_result.return_code,
            duration=cmd_result.duration,
            output_path=output_path,
        )

    def process_composite(
        self,
        name: str,
        request: ProcessingRequest,
        params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        composite = self._lookup_composite(name)
        current_input = request.input_path
        temp_dir = Path(tempfile.mkdtemp(prefix=f"weg-{name}-"))
        all_commands: list[str] = []
        total_duration = 0.0
        try:
            for i, step in enumerate(composite.steps):
                effect = self._lookup_effect(step.effect_name)
                merged_params = {**step.parameters, **(params or {})}
                resolved_params = self._param_resolver.resolve_all(
                    effect.parameters, merged_params
                )
                if i < len(composite.steps) - 1:
                    step_output = temp_dir / f"step_{i}_{current_input.name}"
                else:
                    step_output = request.output_path or self._output_path_svc.resolve(
                        request.input_path, self._output_dir, ItemType.COMPOSITE
                    )
                step_request = ProcessingRequest(
                    input_path=current_input,
                    output_path=step_output,
                    params=request.params,
                )
                rendered = self._subst.substitute(
                    effect.command, resolved_params, step_request
                )
                cmd_result = self._runner.execute(rendered)
                all_commands.append(rendered)
                total_duration += cmd_result.duration
                if cmd_result.return_code != 0:
                    stable_path = request.output_path or self._output_path_svc.resolve(
                        request.input_path, self._output_dir, ItemType.COMPOSITE
                    )
                    try:
                        shutil.copy2(step_output, stable_path)
                    except OSError:
                        pass
                    return ProcessingResult(
                        success=False,
                        command="; ".join(all_commands),
                        stdout=cmd_result.stdout,
                        stderr=cmd_result.stderr,
                        return_code=cmd_result.return_code,
                        duration=total_duration,
                        output_path=stable_path,
                    )
                current_input = step_output
            return ProcessingResult(
                success=True,
                command="; ".join(all_commands),
                stdout="",
                stderr="",
                return_code=0,
                duration=total_duration,
                output_path=current_input,
            )
        finally:
            self._cleanup_temp(temp_dir)

    def process_preset(
        self,
        name: str,
        request: ProcessingRequest,
        params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        preset = self._lookup_preset(name)
        if not preset.effects:
            return ProcessingResult(
                success=False,
                command="",
                stdout="",
                stderr="",
                return_code=-1,
                duration=0.0,
            )
        current_input = request.input_path
        temp_dir = Path(tempfile.mkdtemp(prefix=f"weg-preset-{name}-"))
        all_commands: list[str] = []
        total_duration = 0.0
        try:
            merged_preset_params = {**preset.parameters, **(params or {})}
            for i, effect_name in enumerate(preset.effects):
                is_last = i == len(preset.effects) - 1
                step_output = (
                    request.output_path or self._output_path_svc.resolve(
                        request.input_path, self._output_dir, ItemType.PRESET
                    ) if is_last else temp_dir / f"step_{i}_{Path(current_input).name}"
                )
                step_request = ProcessingRequest(
                    input_path=current_input, output_path=step_output, params=request.params,
                )
                try:
                    composite = self._lookup_composite(effect_name)
                    result = self.process_composite(
                        effect_name, step_request, merged_preset_params
                    )
                    rendered = result.command
                    cmd_result = CommandResult(
                        stdout=result.stdout, stderr=result.stderr,
                        return_code=0 if result.success else 1,
                        duration=result.duration,
                    )
                except CompositeNotFoundError:
                    effect = self._lookup_effect(effect_name)
                    resolved_params = self._param_resolver.resolve_all(effect.parameters, merged_preset_params)
                    rendered = self._subst.substitute(effect.command, resolved_params, step_request)
                    cmd_result = self._runner.execute(rendered)
                all_commands.append(rendered)
                total_duration += cmd_result.duration
                if cmd_result.return_code != 0:
                    return ProcessingResult(
                        success=False,
                        command="; ".join(all_commands),
                        stdout=cmd_result.stdout,
                        stderr=cmd_result.stderr,
                        return_code=cmd_result.return_code,
                        duration=total_duration,
                        output_path=step_output,
                    )
                current_input = step_output
            return ProcessingResult(
                success=True,
                command="; ".join(all_commands),
                stdout="",
                stderr="",
                return_code=0,
                duration=total_duration,
                output_path=current_input,
            )
        finally:
            self._cleanup_temp(temp_dir)

    def process_batch(self, request: Any) -> Any:
        raise NotImplementedError("Batch processing deferred to Epic 3")

    def _lookup_effect(self, name: str) -> Any:
        for effect in self._catalog.effects:
            if effect.name == name:
                return effect
        raise EffectNotFoundError(name)

    def _lookup_composite(self, name: str) -> Any:
        for composite in self._catalog.composites:
            if composite.name == name:
                return composite
        raise CompositeNotFoundError(name)

    def _lookup_preset(self, name: str) -> Any:
        for preset in self._catalog.presets:
            if preset.name == name:
                return preset
        raise PresetNotFoundError(name)

    @staticmethod
    def _cleanup_temp(temp_dir: Path) -> None:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
