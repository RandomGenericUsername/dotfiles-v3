from __future__ import annotations

import typer

from wallpaper_effects_generator.ports.output import OutputPort
from wallpaper_effects_generator.ports.version_provider import VersionProviderPort


def version_command(
    ctx: typer.Context,
    version_provider: VersionProviderPort,
    output_adapter: OutputPort,
) -> None:
    ver = version_provider.get_version()
    output_adapter.message(f"wallpaper-effects-generator {ver}")
