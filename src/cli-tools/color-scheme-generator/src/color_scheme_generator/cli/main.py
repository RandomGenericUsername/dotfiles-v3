from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import (
    AppSettings,
    GenerationRequest,
    GeneratorConfig,
)
from color_scheme_generator.cli.show import show
from color_scheme_generator.cli.version_cmd import version
from color_scheme_generator.factory import CliDependencies, create_backend_registry

app = typer.Typer()


def build_deps() -> CliDependencies:
    registry = create_backend_registry()
    return CliDependencies(
        backend_registry=registry,
        output_adapter=JsonOutput(),
        processor=LocalProcessor(registry),
    )


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    ctx.obj = {"deps": build_deps()}


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
        result = deps.processor.process_generate(request, AppSettings())
        deps.output_adapter.process_result(result)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import sys
        import json as _json
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None


app.command()(show)
app.command()(version)
