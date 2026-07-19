from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from color_scheme_generator.cli._helpers import default_app_settings, parse_params
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ColorSchemeError, ConfigResolutionError
from color_scheme_generator.domain.models import (
    GenerationRequest,
    GeneratorConfig,
)
from color_scheme_generator.domain.services import ParameterResolutionService
from color_scheme_generator.factory import CliDependencies


def show(
    ctx: typer.Context,
    image_path: Path = typer.Argument(..., help="Path to the input image file"),  # noqa: B008
    backend: Backend | None = typer.Option(None, "--backend", help="Extraction backend"),  # noqa: B008
    param: list[str] = typer.Option([], "--param", help="Backend parameter overrides"),  # noqa: B008
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = (
            deps.config_resolver.resolve()
            if deps.config_resolver
            else default_app_settings()
        )
    except ColorSchemeError:
        typer.echo("Warning: config resolution failed, using defaults", err=True)
        settings = default_app_settings()

    try:
        raw_params = parse_params(param)

        resolved_backend = backend or settings.generation.backend or Backend.CUSTOM

        resolved_params: dict[str, Any] = {}
        if raw_params:
            if not deps.backend_catalog_loader:
                raise ConfigResolutionError(
                    key=next(iter(raw_params)),
                    reason="No backend catalog loader available — cannot validate params",
                )
            try:
                catalog = deps.backend_catalog_loader.load()
            except Exception as exc:
                raise ColorSchemeError(
                    f"Failed to load backend catalog: {exc}"
                ) from exc
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
