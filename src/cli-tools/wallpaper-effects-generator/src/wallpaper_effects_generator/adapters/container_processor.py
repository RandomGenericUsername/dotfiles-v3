from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from oci_runtime import RunConfig, VolumeMount, engine_qualified_image

from wallpaper_effects_generator.adapters.serializer.effects_serializer import (
    EffectsSerializer,
)
from wallpaper_effects_generator.adapters.serializer.settings_serializer import (
    SettingsSerializer,
)
from wallpaper_effects_generator.domain.enums import ItemType, RuntimeMode
from wallpaper_effects_generator.domain.exceptions import (
    CommandExecutionError,
    CompositeNotFoundError,
    ContainerImageNotFoundError,
    EffectNotFoundError,
    PresetNotFoundError,
)
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    CompositeDefinition,
    ContainerSettings,
    EffectDefinition,
    EffectsCatalog,
    PresetDefinition,
    ProcessingRequest,
    ProcessingResult,
    RuntimeSettings,
)
from wallpaper_effects_generator.domain.services import (
    OutputPathService,
    ParameterResolutionService,
)
from wallpaper_effects_generator.ports.context_validator import (
    ContextValidatorPort,
)
from wallpaper_effects_generator.ports.processor import EffectProcessorPort


class ContainerProcessor(EffectProcessorPort):
    def __init__(
        self,
        command_runner: object,
        catalog: EffectsCatalog,
        output_dir: Path,
        container_engine: object | None = None,
        container_settings: ContainerSettings | None = None,
        settings: AppSettings | None = None,
        settings_serializer: SettingsSerializer | None = None,
        effects_serializer: EffectsSerializer | None = None,
        parameter_resolution: ParameterResolutionService | None = None,
        output_path_service: OutputPathService | None = None,
        context_validator: ContextValidatorPort | None = None,
        timeout: int | None = 3600,
    ) -> None:
        self._engine = container_engine
        self._catalog = catalog
        self._output_dir = output_dir
        self._container_settings = container_settings or ContainerSettings()
        self._settings = settings
        self._settings_serializer = settings_serializer or SettingsSerializer()
        self._effects_serializer = effects_serializer or EffectsSerializer()
        self._param_resolver = parameter_resolution or ParameterResolutionService()
        self._output_path_svc = output_path_service or OutputPathService()
        self._context_validator = context_validator
        self._timeout = timeout

    def _get_engine(self) -> object:
        if self._engine is None:
            from wallpaper_effects_generator.factory import create_container_engine as _make_engine
            self._engine = _make_engine(self._container_settings)
        return self._engine

    def _pre_flight(self, request: ProcessingRequest) -> ProcessingResult | None:
        if self._context_validator is None or self._settings is None:
            return None
        result = self._context_validator.validate(
            input_path=request.input_path,
            settings=self._settings,
            catalog=self._catalog,
            output_dir=self._output_dir,
        )
        if not result.valid:
            return ProcessingResult(
                success=False, command="", stdout="", stderr="; ".join(result.errors), return_code=-1,
            )
        return None

    def _ensure_image(self) -> str:
        image = self._resolve_image()
        if not self._get_engine().images.exists(image):
            raise ContainerImageNotFoundError(image)
        return image

    def process_effect(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        pre = self._pre_flight(request)
        if pre is not None:
            return pre
        effect = self._lookup_effect(name)
        self._param_resolver.resolve_all(effect.parameters, params or request.params)
        return self._run_in_container(
            self._build_weg_command("effect", name, request, params or request.params),
            request, name, ItemType.EFFECT,
        )

    def process_composite(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        pre = self._pre_flight(request)
        if pre is not None:
            return pre
        composite = self._lookup_composite(name)
        if not composite.steps:
            return ProcessingResult(
                success=False, command="", stdout="", stderr=f"Composite '{name}' has no steps defined", return_code=-1,
            )
        return self._run_in_container(
            self._build_weg_command("composite", name, request, params or request.params),
            request, name, ItemType.COMPOSITE,
        )

    def process_preset(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        pre = self._pre_flight(request)
        if pre is not None:
            return pre
        preset = self._lookup_preset(name)
        if not preset.effects:
            return ProcessingResult(
                success=False, command="", stdout="", stderr=f"Preset '{name}' has no effects defined", return_code=-1,
            )
        return self._run_in_container(
            self._build_weg_command("preset", name, request, params or request.params),
            request, name, ItemType.PRESET,
        )

    def process_batch(self, request: Any) -> Any:
        raise NotImplementedError("Batch processing deferred to Epic 3")

    def _build_weg_command(
        self, subcommand: str, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None,
    ) -> list[str]:
        input_name = Path(request.input_path).name
        output_name = Path(request.output_path).name
        cmd = [
            "weg",
            "--config", "/weg-config/settings.toml",
            "--effects", "/weg-effects/effects.yaml",
            "process", subcommand, name,
            f"/input/{input_name}",
            "-o", "/output",
        ]
        if params:
            for key, value in params.items():
                cmd.extend(["--param", f"{key}={value}"])
        return cmd

    def _run_in_container(
        self, container_args: list[str], request: ProcessingRequest,
        effect_name: str, item_type: ItemType = ItemType.EFFECT,
    ) -> ProcessingResult:
        settings_toml: Path | None = None
        effects_yaml: Path | None = None
        temp_out: Path | None = None
        try:
            image = self._ensure_image()
            settings_toml, effects_yaml = self._serialize_artifacts()
            input_parent = request.input_path.parent.resolve()
            output_path = request.output_path or self._output_path_svc.resolve(
                request.input_path, self._output_dir, item_type,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temp_out = Path(tempfile.mkdtemp(dir=output_path.parent, prefix=".weg-container-"))
            caps = self._get_engine().capabilities
            run_flags = list(caps.default_run_flags) if caps is not None else []
            run_config = RunConfig(
                image=image, command=tuple(container_args), detach=False, remove=True,
                volumes=(
                    VolumeMount(source=str(settings_toml), target="/weg-config/settings.toml", read_only=True),
                    VolumeMount(source=str(effects_yaml), target="/weg-effects/effects.yaml", read_only=True),
                    VolumeMount(source=str(input_parent), target="/input", read_only=True),
                    VolumeMount(source=str(temp_out), target="/output", read_only=False),
                ),
                runtime_flags=tuple(run_flags),
            )
            start = time.monotonic()
            self._get_engine().containers.run(run_config)
            duration = time.monotonic() - start
            container_out = temp_out / request.input_path.name
            if container_out.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(container_out), str(output_path))
            return ProcessingResult(
                success=True, command=" ".join(container_args),
                stdout="", stderr="", return_code=0, output_path=output_path,
                duration=duration,
            )
        except CommandExecutionError as e:
            command_str = " ".join(container_args)
            return ProcessingResult(
                success=False, command=command_str, stdout="", stderr=str(e),
                return_code=e.return_code, output_path=output_path,
            )
        finally:
            self._cleanup_artifacts(settings_toml, effects_yaml)
            if temp_out is not None and temp_out.exists():
                shutil.rmtree(temp_out, ignore_errors=True)

    def _serialize_artifacts(self) -> tuple[Path, Path]:
        settings_toml: Path | None = None
        effects_yaml: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
                settings_toml = Path(f.name)
            if self._settings is not None:
                local_settings = AppSettings(
                    version=self._settings.version,
                    execution=self._settings.execution,
                    output=self._settings.output,
                    processing=self._settings.processing,
                    backend=self._settings.backend,
                    runtime=RuntimeSettings(mode=RuntimeMode.LOCAL),
                    container=self._settings.container,
                )
                self._settings_serializer.serialize(local_settings, settings_toml)
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
                effects_yaml = Path(f.name)
            self._effects_serializer.serialize(self._catalog, effects_yaml)
            return settings_toml, effects_yaml
        except BaseException:
            self._cleanup_artifacts(settings_toml, effects_yaml)
            raise

    @staticmethod
    def _cleanup_artifacts(*paths: Path | None) -> None:
        for p in paths:
            if p is not None:
                p.unlink(missing_ok=True)

    def _resolve_image(self) -> str:
        cs = self._container_settings
        return engine_qualified_image(
            cs.image_name, cs.engine, cs.image_tag, cs.image_registry
        )

    def _lookup_effect(self, name: str) -> EffectDefinition:
        for effect in self._catalog.effects:
            if effect.name == name:
                return effect
        raise EffectNotFoundError(name)

    def _lookup_composite(self, name: str) -> CompositeDefinition:
        for composite in self._catalog.composites:
            if composite.name == name:
                return composite
        raise CompositeNotFoundError(name)

    def _lookup_preset(self, name: str) -> PresetDefinition:
        for preset in self._catalog.presets:
            if preset.name == name:
                return preset
        raise PresetNotFoundError(name)
