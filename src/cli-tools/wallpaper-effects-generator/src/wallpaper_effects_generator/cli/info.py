from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.adapters.catalog_cache import CatalogCache
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.output import OutputPort


def info_command(
    config_path: str | None,
    effects_path: str | None,
    output_adapter: OutputPort,
    config_resolver: ConfigResolverPort,
    effect_loader: EffectLoaderPort,
    catalog_cache: CatalogCache | None = None,
    cli_overrides: dict[str, str] | None = None,
) -> None:
    settings = config_resolver.resolve(
        explicit_path=Path(config_path) if config_path else None,
        cli_overrides=cli_overrides,
    )
    settings_source = config_resolver.get_resolved_path()

    if catalog_cache:
        effects = catalog_cache.get(effects_path)
    else:
        effects = effect_loader.load(
            path=Path(effects_path) if effects_path else None,
        )
    effects_source = effect_loader.get_resolved_path()

    sources: list[str] = []
    if settings_source:
        sources.append(f"settings: {settings_source}")
    if effects_source:
        sources.append(f"effects: {effects_source}")
    output_adapter.config_info(settings, effects, sources)
