from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

import typer


def version(ctx: typer.Context) -> None:
    try:
        ver = _pkg_version("color-scheme-generator")
    except PackageNotFoundError:
        msg = json.dumps({"error": "color-scheme-generator package not installed"})
        print(msg, file=sys.stderr)
        raise typer.Exit(code=1) from None

    ctx.obj["deps"].output_adapter.version_info(ver)
