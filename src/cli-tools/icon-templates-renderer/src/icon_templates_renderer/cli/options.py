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

PLACEHOLDER_OPT: str = typer.Option(
    ...,
    "--placeholder",
    help="Placeholder name to retarget (e.g. COLOR_ACCENT)",
)

TOKEN_OPT: str = typer.Option(
    ...,
    "--token",
    help="Palette token or #rrggbb literal to map the placeholder to",
)

VARIANT_OPT: str | None = typer.Option(
    None,
    "--variant",
    help="Limit the edit to a single variant (creates an override)",
)

DRY_RUN_OPT: bool = typer.Option(
    False,
    "--dry-run",
    help="Compute the edit without writing anything",
)

DIFF_OPT: bool = typer.Option(
    False,
    "--diff",
    help="Print the unified diff of the edit",
)

ICONS_MANIFEST_OPT: Path | None = typer.Option(
    None,
    "--icons",
    help="Path to the icons manifest (defaults to icons.yaml next to the file)",
)
