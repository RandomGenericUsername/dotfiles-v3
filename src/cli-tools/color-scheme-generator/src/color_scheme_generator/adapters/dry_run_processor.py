from __future__ import annotations

import shlex
import time
from typing import TYPE_CHECKING

from color_scheme_generator.domain.enums import RuntimeMode
from color_scheme_generator.domain.exceptions import (
    BackendNotRegisteredError,
    ColorSchemeError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    InvalidImageError,
    PaletteGenerationError,
)
from color_scheme_generator.domain.models import (
    BackendParameterDefinition,
    GenerationResult,
)

if TYPE_CHECKING:
    from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
    from color_scheme_generator.domain.enums import Backend
    from color_scheme_generator.domain.models import (
        AppSettings,
        GenerationRequest,
    )
    from color_scheme_generator.ports.backend_catalog_loader import BackendCatalogLoaderPort
    from color_scheme_generator.ports.container_runtime import ContainerRuntimePort
    from color_scheme_generator.ports.output import OutputPort
    from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort


class DryRunProcessor:
    def __init__(
        self,
        backend_catalog_loader: BackendCatalogLoaderPort,
        container_runtime: ContainerRuntimePort | None = None,
        output_adapter: OutputPort | None = None,
        template_dir_resolver: TemplateDirResolver | None = None,
        backend_registry: dict[Backend, PaletteGeneratorPort] | None = None,
    ) -> None:
        self._backend_catalog_loader = backend_catalog_loader
        self._container_runtime = container_runtime
        self._output_adapter = output_adapter
        self._template_dir_resolver = template_dir_resolver
        self._backend_registry = backend_registry or {}

    def _build_image_name(self, settings: AppSettings, backend_value: str) -> str:
        prefix = settings.container.image_prefix
        tag = settings.container.image_tag
        return f"{prefix}color-scheme-{backend_value}:{tag}"

    def _pre_flight_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> None:
        if not request.image_path.is_file():
            raise InvalidImageError(
                request.image_path,
                "Input image does not exist or is not readable",
            )

        output_dir = request.config.output_dir
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PaletteGenerationError(
                f"Output directory is not writable: {output_dir}"
            ) from exc

        if self._template_dir_resolver:
            try:
                self._template_dir_resolver.resolve()
            except Exception as exc:
                raise PaletteGenerationError(
                    f"Templates directory could not be resolved: {exc}"
                ) from exc

        if settings.runtime.mode == RuntimeMode.LOCAL:
            if request.config.backend not in self._backend_registry:
                raise BackendNotRegisteredError(request.config.backend)
        elif settings.runtime.mode == RuntimeMode.CONTAINER:
            if self._container_runtime is None:
                raise ContainerRuntimeUnavailableError(
                    "No container runtime configured"
                )
            image = self._build_image_name(settings, request.config.backend.value)
            if not self._container_runtime.image_exists(image):
                raise ContainerImageNotFoundError(image, request.config.backend)

    def _validate_params(
        self, backend: Backend, params: dict[str, str]
    ) -> None:
        catalog = self._backend_catalog_loader.load()
        if backend not in catalog:
            raise PaletteGenerationError(
                f"Backend '{backend.value}' not found in catalog"
            )
        backend_def = catalog[backend]

        for param_name, param_value in params.items():
            param_def = None
            for pd in backend_def.parameters:
                if pd.name == param_name:
                    param_def = pd
                    break
            if param_def is None:
                raise PaletteGenerationError(
                    f"Unknown parameter '{param_name}' for backend '{backend.value}'"
                )

            try:
                self._coerce_param(param_def, param_value)
            except (ValueError, TypeError) as exc:
                raise PaletteGenerationError(
                    f"Parameter '{param_name}': expected type {param_def.type_}, "
                    f"got '{param_value}'"
                ) from exc

    def _coerce_param(
        self, param_def: BackendParameterDefinition, raw_value: str
    ) -> object:
        if param_def.type_ == "float":
            return float(raw_value)
        elif param_def.type_ == "int":
            return int(raw_value)
        elif param_def.type_ == "str":
            if param_def.choices and raw_value not in param_def.choices:
                raise ValueError(
                    f"'{raw_value}' is not a valid choice. "
                    f"Must be one of: {', '.join(param_def.choices)}"
                )
            return raw_value
        return raw_value

    def _build_command_plan(
        self, request: GenerationRequest, subcommand: str
    ) -> str:
        cmd = [
            "csg",
            subcommand,
            str(request.image_path),
            "--runtime",
            "local",
            "--backend",
            request.config.backend.value,
        ]
        for key, value in request.config.params.items():
            cmd.extend(["--param", f"{key}={value}"])
        if subcommand == "generate":
            for fmt in request.config.formats:
                cmd.extend(["--format", fmt.value])
            cmd.extend(["-o", str(request.config.output_dir)])
        return shlex.join(cmd)

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        start = time.monotonic()

        try:
            self._pre_flight_generate(request, settings)
            self._validate_params(request.config.backend, request.config.params)

            command_plan = self._build_command_plan(request, "generate")
            result = GenerationResult(
                success=True,
                color_scheme=None,
                output_files=(),
                backend=request.config.backend,
                stderr=command_plan,
                return_code=0,
                duration=time.monotonic() - start,
            )

            if self._output_adapter:
                self._output_adapter.process_result(result)

            return result

        except ColorSchemeError as exc:
            if self._output_adapter:
                self._output_adapter.error(exc)
            raise

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        start = time.monotonic()

        try:
            self._pre_flight_generate(request, settings)
            self._validate_params(request.config.backend, request.config.params)

            command_plan = self._build_command_plan(request, "show")
            result = GenerationResult(
                success=True,
                color_scheme=None,
                output_files=(),
                backend=request.config.backend,
                stderr=command_plan,
                return_code=0,
                duration=time.monotonic() - start,
            )

            if self._output_adapter:
                self._output_adapter.process_result(result)

            return result

        except ColorSchemeError as exc:
            if self._output_adapter:
                self._output_adapter.error(exc)
            raise
