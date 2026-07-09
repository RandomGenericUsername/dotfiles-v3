from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


class RichOutputAdapter:
    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def process_result(self, result: ProcessingResult) -> None:
        if result.success:
            self._console.print(f"[green]Success:[/green] {escape(result.command)}")
        else:
            self._console.print(f"[red]Failed:[/red] {escape(result.command)}")
        if result.stderr:
            self._console.print(f"[yellow]stderr:[/yellow] {escape(result.stderr)}")
        if result.output_path:
            self._console.print(f"[blue]Output:[/blue] {escape(str(result.output_path))}")
        if result.duration is not None:
            self._console.print(f"[dim]Duration:[/dim] {result.duration:.2f}s")

    def batch_result(self, result: BatchResult) -> None:
        status_color = "green" if result.failed == 0 else "red"
        self._console.print(
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
            self._console.print(table)
        if result.output_dir:
            self._console.print(f"Output directory: [blue]{escape(str(result.output_dir))}[/blue]")

    def catalog_list(self, catalog: EffectsCatalog, query: CatalogQuery) -> None:
        if query == CatalogQuery.EFFECT:
            self._render_effect_table(catalog.effects)
        elif query == CatalogQuery.COMPOSITE:
            self._render_composite_table(catalog.composites)
        elif query == CatalogQuery.PRESET:
            self._render_preset_table(catalog.presets)
        elif query == CatalogQuery.ALL:
            self._render_full_catalog(catalog)

    def config_info(
        self,
        settings: AppSettings,
        catalog: EffectsCatalog,
        sources: list[str],
    ) -> None:
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
        self._console.print(table)

    def dump_config(
        self,
        settings: AppSettings,
        sources: list[str],
    ) -> None:
        table = Table(title="Resolved Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Version", settings.version)
        table.add_row("Parallel", str(settings.execution.parallel))
        table.add_row("Strict", str(settings.execution.strict))
        table.add_row("Max Workers", str(settings.execution.max_workers))
        table.add_row("Verbosity", settings.output.verbosity.value)
        table.add_row("Temp Dir", str(settings.processing.temp_dir))
        table.add_row("Binary", settings.backend.binary)
        table.add_row("Runtime Mode", settings.runtime.mode.value)
        table.add_row("Container Engine", settings.container.engine)
        table.add_row("Image Tag", settings.container.image_tag)
        table.add_row("Image Registry", settings.container.image_registry or "(none)")
        if sources:
            table.add_row("Sources", ", ".join(sources))
        self._console.print(table)

    def error(self, exc: Exception) -> None:
        self._console.print(f"[red]Error:[/red] {escape(type(exc).__name__)}: {escape(str(exc))}")

    def message(self, msg: str) -> None:
        self._console.print(msg)

    def _render_effect_table(self, effects: tuple) -> None:
        table = Table(title="Effects Catalog", show_header=True, header_style="bold")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Command", style="dim")
        for e in effects:
            table.add_row(escape(e.name), escape(e.description), escape(e.command))
        self._console.print(table)

    def _render_composite_table(self, composites: tuple) -> None:
        for c in composites:
            steps = ", ".join(escape(s.effect_name) for s in c.steps)
            self._console.print(f"[bold]{escape(c.name)}[/bold]: [{steps}]")
            if c.description:
                self._console.print(f"  {escape(c.description)}")

    def _render_preset_table(self, presets: tuple) -> None:
        for p in presets:
            self._console.print(f"[bold]{escape(p.name)}[/bold]: {', '.join(escape(e) for e in p.effects)}")

    def _render_full_catalog(self, catalog: EffectsCatalog) -> None:
        self._render_effect_table(catalog.effects)
        if catalog.composites:
            self._console.print("\n[bold]Composites:[/bold]")
            self._render_composite_table(catalog.composites)
        if catalog.presets:
            self._console.print("\n[bold]Presets:[/bold]")
            self._render_preset_table(catalog.presets)
