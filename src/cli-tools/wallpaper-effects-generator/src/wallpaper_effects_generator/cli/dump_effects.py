from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.output import OutputPort


def dump_effects_command(
    effects_path: str | None,
    output_adapter: OutputPort,
    effect_loader: EffectLoaderPort,
) -> None:
    catalog = effect_loader.load(
        path=Path(effects_path) if effects_path else None,
    )
    output_adapter.catalog_list(catalog, CatalogQuery.EFFECT)
