from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.cli._helpers import build_overrides
from icon_templates_renderer.cli.options import ICON_OPT, TEMPLATE_DIR_OPT
from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import ListRequest, PathOverrides
from icon_templates_renderer.factory import CliDependencies


def list_command(
    ctx: typer.Context,
    yaml_file: Path = typer.Argument(..., help="Path to the icons YAML file"),  # noqa: B008
    icon: str | None = ICON_OPT,
    template_dir: Path | None = TEMPLATE_DIR_OPT,
) -> None:
    """List icon groups and their variants defined in a YAML file."""
    deps: CliDependencies = ctx.obj["deps"]
    overrides: PathOverrides = build_overrides(template_dir, None, None)
    request = ListRequest(
        yaml_path=Path(yaml_file).resolve(),
        icon=icon,
        overrides=overrides,
    )
    try:
        result = deps.icon_renderer.list(request)
        deps.output_adapter.list_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
