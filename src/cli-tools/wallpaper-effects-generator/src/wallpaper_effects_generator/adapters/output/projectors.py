from __future__ import annotations

from dataclasses import asdict
from typing import Any

import yaml
from cli_output.domain.views import CustomView, ErrorView, MessageView, ResultView
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from wallpaper_effects_generator.domain.enums import CatalogQuery, ItemType
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


def project_result(result: ProcessingResult) -> ResultView:
    fields: dict[str, Any] = {
        "command": result.command,
        "return_code": result.return_code,
        "duration": result.duration,
    }
    if result.stdout:
        fields["stdout"] = result.stdout
    if result.stderr:
        fields["stderr"] = result.stderr
    if result.output_path:
        fields["output_path"] = str(result.output_path)
    return ResultView(success=result.success, fields=fields)


def project_batch(result: BatchResult) -> CustomView:
    obj: dict[str, Any] = {
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "attempted": result.attempted,
        "cancelled": result.cancelled,
        "output_dir": str(result.output_dir) if result.output_dir else None,
        "results": [asdict(r) for r in result.results],
    }
    lines = [
        f"total: {result.total}",
        f"succeeded: {result.succeeded}",
        f"failed: {result.failed}",
        "---",
    ]
    for r in result.results:
        lines.append(f"  command: {r.command}")
        lines.append(f"  status: {'success' if r.success else 'failure'}")
        if r.stdout:
            lines.append(f"  stdout: {r.stdout}")
        if r.stderr:
            lines.append(f"  stderr: {r.stderr}")
        if r.output_path:
            lines.append(f"  output: {r.output_path}")
        if r.duration:
            lines.append(f"  duration: {r.duration:.2f}s")
        lines.append("  ---")
    if result.output_dir:
        lines.append(f"output_dir: {result.output_dir}")

    def rich(console: Console) -> None:
        status_color = "green" if result.failed == 0 else "red"
        console.print(
            f"[bold]Batch Result:[/bold] "
            f"[{status_color}]{result.succeeded}/{result.total}[/{status_color}] "
            f"succeeded"
        )
        if result.results:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Command", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Duration", style="dim")
            table.add_column("Output", style="blue")
            for r in result.results:
                status = "[green]OK[/green]" if r.success else "[red]FAIL[/red]"
                dur = f"{r.duration:.2f}s" if r.duration else ""
                out = escape(str(r.output_path)) if r.output_path else ""
                table.add_row(escape(r.command), status, dur, out)
            console.print(table)
        if result.output_dir:
            console.print(f"Output directory: [blue]{escape(str(result.output_dir))}[/blue]")

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)


def _effect_to_dict(e: object) -> dict:
    d = asdict(e)
    d["item_type"] = e.item_type.value if isinstance(e.item_type, ItemType) else e.item_type
    d["parameters"] = {
        p.key: {
            "type": str(type(p.default).__name__) if p.default is not None else "string",
            "default": p.default,
            "description": p.description,
        }
        for p in e.parameters
    }
    return d


def _convert(obj: object) -> object:
    if isinstance(obj, tuple):
        return [_convert(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert(i) for i in obj]
    return obj


def project_catalog(catalog: EffectsCatalog, query: CatalogQuery) -> CustomView:
    obj: dict[str, Any]
    if query == CatalogQuery.EFFECT:
        obj = {"items": [asdict(e) for e in catalog.effects], "count": len(catalog.effects)}
    elif query == CatalogQuery.COMPOSITE:
        obj = {"items": [asdict(c) for c in catalog.composites], "count": len(catalog.composites)}
    elif query == CatalogQuery.PRESET:
        obj = {"items": [asdict(p) for p in catalog.presets], "count": len(catalog.presets)}
    else:
        obj = {
            "effects": [asdict(e) for e in catalog.effects],
            "composites": [asdict(c) for c in catalog.composites],
            "presets": [asdict(p) for p in catalog.presets],
        }

    data: dict[str, list] = {}
    if query in (CatalogQuery.EFFECT, CatalogQuery.ALL):
        data["effects"] = [_effect_to_dict(e) for e in catalog.effects]
    if query in (CatalogQuery.COMPOSITE, CatalogQuery.ALL):
        data["composites"] = _convert([asdict(c) for c in catalog.composites])
    if query in (CatalogQuery.PRESET, CatalogQuery.ALL):
        data["presets"] = _convert([asdict(p) for p in catalog.presets])
    plain = yaml.dump({"version": "1.0", **data}, default_flow_style=False, sort_keys=False).rstrip(
        "\n"
    )

    return CustomView(plain=plain, object=obj, rich=_catalog_rich(catalog, query))


def _catalog_rich(catalog: EffectsCatalog, query: CatalogQuery) -> Any:
    def render(console: Console) -> None:
        if query == CatalogQuery.EFFECT:
            _effect_table(console, catalog.effects)
        elif query == CatalogQuery.COMPOSITE:
            _composite_lines(console, catalog.composites)
        elif query == CatalogQuery.PRESET:
            _preset_lines(console, catalog.presets)
        else:
            _effect_table(console, catalog.effects)
            if catalog.composites:
                console.print("\n[bold]Composites:[/bold]")
                _composite_lines(console, catalog.composites)
            if catalog.presets:
                console.print("\n[bold]Presets:[/bold]")
                _preset_lines(console, catalog.presets)

    return render


def _effect_table(console: Console, effects: tuple) -> None:
    table = Table(title="Effects Catalog", show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Command", style="dim")
    for e in effects:
        table.add_row(escape(e.name), escape(e.description), escape(e.command))
    console.print(table)


def _composite_lines(console: Console, composites: tuple) -> None:
    for c in composites:
        steps = ", ".join(escape(s.effect_name) for s in c.steps)
        console.print(f"[bold]{escape(c.name)}[/bold]: [{steps}]")
        if c.description:
            console.print(f"  {escape(c.description)}")


def _preset_lines(console: Console, presets: tuple) -> None:
    for p in presets:
        console.print(f"[bold]{escape(p.name)}[/bold]: {', '.join(escape(e) for e in p.effects)}")


def project_config_info(
    settings: AppSettings,
    catalog: EffectsCatalog,
    sources: list[str],
) -> CustomView:
    obj: dict[str, Any] = {
        "version": settings.version,
        "settings": asdict(settings),
        "catalog": {
            "effects_count": len(catalog.effects),
            "composites_count": len(catalog.composites),
            "presets_count": len(catalog.presets),
        },
        "sources": sources,
    }
    lines = [
        f"version: {settings.version}",
        f"effects_count: {len(catalog.effects)}",
        f"composites_count: {len(catalog.composites)}",
        f"presets_count: {len(catalog.presets)}",
        f"runtime_mode: {settings.runtime.mode.value}",
    ]
    if sources:
        lines.append(f"sources: {', '.join(sources)}")

    def rich(console: Console) -> None:
        table = Table(title="Configuration Info")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Version", settings.version)
        table.add_row("Effects", str(len(catalog.effects)))
        table.add_row("Composites", str(len(catalog.composites)))
        table.add_row("Presets", str(len(catalog.presets)))
        table.add_row("Runtime Mode", settings.runtime.mode.value)
        if sources:
            table.add_row("Sources", ", ".join(sources))
        console.print(table)

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)


def project_error(exc: Exception) -> ErrorView:
    return ErrorView(kind=type(exc).__name__, message=str(exc))


def project_message(msg: str) -> MessageView:
    return MessageView(text=msg)
