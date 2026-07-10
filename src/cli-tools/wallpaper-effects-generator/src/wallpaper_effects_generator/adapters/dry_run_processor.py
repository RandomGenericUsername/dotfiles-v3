from __future__ import annotations

from pathlib import Path
from typing import Any

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import (
    CompositeNotFoundError,
    EffectNotFoundError,
    PresetNotFoundError,
)
from wallpaper_effects_generator.domain.models import (
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


class DryRunProcessor(EffectProcessorPort):
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
        pre_flight = self._pre_flight(request)
        if not pre_flight.success:
            return pre_flight
        effect = self._lookup_effect(name)
        resolved_params = self._param_resolver.resolve_all(effect.parameters, params)
        rendered = self._subst.substitute(effect.command, resolved_params, request)
        output_path = request.output_path or self._output_path_svc.resolve(
            request.input_path, self._output_dir, ItemType.EFFECT
        )
        return ProcessingResult(
            success=True,
            command=rendered,
            stdout="",
            stderr="",
            return_code=0,
            output_path=output_path,
        )

    def process_composite(
        self,
        name: str,
        request: ProcessingRequest,
        params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        pre_flight = self._pre_flight(request)
        if not pre_flight.success:
            return pre_flight
        composite = self._lookup_composite(name)
        commands: list[str] = []
        current_input = request.input_path
        for i, step in enumerate(composite.steps):
            effect = self._lookup_effect(step.effect_name)
            merged_params = {**step.parameters, **(params or {})}
            resolved_params = self._param_resolver.resolve_all(
                effect.parameters, merged_params
            )
            if i < len(composite.steps) - 1:
                step_output = Path(f"temp_step_{i}")
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
            commands.append(rendered)
            current_input = step_output
        return ProcessingResult(
            success=True,
            command="; ".join(commands),
            stdout="",
            stderr="",
            return_code=0,
            output_path=current_input,
        )

    def process_preset(
        self,
        name: str,
        request: ProcessingRequest,
        params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        pre_flight = self._pre_flight(request)
        if not pre_flight.success:
            return pre_flight
        preset = self._lookup_preset(name)
        if not preset.effects:
            return ProcessingResult(
                success=False, command="", stdout="", stderr="", return_code=-1, duration=0.0,
            )
        commands: list[str] = []
        current_input = request.input_path
        for effect_name in preset.effects:
            effect = self._lookup_effect(effect_name)
            resolved_params = self._param_resolver.resolve_all(effect.parameters, params)
            output_path = self._output_path_svc.resolve(
                current_input, self._output_dir, ItemType.PRESET
            )
            step_request = ProcessingRequest(
                input_path=current_input,
                output_path=output_path,
                params=request.params,
            )
            rendered = self._subst.substitute(
                effect.command, resolved_params, step_request
            )
            commands.append(rendered)
            current_input = output_path
        return ProcessingResult(
            success=True,
            command="; ".join(commands),
            stdout="",
            stderr="",
            return_code=0,
            output_path=request.output_path or current_input,
        )

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

    def _pre_flight(self, request: ProcessingRequest) -> ProcessingResult:
        errors: list[str] = []
        if not request.input_path.exists():
            errors.append(f"Input not found: {request.input_path}")
        if not self._runner.is_available():
            errors.append(f"Binary not available: {self._runner.get_binary()}")
        if not self._output_dir.exists():
            errors.append(f"Output dir not found: {self._output_dir}")
        if errors:
            return ProcessingResult(
                success=False,
                command="",
                stdout="",
                stderr="; ".join(errors),
                return_code=-1,
            )
        return ProcessingResult(
            success=True, command="", stdout="", stderr="", return_code=0,
        )
