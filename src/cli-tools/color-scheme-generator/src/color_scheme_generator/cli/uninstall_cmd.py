from __future__ import annotations

import logging
from pathlib import Path

import typer

from color_scheme_generator.cli._helpers import build_image_name
from color_scheme_generator.cli.options import CONFIG_OPT, ENGINE_OPT
from color_scheme_generator.domain.enums import Backend, ContainerEngine
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.factory import CliDependencies, create_container_engine

log = logging.getLogger(__name__)


def uninstall(
    ctx: typer.Context,
    config_path: Path | None = CONFIG_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without removing"),
    force: bool = typer.Option(False, "--force", "-f", help="Force image removal even if in use"),
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve(explicit_path=config_path)
        engine = container_engine or ContainerEngine(settings.container.engine) or ContainerEngine.DOCKER
        engine_value = engine.value
        container_engine = create_container_engine(engine)
        target_backends = list(dict.fromkeys(backend or list(Backend)))
        if not yes:
            typer.confirm(
                f"Remove {len(target_backends)} backend image(s)?",
                abort=True,
            )
        results: list[dict[str, str]] = []
        for b in target_backends:
            image = build_image_name(settings, b, engine_value)
            if dry_run:
                results.append({
                    "backend": b.value,
                    "image": image,
                    "status": "would-remove",
                })
            else:
                container_engine.remove_image(image, force=force, backend=b)
                results.append({
                    "backend": b.value,
                    "image": image,
                    "status": "removed",
                })

        deps.output_adapter.uninstall_result(results)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import json as _json
        import sys
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None
