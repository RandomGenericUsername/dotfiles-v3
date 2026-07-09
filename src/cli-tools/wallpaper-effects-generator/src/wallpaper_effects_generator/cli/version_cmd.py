from __future__ import annotations

import typer

from wallpaper_effects_generator.factory import create_output_adapter
from wallpaper_effects_generator.ports.version_provider import VersionProviderPort


def version_command(
    ctx: typer.Context,
    version_provider: VersionProviderPort,
) -> None:
    output_adapter = create_output_adapter(ctx.obj["output_format"])
    ver = version_provider.get_version()
    output_adapter.message(f"wallpaper-effects-generator {ver}")
