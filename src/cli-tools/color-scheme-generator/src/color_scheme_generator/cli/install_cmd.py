from __future__ import annotations

import json
import logging
from importlib.resources import files as pkg_files

import typer

from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput
from color_scheme_generator.domain.enums import Backend, ContainerEngine
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import AppSettings
from color_scheme_generator.factory import CliDependencies, create_container_engine

log = logging.getLogger(__name__)


def _get_container_engine(
    deps: CliDependencies,
    engine: ContainerEngine,
) -> CliDependencies.container_engine:
    return create_container_engine(engine)


def _build_image_name(settings: AppSettings, backend: Backend) -> str:
    prefix = settings.container.image_prefix
    return f"{prefix}color-scheme-{backend.image_suffix}:{settings.container.image_tag}"


def _resolve_dockerfile(backend: Backend) -> str:
    return str(
        pkg_files("color_scheme_generator.adapters.docker").joinpath(
            f"Dockerfile.{backend.image_suffix}"
        )
    )


def install(
    ctx: typer.Context,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to build"),  # noqa: B008
    engine: ContainerEngine = typer.Option(  # noqa: B008
        ContainerEngine.DOCKER, "--engine", help="Container engine", case_sensitive=False
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without building"),  # noqa: B008
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve()
        container_engine = _get_container_engine(deps, engine)
        target_backends = backend or list(Backend)
        results: list[dict[str, str]] = []
        for b in target_backends:
            image = _build_image_name(settings, b)
            if dry_run:
                results.append({
                    "backend": b.value,
                    "image": image,
                    "status": "would-build",
                })
            else:
                from oci_runtime.domain.types import BuildContext

                dockerfile = _resolve_dockerfile(b)
                context = BuildContext(build_file_path=dockerfile)
                container_engine.build_image(context, image)
                results.append({
                    "backend": b.value,
                    "image": image,
                    "status": "built",
                })

        adapter = deps.output_adapter
        if isinstance(adapter, JsonOutput):
            print(json.dumps({"install": results}, indent=2))
        elif isinstance(adapter, RichOutput):
            from rich.table import Table

            table = Table(title="Install Results", box=None)
            table.add_column("Backend", style="cyan")
            table.add_column("Image")
            table.add_column("Status")
            for r in results:
                table.add_row(r["backend"], r["image"], r["status"])
            adapter._console.print()
            adapter._console.print(table)
            adapter._console.print()
        elif isinstance(adapter, PlainOutput):
            for r in results:
                print(f"{r['backend']}: {r['image']} [{r['status']}]")
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
