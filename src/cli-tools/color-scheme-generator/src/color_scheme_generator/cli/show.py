from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import AppSettings, GenerationRequest, GeneratorConfig


def show(
    ctx: typer.Context,
    image_path: Path = typer.Argument(..., exists=False),  # noqa: B008
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
        result = deps.processor.process_show(request, AppSettings())
        deps.output_adapter.palette_display(result.color_scheme)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
