from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any

from cli_output.domain.views import (
    ConfigInfoView,
    CustomView,
    ErrorView,
    ListView,
    MessageView,
    RawView,
    ResultView,
)


class PlainRenderer:
    def message(self, view: MessageView) -> None:
        self._write(view.text)

    def result(self, view: ResultView) -> None:
        lines: list[str] = []
        if view.title:
            lines.append(view.title)
        lines.append(f"success: {str(view.success).lower()}")
        for key, value in view.fields.items():
            lines.append(f"{key}: {value}")
        self._write("\n".join(lines))

    def list(self, view: ListView) -> None:
        lines: list[str] = []
        if view.title:
            lines.append(view.title)
        if view.columns:
            widths = [len(str(column)) for column in view.columns]
            for row in view.rows:
                for i, cell in enumerate(row):
                    if i < len(widths):
                        widths[i] = max(widths[i], len(str(cell)))
            lines.append(
                "  ".join(str(column).ljust(widths[i]) for i, column in enumerate(view.columns))
            )
            for row in view.rows:
                cells = [str(cell) for cell in row]
                lines.append(
                    "  ".join(
                        cell.ljust(widths[i]) if i < len(widths) else cell
                        for i, cell in enumerate(cells)
                    )
                )
        if view.summary:
            for key, value in view.summary.items():
                lines.append(f"{key}: {value}")
        self._write("\n".join(lines))

    def error(self, view: ErrorView) -> None:
        self._write(f"error: {view.kind}: {view.message}", stream=sys.stderr)
        for key, value in view.details.items():
            sys.stderr.write(f"  {key}: {value}\n")

    def config(self, view: ConfigInfoView) -> None:
        lines: list[str] = ["config:"]
        lines.append(f"  resolved_path: {view.resolved_path}")
        lines.append(f"  sources: {', '.join(view.sources)}")
        for name, data in view.sections:
            lines.append(f"  section: {name}")
            for key, value in data.items():
                lines.append(f"    {key}: {value}")
        for override in view.applied_overrides:
            lines.append(
                f"  override: {', '.join(f'{key}={value}' for key, value in override.items())}"
            )
        self._write("\n".join(lines))

    def raw(self, view: RawView) -> None:
        self._write(view.content, end="")

    def custom(self, view: CustomView) -> None:
        self._write(view.plain)

    @contextmanager
    def status(self, message: str) -> Any:
        yield

    @contextmanager
    def progress(self, total: int, message: str) -> Any:
        yield _NoOpProgress()

    def _write(self, content: str, *, stream: Any = None, end: str = "\n") -> None:
        target = stream if stream is not None else sys.stdout
        target.write(content)
        if end:
            target.write(end)


class _NoOpProgress:
    def advance(self, advance: int = 1) -> None:
        pass
