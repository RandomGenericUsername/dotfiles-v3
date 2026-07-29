from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

import typer

from color_scheme_generator.domain.exceptions import OutputWriteError
from color_scheme_generator.factory import CliDependencies


def dump_config(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path or directory (appends settings.toml)"),  # noqa: B008
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    content = (
        resource_files("color_scheme_generator.defaults")
        .joinpath("settings.toml")
        .read_text()
    )

    if output is None:
        print(content, end="")
        return

    output_path = output
    if output_path.suffix != ".toml":
        output_path = output_path / "settings.toml"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
    except (OSError, PermissionError) as e:
        raise OutputWriteError(path=output_path, reason=str(e)) from e

    adapter = deps.output_adapter
    if adapter is not None:
        adapter.message(f"Default config written to {output_path.resolve()}")
