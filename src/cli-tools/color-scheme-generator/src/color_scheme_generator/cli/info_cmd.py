from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import typer

from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import AppSettings
from color_scheme_generator.factory import CliDependencies


def _check_backend_availability(
    backend: Backend,
    backend_registry: CliDependencies.backend_registry,
) -> bool:
    generator = backend_registry.get(backend)
    if generator is None:
        return False
    return generator.is_available()


def info(ctx: typer.Context) -> None:
    deps: CliDependencies = ctx.obj["deps"]

    config_resolver: AssembledConfigResolver | None = deps.config_resolver
    template_dir_resolver: TemplateDirResolver | None = deps.template_dir_resolver
    backend_catalog_loader: YamlBackendCatalogLoader | None = deps.backend_catalog_loader

    settings: AppSettings | None = None
    sources: list[str] = []

    if config_resolver is not None:
        try:
            config_path = ctx.obj.get("config_path")
            cli_overrides = ctx.obj.get("cli_overrides", {})
            settings = config_resolver.resolve(
                explicit_path=config_path, cli_overrides=cli_overrides
            )
        except ConfigResolutionError as exc:
            typer.echo(f"Warning: {exc}", err=True)

        if config_resolver.last_result is not None:
            sources.append(
                f"settings: {config_resolver.last_result.resolved_path}"
            )

    if template_dir_resolver is not None:
        try:
            settings_dir = settings.template.templates_dir if settings else None
            sources.append(
                f"templates: {template_dir_resolver.resolve(settings_dir=settings_dir)}"
            )
        except ConfigResolutionError:
            pass

    if backend_catalog_loader is not None:
        try:
            catalog = backend_catalog_loader.load()
            for b in Backend:
                if b.value in catalog:
                    sources.append(
                        f"catalog: {catalog[b].description}"
                    )
                    break
        except ConfigResolutionError:
            pass

    backends: dict[str, dict[str, bool | str | None]] = {}
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
    adapter.config_info(settings, backends, sources, catalog if backend_catalog_loader else None)
