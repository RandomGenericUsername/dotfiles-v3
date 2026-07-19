from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.cli._helpers import default_app_settings, parse_params
from color_scheme_generator.cli.dump_config_cmd import dump_config
from color_scheme_generator.cli.dump_templates_cmd import dump_templates
from color_scheme_generator.cli.info_cmd import info
from color_scheme_generator.cli.list_backends_cmd import list_backends
from color_scheme_generator.cli.show import show
from color_scheme_generator.cli.version_cmd import version
from color_scheme_generator.domain.enums import (
    Backend,
    ColorFormat,
    ContainerEngine,
    OutputFormat,
    RuntimeMode,
)
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
from color_scheme_generator.factory import (
    CliDependencies,
    create_backend_catalog_loader,
    create_backend_registry,
    create_config_resolver,
    create_output_adapter,
    create_template_dir_resolver,
    create_template_renderer,
)

app = typer.Typer()


def build_deps() -> CliDependencies:
    registry = create_backend_registry()
    return CliDependencies(
        backend_registry=registry,
        backend_catalog_loader=create_backend_catalog_loader(),
        config_resolver=create_config_resolver(),
        processor=LocalProcessor(registry),
        template_dir_resolver=create_template_dir_resolver(),
        template_renderer=create_template_renderer(),
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(  # noqa: B008
        OutputFormat.JSON,
        "--output-format",
        help="Output format for command results",
        case_sensitive=False,
    ),
) -> None:
    ctx.obj = {"deps": build_deps()}
    ctx.obj["deps"].output_adapter = create_output_adapter(output_format)


@app.command()
def generate(
    ctx: typer.Context,
    image_path: Path = typer.Argument(..., help="Path to the input image file"),  # noqa: B008
    backend: Backend | None = typer.Option(None, "--backend", help="Extraction backend"),  # noqa: B008
    param: list[str] = typer.Option([], "--param", help="Backend parameter overrides"),  # noqa: B008
    formats: list[ColorFormat] | None = typer.Option(  # noqa: B008
        None, "--format", "-f", help="Output formats"
    ),
    output_dir: Path | None = typer.Option(  # noqa: B008
        None, "--output-dir", "-o", help="Output directory"
    ),
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

        resolved_formats: tuple[ColorFormat, ...]
        if formats is not None:
            resolved_formats = tuple(formats)
        else:
            resolved_formats = settings.output.default_formats

        resolved_output_dir = output_dir or settings.output.directory

        config = GeneratorConfig(
            backend=resolved_backend,
            params=resolved_params,
            formats=resolved_formats,
            output_dir=resolved_output_dir,
        )
        request = GenerationRequest(image_path=image_path, config=config)
        result = deps.processor.process_generate(request, settings)
        deps.output_adapter.process_result(result)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import json as _json
        import sys
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None


app.command()(info)
app.command()(dump_config)
app.command()(dump_templates)
app.command()(list_backends)
app.command()(show)
app.command()(version)
