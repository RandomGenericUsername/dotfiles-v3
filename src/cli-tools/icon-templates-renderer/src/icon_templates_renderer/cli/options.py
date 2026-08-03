from __future__ import annotations

from pathlib import Path

import typer

ICON_OPT: str | None = typer.Option(
    None,
    "--icon",
    help="Operate on a single icon group",
)

UNSAFE_OPT: bool = typer.Option(
    False,
    "--unsafe",
    help="Allow unresolved placeholders",
)

TEMPLATE_DIR_OPT: Path | None = typer.Option(
    None,
    "--template-dir",
    help="Override template root directory for all groups",
)

COLOR_SCHEME_OPT: Path | None = typer.Option(
    None,
    "--color-scheme",
    help="Override the color scheme file for all groups",
)

OUTPUT_DIR_OPT: Path | None = typer.Option(
    None,
    "--output-dir",
    help="Override output root directory for all groups",
)

CONFIG_OPT: Path | None = typer.Option(
    None,
    "--config",
    help="Path to the settings.toml file (defaults to discovery + bundled defaults)",
)
