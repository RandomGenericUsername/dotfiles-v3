from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.domain.enums import OutputFormat, Verbosity
from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import TemplateSetPlaceholderRequest
from icon_templates_renderer.factory import CliDependencies, create_output_adapter

template_app = typer.Typer(help="Analyze and rewrite template paint attributes (placeholders).")


@template_app.command("analyze")
def analyze_command(
    ctx: typer.Context,
    template_file: Path = typer.Argument(..., help="Path to the template SVG file"),  # noqa: B008
    json: bool = typer.Option(  # noqa: B008
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """Report the mode, shapes, and paint attributes of a template file."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        if json:
            verbosity: Verbosity = ctx.obj.get("verbosity", Verbosity.NORMAL)
            deps.output_adapter = create_output_adapter(OutputFormat.JSON, verbosity=verbosity)
        result = deps.template_writer.analyze(Path(template_file).resolve())
        deps.output_adapter.template_analysis_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None


@template_app.command("scan")
def scan_command(
    ctx: typer.Context,
    template_dir: Path = typer.Argument(..., help="Template root directory to scan"),  # noqa: B008
    json: bool = typer.Option(  # noqa: B008
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """Classify every template SVG under a root as templated or bare."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        if json:
            verbosity: Verbosity = ctx.obj.get("verbosity", Verbosity.NORMAL)
            deps.output_adapter = create_output_adapter(OutputFormat.JSON, verbosity=verbosity)
        entries = deps.template_writer.scan(Path(template_dir).resolve())
        deps.output_adapter.template_scan_result(entries)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None


@template_app.command("set-placeholder")
def set_placeholder_command(
    ctx: typer.Context,
    template_file: Path = typer.Argument(..., help="Path to the template SVG file"),  # noqa: B008
    shape: int = typer.Option(..., "--shape", help="Shape id (1-based document order)"),  # noqa: B008
    name: str = typer.Option(..., "--name", help="Placeholder name (e.g. COLOR_ACCENT)"),  # noqa: B008
) -> None:
    """Rewrite one shape's paint attribute to ``{{NAME}}``."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        path = Path(template_file).resolve()
        request = TemplateSetPlaceholderRequest(path=path, shape_id=shape, name=name)
        result = deps.template_writer.set_placeholder(request)
        if ctx.obj.get("output_format", OutputFormat.PLAIN) is not OutputFormat.JSON:
            deps.output_adapter.message(f"Set shape {shape} paint = {{{{{name}}}}}.")
        deps.output_adapter.template_analysis_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
