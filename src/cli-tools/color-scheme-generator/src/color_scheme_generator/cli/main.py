from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.cli.dump_config_cmd import dump_config
from color_scheme_generator.cli.dump_templates_cmd import dump_templates
from color_scheme_generator.cli.info_cmd import info
from color_scheme_generator.cli.list_backends_cmd import list_backends
from color_scheme_generator.cli.show import show
from color_scheme_generator.cli.version_cmd import version
from color_scheme_generator.domain.enums import Backend, ContainerEngine, OutputFormat, RuntimeMode
from color_scheme_generator.domain.exceptions import ColorSchemeError
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
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    config = GeneratorConfig(
        backend=Backend.CUSTOM,
        params={},
        formats=(),
        output_dir=Path("/tmp/color-scheme"),
    )
    request = GenerationRequest(image_path=image_path, config=config)
    try:
        settings = AppSettings(
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
