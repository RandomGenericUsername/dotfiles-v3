from __future__ import annotations

from pathlib import Path

import typer

from wallpaper_effects_generator.domain.enums import ContainerEngine, RuntimeMode

RUNTIME_OPT: RuntimeMode | None = typer.Option(
    None,
    "--runtime",
    "-r",
    help="Execution runtime mode",
    case_sensitive=False,
)

ENGINE_OPT: ContainerEngine | None = typer.Option(
    None,
    "--container-engine",
    help="Container engine to use (only for container runtime)",
    case_sensitive=False,
)

CONFIG_OPT: Path | None = typer.Option(
    None,
    "--config",
    "-c",
    help="Path to settings.toml config file",
    exists=True,
    file_okay=True,
    dir_okay=False,
    readable=True,
    resolve_path=True,
)

EFFECTS_OPT: Path | None = typer.Option(
    None,
    "--effects",
    "-e",
    help="Path to effects.yaml file",
    exists=True,
    file_okay=True,
    dir_okay=False,
    readable=True,
    resolve_path=True,
)

SOURCE_ROOT_OPT: Path | None = typer.Option(
    None,
    "--source-root",
    envvar="WEG_SOURCE_ROOT",
    help="Source repo root used as the container image build context. "
    "Required when the CLI is not running from a source checkout.",
    exists=True,
    file_okay=False,
    dir_okay=True,
    resolve_path=True,
)
