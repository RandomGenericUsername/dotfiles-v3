"""Shared option definitions for the dotfiles-provision CLI.

Module-level importable constants (no eager ``create_renderer``) so the
composition root in ``main.py`` stays the single place that wires renderers
and dependencies. Only ``typer`` and ``cli_output`` are imported — both are
declared package dependencies and layering-guard-allowed roots.
"""

from __future__ import annotations

import typer
from cli_output.domain.enums import OutputFormat

OUTPUT_FORMAT_OPT: OutputFormat = typer.Option(
    OutputFormat.JSON,
    "--output-format",
    help="Output format for command results",
    case_sensitive=False,
)

CHECK_OPT: bool = typer.Option(
    False,
    "--check",
    help="Dry run: complete cleanly with no mutation",
)

BECOME_PASSWORD_OPT: str | None = typer.Option(
    None,
    "--become-password",
    help="Sudo password for become:true plays (packages/bootstrap); input is hidden",
    hide_input=True,
)
