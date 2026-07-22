from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode
from color_scheme_generator.domain.exceptions import ColorSchemeError, ConfigResolutionError
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.domain.services import ParameterResolutionService


def default_app_settings() -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/color-scheme"),
            default_formats=(),
            overwrite=False,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={},
        ),
        template=TemplateSettings(
            templates_dir=None,
            custom_templates_dir=None,
        ),
        runtime=RuntimeSettings(
            mode=RuntimeMode.LOCAL,
            engine=ContainerEngine.DOCKER,
        ),
        container=ContainerSettings(
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
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


def build_image_name(settings: AppSettings, backend: Backend) -> str:
    prefix = settings.container.image_prefix
    return f"{prefix}color-scheme-{backend.image_suffix}:{settings.container.image_tag}"
