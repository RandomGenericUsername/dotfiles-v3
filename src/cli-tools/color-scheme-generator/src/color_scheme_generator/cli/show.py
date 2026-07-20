from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.cli._helpers import (
    default_app_settings,
    parse_params,
    resolve_backend_params,
)
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import (
    GenerationRequest,
    GeneratorConfig,
)
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

        resolved_params = resolve_backend_params(
            raw_params, resolved_backend, deps.backend_catalog_loader
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
