from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from oci_runtime import engine_qualified_image

from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend, ColorFormat, ContainerEngine, RuntimeMode
from color_scheme_generator.domain.exceptions import ColorSchemeError, ConfigResolutionError
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
)
from color_scheme_generator.domain.services import ParameterResolutionService
from color_scheme_generator.factory import (
    CliDependencies,
    create_container_engine,
    create_container_processor,
    create_local_processor,
)
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


def default_app_settings() -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/color-scheme"),
            default_formats=(ColorFormat.JSON, ColorFormat.SH),
            overwrite=False,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={},
        ),
        runtime=RuntimeSettings(
            mode=RuntimeMode.LOCAL,
        ),
        container=ContainerSettings(
            engine="docker",
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=300,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


def parse_params(raw: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            print(
                f"Warning: ignoring malformed parameter '{entry}' (expected key=value)",
                file=sys.stderr,
            )
            continue
        key, _, value = entry.partition("=")
        key = key.strip()
        if not key:
            print(
                f"Warning: ignoring malformed parameter with empty key '{entry}'",
                file=sys.stderr,
            )
            continue
        result[key] = value.strip()
    return result


def resolve_backend_params(
    raw_params: dict[str, str],
    resolved_backend: Backend,
    backend_catalog_loader: YamlBackendCatalogLoader | None,
) -> dict[str, Any]:
    if not raw_params:
        return {}

    if not backend_catalog_loader:
        raise ConfigResolutionError(
            key=next(iter(raw_params)),
            reason="No backend catalog loader available — cannot validate params",
        )

    try:
        catalog = backend_catalog_loader.load()
    except Exception as exc:
        raise ColorSchemeError(f"Failed to load backend catalog: {exc}") from exc

    backend_def = catalog.get(resolved_backend)
    if not backend_def:
        raise ConfigResolutionError(
            key=next(iter(raw_params)),
            reason=(
                f"Backend '{resolved_backend.value}' not found in catalog"
                " — cannot validate params"
            ),
        )

    valid_keys = {p.name for p in backend_def.parameters}
    for key in raw_params:
        if key not in valid_keys:
            raise ConfigResolutionError(
                key=key,
                reason=(
                    f"Parameter '{key}' is not defined"
                    f" for backend '{resolved_backend.value}'"
                ),
            )

    if backend_def.parameters:
        return ParameterResolutionService.resolve_all(backend_def.parameters, raw_params)
    return {}


def build_image_name(settings: AppSettings, backend: Backend, engine: str = "docker") -> str:
    prefix = settings.container.image_prefix
    base = f"{prefix}-{backend.image_suffix}"
    return engine_qualified_image(base, engine, settings.container.image_tag)


def resolve_processor(
    settings: AppSettings,
    deps: CliDependencies,
    engine_override: str | None = None,
) -> ColorSchemeProcessorPort:
    if deps.processor is not None:
        return deps.processor
    if settings.runtime.mode == RuntimeMode.CONTAINER:
        engine_value = engine_override or settings.container.engine
        engine = ContainerEngine(engine_value)
        container_runtime = create_container_engine(engine=engine)
        return create_container_processor(
            container_runtime,
            template_dir_resolver=deps.template_dir_resolver,
            engine_value=engine_value,
        )
    return create_local_processor(deps.backend_registry, deps.template_renderer)


def resolve_container_engine(
    container_engine: ContainerEngine | None,
    config_resolver: AssembledConfigResolver | None,
    config_path: str | None,
    cli_overrides: dict[str, str],
) -> ContainerEngine:
    if container_engine is not None:
        return container_engine
    if config_resolver is not None:
        try:
            settings = config_resolver.resolve(
                explicit_path=config_path, cli_overrides=cli_overrides
            )
            return ContainerEngine(settings.container.engine)
        except Exception:
            pass
    return ContainerEngine.DOCKER
