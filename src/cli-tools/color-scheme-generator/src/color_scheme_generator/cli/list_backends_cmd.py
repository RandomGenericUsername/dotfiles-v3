from __future__ import annotations

import json

import typer

from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import BackendDefinition
from color_scheme_generator.factory import CliDependencies


def _get_backend_info(
    backend: Backend,
    registry: CliDependencies.backend_registry,
    catalog: dict[Backend, BackendDefinition] | None,
) -> dict:
    generator = registry.get(backend)
    available = generator.is_available() if generator is not None else False

    info: dict = {
        "name": backend.value,
        "available": available,
        "image_available": None,
    }

    if catalog is not None and backend in catalog:
        defn = catalog[backend]
        info["display_name"] = defn.display_name
        info["description"] = defn.description
        info["parameters"] = [
            {
                "name": p.name,
                "type": p.type_,
                "default": p.default,
                "choices": list(p.choices) if p.choices else None,
            }
            for p in defn.parameters
        ]
    else:
        info["display_name"] = backend.value.title()
        info["description"] = ""
        info["parameters"] = []

    return info


def list_backends(ctx: typer.Context) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    backend_catalog_loader: YamlBackendCatalogLoader | None = deps.backend_catalog_loader

    catalog: dict[Backend, BackendDefinition] | None = None
    if backend_catalog_loader is not None:
        try:
            catalog = backend_catalog_loader.load()
        except ConfigResolutionError:
            pass

    backends_list = [_get_backend_info(b, deps.backend_registry, catalog) for b in Backend]

    adapter = deps.output_adapter

    if isinstance(adapter, JsonOutput):
        print(json.dumps({"backends": backends_list}, indent=2))
    elif isinstance(adapter, RichOutput):
        from rich.table import Table

        for b in backends_list:
            table = Table(title=b.get("display_name", b["name"]), box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            table.add_row("Name", b["name"])
            table.add_row("Description", b.get("description", ""))
            table.add_row("Available", "yes" if b["available"] else "no")
            img = "not implemented" if b["image_available"] is None else str(b["image_available"])
            table.add_row("Image", img)

            if b.get("parameters"):
                params_table = Table(title="Parameters", box=None)
                params_table.add_column("Name", style="cyan")
                params_table.add_column("Type")
                params_table.add_column("Default")
                params_table.add_column("Choices")
                for p in b["parameters"]:
                    choices = ", ".join(p["choices"]) if p.get("choices") else ""
                    default = p.get("default", "")
                    params_table.add_row(p["name"], p["type"], str(default), choices)
                adapter._console.print(params_table)
                adapter._console.print()

            adapter._console.print(table)
            adapter._console.print()
    elif isinstance(adapter, PlainOutput):
        for b in backends_list:
            desc = b.get("description", "")
            avail = "yes" if b["available"] else "no"
            print(f"{b['name']} - {desc}")
            print(f"  Available: {avail}")
            print("  Image: not implemented")
            if b.get("parameters"):
                print("  Parameters:")
                for p in b["parameters"]:
                    choices = f", choices: {', '.join(p['choices'])}" if p.get("choices") else ""
                    print(
                        f"    {p['name']} ({p['type']}, default: {p.get('default', '')}{choices})"
                    )
