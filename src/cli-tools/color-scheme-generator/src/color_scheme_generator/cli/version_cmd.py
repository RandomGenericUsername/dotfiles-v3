from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

import typer


def version() -> None:
    try:
        ver = _pkg_version("color-scheme-generator")
        print(json.dumps({"version": ver}))
    except PackageNotFoundError:
        print(json.dumps({"error": "color-scheme-generator package not installed"}), file=sys.stderr)
        raise typer.Exit(code=1) from None
