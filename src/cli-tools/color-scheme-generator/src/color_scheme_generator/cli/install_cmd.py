from __future__ import annotations

import json
import logging
from importlib.resources import files as pkg_files
from pathlib import Path

import typer
from oci_runtime import engine_qualified_image

from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput
from color_scheme_generator.cli._helpers import build_image_name
from color_scheme_generator.cli.options import CONFIG_OPT, ENGINE_OPT
from color_scheme_generator.domain.enums import Backend, ContainerEngine
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.factory import CliDependencies, create_container_engine

log = logging.getLogger(__name__)


def _resolve_dockerfile(backend: Backend) -> Path:
    return Path(
        str(
            pkg_files("color_scheme_generator.adapters.docker").joinpath(
                f"Dockerfile.{backend.image_suffix}"
            )
        )
    )


def _find_project_root(docker_dir: Path) -> Path | None:
    for parent in docker_dir.parents:
        if (parent / "pyproject.toml").exists():
            for ancestor in parent.parents:
                if (ancestor / "shared" / "config-assembler-engine").exists():
                    return ancestor
            return parent
    return None


def install(
    ctx: typer.Context,
    config_path: Path | None = CONFIG_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to build"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without building"),
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve(explicit_path=config_path)
        engine = container_engine or ContainerEngine(settings.container.engine) or ContainerEngine.DOCKER
        engine_value = engine.value
        container_engine = create_container_engine(engine)
        target_backends = list(dict.fromkeys(backend or list(Backend)))

        docker_dir = _resolve_dockerfile(list(Backend)[0]).parent
        project_root = _find_project_root(docker_dir)
        prefix = settings.container.image_prefix
        base_image = engine_qualified_image(
            f"{prefix}-base", engine_value, settings.container.image_tag
        )

        results: list[dict[str, str]] = []

        if not dry_run and project_root is not None:
            base_dockerfile = docker_dir / "Dockerfile.base"
            if base_dockerfile.exists():
                from oci_runtime.domain.types import BuildContext

                ctx_build = BuildContext(
                    build_file_path=base_dockerfile,
                    context_path=project_root,
                )
                container_engine.build_image(ctx_build, base_image)
                results.append({
                    "backend": "base",
                    "image": base_image,
                    "status": "built",
                })

        for b in target_backends:
            image = build_image_name(settings, b, engine_value)
            if dry_run:
                results.append({
                    "backend": b.value,
                    "image": image,
                    "status": "would-build",
                })
            else:
                from oci_runtime.domain.types import BuildContext

                dockerfile = _resolve_dockerfile(b)
                if not dockerfile.exists():
                    raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")
                kwargs = {"build_file_path": dockerfile}
                if project_root is not None:
                    kwargs["context_path"] = project_root
                kwargs["build_args"] = {"BASE_IMAGE": base_image}
                context = BuildContext(**kwargs)
                container_engine.build_image(context, image, backend=b)
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
            adapter.print_table(table)
        elif isinstance(adapter, PlainOutput):
            for r in results:
                print(f"{r['backend']}: {r['image']} [{r['status']}]")
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import json as _json
        import sys
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None
