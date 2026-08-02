from __future__ import annotations

import logging

import typer

from icon_templates_renderer.cli.list_cmd import list_command
from icon_templates_renderer.cli.render import render_command
from icon_templates_renderer.cli.validate import validate_command
from icon_templates_renderer.domain.enums import OutputFormat, Verbosity
from icon_templates_renderer.factory import CliDependencies, create_output_adapter

app = typer.Typer(help="Render SVG icon templates with color scheme values")


def build_deps() -> CliDependencies:
    deps = CliDependencies()
    deps.config_resolver = None
    return deps


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
