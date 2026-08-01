from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress as RichProgress
from rich.table import Table
from rich.text import Text

from cli_output.domain.views import (
    ConfigInfoView,
    CustomView,
    ErrorView,
    ListView,
    MessageView,
    RawView,
    ResultView,
)


class RichRenderer:
    def __init__(self, console: Console | None = None) -> None:
        self._console = console if console is not None else Console()
        self._stderr = Console(stderr=True)

    def message(self, view: MessageView) -> None:
        self._console.print(view.text)

    def result(self, view: ResultView) -> None:
        title = view.title or ("Success" if view.success else "Failure")
        self._console.print(Text(title, style="bold green" if view.success else "bold red"))
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        for key, value in view.fields.items():
            table.add_row(key, str(value))
        self._console.print(table)

    def list(self, view: ListView) -> None:
        table = Table(title=view.title)
        for column in view.columns:
            table.add_column(str(column))
        for row in view.rows:
            table.add_row(*[str(cell) for cell in row])
        self._console.print(table)
        if view.summary:
            for key, value in view.summary.items():
                self._console.print(f"{key}: {value}")

    def error(self, view: ErrorView) -> None:
        panel = Panel(
            Text(view.message, style="red"),
            title=Text(f"Error: {view.kind}", style="bold red"),
            border_style="red",
        )
        self._stderr.print()
        self._stderr.print(panel)
        if view.details:
            self._stderr.print()
            for key, value in view.details.items():
                self._stderr.print(f"  {key}: {value}")
        self._stderr.print()

    def config(self, view: ConfigInfoView) -> None:
        self._console.print(Text("Config", style="bold"))
        self._console.print(f"resolved path: {view.resolved_path}")
        self._console.print(f"sources: {', '.join(view.sources)}")
        for name, data in view.sections:
            self._console.print(Text(f"[{name}]", style="cyan"))
            for key, value in data.items():
                self._console.print(f"  {key}: {value}")
        for override in view.applied_overrides:
            self._console.print(f"override: {override}")

    def raw(self, view: RawView) -> None:
        self._console.print(view.content, end="")

    def custom(self, view: CustomView) -> None:
        if callable(view.rich):
            view.rich(self._console)
        else:
            self._console.print(view.rich)

    def status(self, message: str) -> Any:
        return self._console.status(message)

    @contextmanager
    def progress(self, total: int, message: str) -> Any:
        with RichProgress(console=self._console) as progress:
            task_id = progress.add_task(message, total=total)
            yield _ProgressBar(progress, task_id)


class _ProgressBar:
    def __init__(self, progress: RichProgress, task_id: int) -> None:
        self._progress = progress
        self._task_id = task_id

    def advance(self, advance: int = 1) -> None:
        self._progress.advance(self._task_id, advance)
