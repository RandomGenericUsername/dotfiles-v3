from __future__ import annotations

import json

import typer

from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput
from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.factory import CliDependencies


def _check_backend_availability(
    backend: Backend,
    backend_registry: CliDependencies.backend_registry,
) -> bool:
    generator = backend_registry.get(backend)
    if generator is None:
        return False
    return generator.is_available()


def _get_config_source(resolved_path_str: str) -> str:
    if resolved_path_str.startswith("/"):
        return "xdg"
    return "default"


def info(ctx: typer.Context) -> None:
    deps: CliDependencies = ctx.obj["deps"]

    config_resolver: AssembledConfigResolver | None = deps.config_resolver
    template_dir_resolver: TemplateDirResolver | None = deps.template_dir_resolver
    backend_catalog_loader: YamlBackendCatalogLoader | None = deps.backend_catalog_loader

    config_path = "not resolved"
    config_source = "none"
    applied_overrides: list[dict[str, str]] = []
    runtime_mode = "unknown"
    container_engine = "unknown"
    templates_directory = "not resolved"
    backends: dict[str, dict[str, bool | None]] = {}

    if config_resolver is not None:
        try:
            settings = config_resolver.resolve()
            runtime_mode = settings.runtime.mode.value
            container_engine = settings.runtime.engine.value
        except ConfigResolutionError:
            pass
        if config_resolver.last_result is not None:
            config_path = str(config_resolver.last_result.resolved_path)
            config_source = _get_config_source(config_path)
            applied_overrides = [
                {
                    "field_path": o.field_path,
                    "raw_value": o.raw_value,
                    "coerced_value": o.coerced_value,
                    "source": o.source,
                }
                for o in config_resolver.last_result.applied_overrides
            ]

    if template_dir_resolver is not None:
        try:
            templates_directory = str(template_dir_resolver.resolve())
        except ConfigResolutionError:
            pass

    for backend in Backend:
        backends[backend.value] = {
            "available": _check_backend_availability(backend, deps.backend_registry),
        }

    if backend_catalog_loader is not None:
        try:
            catalog = backend_catalog_loader.load()
            for b in catalog:
                if b.value in backends:
                    backends[b.value]["description"] = catalog[b].description
        except ConfigResolutionError:
            pass

    adapter = deps.output_adapter

    if isinstance(adapter, JsonOutput):
        payload = {
            "config_path": config_path,
            "config_source": config_source,
            "applied_overrides": applied_overrides,
            "runtime_mode": runtime_mode,
            "container_engine": container_engine,
            "templates_directory": templates_directory,
            "backends": backends,
        }
        print(json.dumps(payload, indent=2))
    elif isinstance(adapter, RichOutput):
        from rich.table import Table

        table = Table(title="Configuration Info", box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Config path", config_path)
        table.add_row("Config source", config_source)
        table.add_row("Runtime mode", runtime_mode)
        table.add_row("Container engine", container_engine)
        table.add_row("Templates directory", templates_directory)
        adapter._console.print()
        adapter._console.print(table)
        adapter._console.print()

        if applied_overrides:
            overrides_table = Table(title="Applied Overrides", box=None)
            overrides_table.add_column("Field", style="cyan")
            overrides_table.add_column("Value")
            overrides_table.add_column("Source")
            for o in applied_overrides:
                overrides_table.add_row(o["field_path"], o["coerced_value"], o["source"])
            adapter._console.print(overrides_table)
            adapter._console.print()

        backends_table = Table(title="Backends", box=None)
        backends_table.add_column("Backend", style="cyan")
        backends_table.add_column("Available")
        for name, info in backends.items():
            available = "yes" if info.get("available") else "no"
            backends_table.add_row(name, available)
        adapter._console.print(backends_table)
        adapter._console.print()
    elif isinstance(adapter, PlainOutput):
        print(f"Config path: {config_path}")
        print(f"Config source: {config_source}")
        print(f"Runtime mode: {runtime_mode}")
        print(f"Container engine: {container_engine}")
        print(f"Templates directory: {templates_directory}")
        print("Backends:")
        for name, info in backends.items():
            avail = "available" if info.get("available") else "not available"
            print(f"  {name}: {avail}")
        if applied_overrides:
            print("Overrides:")
            for o in applied_overrides:
                print(
                    f"  {o['field_path']} = {o['coerced_value']}"
                    f" (source: {o['source']}, coerced: {o['coerced_value']})"
                )
