from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode
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


def show(
    ctx: typer.Context,
    image_path: Path = typer.Argument(..., help="Path to the input image file"),  # noqa: B008
) -> None:
    deps = ctx.obj["deps"]
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
