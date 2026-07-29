from __future__ import annotations

from pathlib import Path

import typer

from color_scheme_generator.domain.enums import ContainerEngine, RuntimeMode

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
    help="Path to settings.toml config file",
    exists=True,
    file_okay=True,
    dir_okay=False,
    readable=True,
    resolve_path=True,
)

TEMPLATES_DIR_OPT: Path | None = typer.Option(
    None,
    "--templates-dir",
    help="Path to directory containing .j2 template files",
    exists=True,
    file_okay=False,
    dir_okay=True,
    readable=True,
    resolve_path=True,
)
