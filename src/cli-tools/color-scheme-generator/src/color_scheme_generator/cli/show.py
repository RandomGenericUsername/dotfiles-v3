from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode
from color_scheme_generator.domain.exceptions import ColorSchemeError, ConfigResolutionError
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationRequest,
    GenerationSettings,
    GeneratorConfig,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.domain.services import ParameterResolutionService


def _parse_params(raw: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        result[key.strip()] = value.strip()
    return result


def _default_app_settings() -> AppSettings:
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


def show(
    ctx: typer.Context,
    image_path: Path = typer.Argument(..., help="Path to the input image file"),  # noqa: B008
    backend: Backend | None = typer.Option(None, "--backend", help="Extraction backend"),  # noqa: B008
    param: list[str] = typer.Option([], "--param", help="Backend parameter overrides"),  # noqa: B008
) -> None:
    deps = ctx.obj["deps"]
    try:
        settings = (
            deps.config_resolver.resolve()
            if deps.config_resolver
            else _default_app_settings()
        )
    except ColorSchemeError:
        settings = _default_app_settings()

    try:
        raw_params = _parse_params(param)

        resolved_backend = backend or settings.generation.backend or Backend.CUSTOM

        resolved_params: dict[str, Any] = {}
        if deps.backend_catalog_loader and raw_params:
            catalog = deps.backend_catalog_loader.load()
            backend_def = catalog.get(resolved_backend)
            if backend_def:
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
                    resolved_params = ParameterResolutionService.resolve_all(
                        backend_def.parameters, raw_params
                    )

        config = GeneratorConfig(
            backend=resolved_backend,
            params=resolved_params,
            formats=(),
            output_dir=settings.output.directory,
        )
        request = GenerationRequest(image_path=image_path, config=config)
        result = deps.processor.process_show(request, settings)
        deps.output_adapter.palette_display(result.color_scheme)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import json as _json
        import sys
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None
