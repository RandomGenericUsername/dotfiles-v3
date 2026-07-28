from __future__ import annotations

import json
import logging

import typer

from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput
from color_scheme_generator.cli._helpers import build_image_name
from color_scheme_generator.domain.enums import Backend, ContainerEngine
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.factory import CliDependencies, create_container_engine

log = logging.getLogger(__name__)


def uninstall(
    ctx: typer.Context,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to remove"),  # noqa: B008
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),  # noqa: B008
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without removing"),  # noqa: B008
    force: bool = typer.Option(False, "--force", "-f", help="Force image removal even if in use"),  # noqa: B008
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve()
        engine = ctx.obj.get("container_engine") or ContainerEngine(settings.container.engine) or ContainerEngine.DOCKER
        container_engine = create_container_engine(engine)
        target_backends = list(dict.fromkeys(backend or list(Backend)))
        if not yes:
            typer.confirm(
                f"Remove {len(target_backends)} backend image(s)?",
                abort=True,
            )
        results: list[dict[str, str]] = []
        for b in target_backends:
            image = build_image_name(settings, b)
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

        adapter = deps.output_adapter
        if isinstance(adapter, JsonOutput):
            print(json.dumps({"uninstall": results}, indent=2))
        elif isinstance(adapter, RichOutput):
            from rich.table import Table

            table = Table(title="Uninstall Results", box=None)
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
