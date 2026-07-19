from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.settings.settings_serializer import SettingsSerializer
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ConfigResolutionError, OutputWriteError
from color_scheme_generator.domain.models import GenerationResult
from color_scheme_generator.factory import CliDependencies


def dump_config(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),  # noqa: B008
    overwrite: bool = typer.Option(False, "--overwrite", "-w", help="Overwrite existing file"),  # noqa: B008
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    config_resolver: AssembledConfigResolver | None = deps.config_resolver

    if config_resolver is None:
        msg = "Config resolver not available"
        raise ConfigResolutionError(key="settings.toml", reason=msg)

    try:
        settings = config_resolver.resolve()
    except ConfigResolutionError:
        raise

    serializer = SettingsSerializer()
    toml_str = serializer.serialize(settings)

    if output is None:
        print(toml_str)
        return

    if output.exists() and not overwrite:
        msg = f"File {output} already exists. Use --overwrite to overwrite."
        raise OutputWriteError(path=output, reason=msg)

    try:
        output.write_text(toml_str)
    except (OSError, PermissionError) as e:
        raise OutputWriteError(path=output, reason=str(e)) from e

    adapter = deps.output_adapter
    if adapter is not None:
        adapter.process_result(
            GenerationResult(
                success=True,
                color_scheme=None,
                output_files=(output.resolve(),),
                backend=Backend.CUSTOM,
                stderr="",
                return_code=0,
                duration=0.0,
            )
        )
