from __future__ import annotations

from pathlib import Path

import typer

from wallpaper_effects_generator.cli.options import EFFECTS_OPT
from wallpaper_effects_generator.domain.enums import CatalogQuery, OutputFormat
from wallpaper_effects_generator.factory import create_output_adapter
from wallpaper_effects_generator.ports.output import OutputPort

show_app = typer.Typer(
    name="show",
    help="Display catalog entries",
)


@show_app.callback()
def show_callback(
    ctx: typer.Context,
    effects: Path | None = EFFECTS_OPT,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["effects"] = str(effects) if effects else None


def _get_output_adapter(ctx: typer.Context) -> OutputPort:
    deps = ctx.obj["deps"]
    if deps.output_adapter is not None:
        return deps.output_adapter
    adapter = create_output_adapter(OutputFormat.JSON)
    deps.output_adapter = adapter
    return adapter


def _load_catalog(ctx: typer.Context) -> object:
    deps = ctx.obj["deps"]
    try:
        return deps.catalog_cache.get(ctx.obj.get("effects"))
    except Exception as exc:
        output_adapter = _get_output_adapter(ctx)
        output_adapter.error(exc)
        raise typer.Exit(1) from exc


@show_app.command()
def effects(ctx: typer.Context) -> None:
    output_adapter = _get_output_adapter(ctx)
    catalog = _load_catalog(ctx)
    output_adapter.catalog_list(catalog, CatalogQuery.EFFECT)


@show_app.command()
def composites(ctx: typer.Context) -> None:
    output_adapter = _get_output_adapter(ctx)
    catalog = _load_catalog(ctx)
    output_adapter.catalog_list(catalog, CatalogQuery.COMPOSITE)


@show_app.command()
def presets(ctx: typer.Context) -> None:
    output_adapter = _get_output_adapter(ctx)
    catalog = _load_catalog(ctx)
    output_adapter.catalog_list(catalog, CatalogQuery.PRESET)


@show_app.command(name="all")
def show_all(ctx: typer.Context) -> None:
    output_adapter = _get_output_adapter(ctx)
    catalog = _load_catalog(ctx)
    output_adapter.catalog_list(catalog, CatalogQuery.ALL)
