from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.output import OutputPort


def dump_config_command(
    config_path: str | None,
    output_adapter: OutputPort,
    config_resolver: ConfigResolverPort,
) -> None:
    settings = config_resolver.resolve(
        explicit_path=Path(config_path) if config_path else None,
    )
    settings_source = config_resolver.get_resolved_path()
    sources: list[str] = []
    if settings_source:
        sources.append(f"settings: {settings_source}")

    output_adapter.dump_config(settings, sources)
