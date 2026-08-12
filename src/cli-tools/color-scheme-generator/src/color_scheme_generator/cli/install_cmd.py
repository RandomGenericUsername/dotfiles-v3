from __future__ import annotations

import logging
from importlib.resources import files as pkg_files
from pathlib import Path

import typer
from oci_runtime import (
    engine_qualified_image,
    resolve_source_root,
)
from oci_runtime.domain.exceptions import SourceRootNotFoundError

from color_scheme_generator.cli._helpers import build_image_name
from color_scheme_generator.cli.options import CONFIG_OPT, ENGINE_OPT, SOURCE_ROOT_OPT
from color_scheme_generator.domain.enums import Backend, ContainerEngine
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.factory import CliDependencies, create_container_engine

log = logging.getLogger(__name__)

_SOURCE_ROOT_ENV = "CSG_SOURCE_ROOT"


def _resolve_dockerfile(backend: Backend) -> Path:
    return Path(
        str(
            pkg_files("color_scheme_generator.adapters.docker").joinpath(
                f"Dockerfile.{backend.image_suffix}"
            )
        )
    )


def install(
    ctx: typer.Context,
    config_path: Path | None = CONFIG_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to build"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without building"),
    source_root: Path | None = SOURCE_ROOT_OPT,
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve(explicit_path=config_path)
        engine = container_engine or ContainerEngine(settings.container.engine) or ContainerEngine.DOCKER
        engine_value = engine.value
        container_engine = create_container_engine(engine)
        target_backends = list(dict.fromkeys(backend or list(Backend)))

        docker_dir = _resolve_dockerfile(list(Backend)[0]).parent
        prefix = settings.container.image_prefix
        base_image = engine_qualified_image(
            f"{prefix}-base", engine_value, settings.container.image_tag
        )

        # The build context is the source repo. Resolve it up front so a
        # missing context fails loudly instead of silently building a stale
        # image (or skipping the base image entirely).
        project_root: Path | None = None
        if not dry_run:
            try:
                project_root = resolve_source_root(
                    package="color_scheme_generator",
                    override=source_root,
                    env_var=_SOURCE_ROOT_ENV,
                ).root
            except SourceRootNotFoundError as exc:
                raise ColorSchemeError(str(exc)) from None

        results: list[dict[str, str]] = []

        if not dry_run:
            base_dockerfile = docker_dir / "Dockerfile.base"
            if not base_dockerfile.exists():
                raise FileNotFoundError(f"Dockerfile not found: {base_dockerfile}")
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
                context = BuildContext(
                    build_file_path=dockerfile,
                    context_path=project_root,
                    build_args={"BASE_IMAGE": base_image},
                )
                container_engine.build_image(context, image, backend=b)
                results.append({
                    "backend": b.value,
                    "image": image,
                    "status": "built",
                })

        deps.output_adapter.install_result(results)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import json as _json
        import sys
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None
