from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

import typer

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.output import OutputPort


def dump_effects_command(
    effects_path: str | None,
    output_adapter: OutputPort,
    effect_loader: EffectLoaderPort,
    output_path: Path | None = None,
) -> None:
    if output_path:
        content = (
            resource_files("wallpaper_effects_generator.defaults")
            .joinpath("effects.yaml")
            .read_text()
        )
        output_path.write_text(content)
        typer.echo(f"Default effects written to {output_path}")
        return

    catalog = effect_loader.load(
        path=Path(effects_path) if effects_path else None,
    )
    output_adapter.catalog_list(catalog, CatalogQuery.EFFECT)
