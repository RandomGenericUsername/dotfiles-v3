from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
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


class _CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, Enum):
            return o.value
        return str(o)


class JsonRenderer:
    def message(self, view: MessageView) -> None:
        self._write({"message": view.text})

    def result(self, view: ResultView) -> None:
        payload: dict[str, Any] = {"success": view.success}
        payload.update(view.fields)
        if view.title is not None:
            payload["title"] = view.title
        self._write(payload)

    def list(self, view: ListView) -> None:
        payload: dict[str, Any] = {
            "columns": list(view.columns),
            "rows": [list(row) for row in view.rows],
        }
        if view.title is not None:
            payload["title"] = view.title
        if view.summary is not None:
            payload["summary"] = view.summary
        self._write(payload)

    def error(self, view: ErrorView) -> None:
        payload: dict[str, Any] = {"kind": view.kind, "message": view.message}
        if view.details:
            payload["details"] = view.details
        self._write(payload, stream=sys.stderr)

    def config(self, view: ConfigInfoView) -> None:
        payload: dict[str, Any] = {
            "resolved_path": view.resolved_path,
            "sources": list(view.sources),
            "sections": {name: data for name, data in view.sections},
        }
        if view.applied_overrides:
            payload["applied_overrides"] = [dict(override) for override in view.applied_overrides]
        self._write(payload)

    def raw(self, view: RawView) -> None:
        payload: dict[str, Any] = {"content": view.content}
        if view.content_type is not None:
            payload["content_type"] = view.content_type
        self._write(payload)

    def custom(self, view: CustomView) -> None:
        self._write(view.object)

    @contextmanager
    def status(self, message: str) -> Any:
        yield

    @contextmanager
    def progress(self, total: int, message: str) -> Any:
        yield _NoOpProgress()

    def _write(self, payload: Any, *, stream: Any = None) -> None:
        target = stream if stream is not None else sys.stdout
        json.dump(payload, target, cls=_CustomEncoder, indent=2)
        target.write("\n")


class _NoOpProgress:
    def advance(self, advance: int = 1) -> None:
        pass
