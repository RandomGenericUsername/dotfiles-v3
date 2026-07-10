from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

import typer

from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.output import OutputPort


def dump_config_command(
    config_path: str | None,
    output_adapter: OutputPort,
    config_resolver: ConfigResolverPort,
    output_path: Path | None = None,
) -> None:
    if output_path:
        content = (
            resource_files("wallpaper_effects_generator.defaults")
            .joinpath("settings.toml")
            .read_text()
        )
        output_path.write_text(content)
        typer.echo(f"Default config written to {output_path}")
        return

    settings = config_resolver.resolve(
        explicit_path=Path(config_path) if config_path else None,
    )
    settings_source = config_resolver.get_resolved_path()
    sources: list[str] = []
    if settings_source:
        sources.append(f"settings: {settings_source}")

    output_adapter.dump_config(settings, sources)
