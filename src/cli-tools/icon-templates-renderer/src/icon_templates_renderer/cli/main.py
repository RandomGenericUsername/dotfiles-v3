from __future__ import annotations

import logging

import typer

from icon_templates_renderer.cli.list_cmd import list_command
from icon_templates_renderer.cli.render import render_command
from icon_templates_renderer.cli.validate import validate_command
from icon_templates_renderer.domain.enums import OutputFormat, Verbosity
from icon_templates_renderer.factory import build_deps, create_output_adapter

app = typer.Typer(
    help=(
        "Render SVG icon templates with color scheme values.\n\n"
        "Paths resolve in this order: CLI flag > ICON_RENDERER__<SECTION>__<KEY> env "
        "override > settings.toml field > discovery.\n\n"
        "Templates discovery: ./templates/ dirs (up to 3 levels) then "
        "XDG ~/.config/itr/templates.\n"
        "Color scheme discovery: ./colors.yaml (up to 3 levels) then "
        "XDG ~/.config/itr/colors.yaml.\n"
        "Settings discovery: ./settings.toml (up to 2 levels), XDG ~/.config/itr/settings.toml, "
        "then bundled defaults. Use --config to select a settings.toml explicitly.\n"
        "Env overrides: ICON_RENDERER__OUTPUT__OUTPUT_DIR, ICON_RENDERER__OUTPUT__VERBOSITY, "
        "ICON_RENDERER__TEMPLATES__DIR, ICON_RENDERER__COLOR_SCHEME__PATH, "
        "ICON_RENDERER_CONFIG_FILE_PATH."
    )
)


@app.callback()
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(  # noqa: B008
        OutputFormat.PLAIN,
        "--output-format",
        help="Output format for command results",
        case_sensitive=False,
    ),
    verbose: int = typer.Option(  # noqa: B008
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (use -v, -vv, -vvv)",
    ),
    quiet: bool = typer.Option(  # noqa: B008
        False,
        "--quiet",
        "-q",
        help="Suppress all non-error output",
    ),
) -> None:
    if quiet:
        verbosity = Verbosity.QUIET
    elif verbose > 0:
        match verbose:
            case 1:
                verbosity = Verbosity.VERBOSE
            case _:
                verbosity = Verbosity.DEBUG
    else:
        verbosity = Verbosity.NORMAL

    log_level = {
        Verbosity.QUIET: logging.ERROR,
        Verbosity.NORMAL: logging.WARNING,
        Verbosity.VERBOSE: logging.INFO,
        Verbosity.DEBUG: logging.DEBUG,
    }[verbosity]
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    deps = build_deps()
    deps.output_adapter = create_output_adapter(output_format, verbosity=verbosity)
    ctx.obj = {
        "deps": deps,
        "output_format": output_format,
        "verbosity": verbosity,
    }


app.command("render", help="Render SVG icons from templates using a color scheme")(render_command)
app.command("list", help="List icon groups and their variants defined in a YAML file")(list_command)
app.command("validate", help="Validate the YAML and all referenced files without rendering")(
    validate_command
)
