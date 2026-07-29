from __future__ import annotations

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
