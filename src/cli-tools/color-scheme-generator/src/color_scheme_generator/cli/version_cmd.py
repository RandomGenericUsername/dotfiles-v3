from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

import typer

from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput


def version(ctx: typer.Context) -> None:
    try:
        ver = _pkg_version("color-scheme-generator")
    except PackageNotFoundError:
        msg = json.dumps({"error": "color-scheme-generator package not installed"})
        print(msg, file=sys.stderr)
        raise typer.Exit(code=1) from None

    adapter = ctx.obj["deps"].output_adapter

    if isinstance(adapter, JsonOutput):
        print(json.dumps({"version": ver}))
    elif isinstance(adapter, RichOutput):
        adapter._console.print(f"[bold]color-scheme-generator[/bold] v{ver}")
    elif isinstance(adapter, PlainOutput):
        print(f"color-scheme-generator {ver}")
