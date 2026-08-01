from __future__ import annotations

import typer

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

    all_unavailable = all(not b["available"] for b in backends_list)
    hint = (
        "No backends are available on the host. "
        "Try `csg install` to build container images, "
        "or install a backend binary (wal, wallust) locally."
    ) if all_unavailable else ""

    deps.output_adapter.backends_catalog(backends_list, hint=hint)
