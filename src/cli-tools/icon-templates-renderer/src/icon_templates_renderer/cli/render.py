from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.cli._helpers import resolve_roots
from icon_templates_renderer.cli.options import (
    COLOR_SCHEME_OPT,
    CONFIG_OPT,
    ICON_OPT,
    OUTPUT_DIR_OPT,
    TEMPLATE_DIR_OPT,
    UNSAFE_OPT,
)
from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import RenderRequest, ResolvedRoots
from icon_templates_renderer.factory import CliDependencies


def render_command(
    ctx: typer.Context,
    yaml_file: Path = typer.Argument(..., help="Path to the icons YAML file"),  # noqa: B008
    icon: str | None = ICON_OPT,
    unsafe: bool = UNSAFE_OPT,
    template_dir: Path | None = TEMPLATE_DIR_OPT,
    color_scheme: Path | None = COLOR_SCHEME_OPT,
    output_dir: Path | None = OUTPUT_DIR_OPT,
    config: Path | None = CONFIG_OPT,
) -> None:
    """Render SVG icons from templates using a color scheme."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        roots: ResolvedRoots = resolve_roots(
            deps,
            config,
            template_dir,
            color_scheme,
            output_dir,
            required=True,
        )
        request = RenderRequest(
            yaml_path=Path(yaml_file).resolve(),
            icon=icon,
            unsafe=unsafe or None,
            roots=roots,
        )
        result = deps.icon_renderer.render(request)
        deps.output_adapter.render_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
