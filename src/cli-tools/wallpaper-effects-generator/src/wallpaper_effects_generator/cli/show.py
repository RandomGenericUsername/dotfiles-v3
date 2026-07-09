from __future__ import annotations

import typer

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.ports.output import OutputPort

show_app = typer.Typer(
    name="show",
    help="Display catalog entries",
)


def _get_output_adapter(ctx: typer.Context) -> OutputPort:
    return ctx.obj["deps"].output_adapter


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
