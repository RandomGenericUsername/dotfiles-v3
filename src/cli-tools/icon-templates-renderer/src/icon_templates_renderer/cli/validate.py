from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.cli._helpers import build_overrides
from icon_templates_renderer.cli.options import (
    COLOR_SCHEME_OPT,
    ICON_OPT,
    TEMPLATE_DIR_OPT,
)
from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import PathOverrides, ValidateRequest
from icon_templates_renderer.factory import CliDependencies


def validate_command(
    ctx: typer.Context,
    yaml_file: Path = typer.Argument(..., help="Path to the icons YAML file"),  # noqa: B008
    icon: str | None = ICON_OPT,
    template_dir: Path | None = TEMPLATE_DIR_OPT,
    color_scheme: Path | None = COLOR_SCHEME_OPT,
) -> None:
    """Validate the YAML and all referenced files without rendering."""
    deps: CliDependencies = ctx.obj["deps"]
    overrides: PathOverrides = build_overrides(template_dir, color_scheme, None)
    request = ValidateRequest(
        yaml_path=Path(yaml_file).resolve(),
        icon=icon,
        overrides=overrides,
    )
    try:
        result = deps.icon_renderer.validate(request)
        deps.output_adapter.validate_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
